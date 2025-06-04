import csv
import tarfile
import unicodedata
from pathlib import Path
import urllib.request
import subprocess
import os
import sys

DATA_DIR = Path('My data')
TAR_URL = 'https://github.com/perechen/htr_lexicography/raw/main/data/PL-20k-hand-labelled.tar.gz'
CSV_URL = 'https://raw.githubusercontent.com/perechen/htr_lexicography/main/data/PL-20k-hand-labelled_labels.csv'


def download(url: str, dest: Path):
    if dest.exists():
        print(f'{dest} already exists, skipping download.')
        return
    print(f'Downloading {url} → {dest}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    #


def inspect_tar_rawbytes(tar_path: Path, count: int = 5):
    """
    Inspect the raw byte values of the first few filenames in the tarball
    so we can see patterns like C3, C4, C5 (UTF-8 diacritics) vs. B9 (CP1250).
    """
    print('Inspecting raw filename bytes in tar:')
    cmd = f"tar -tf '{tar_path}' | head -n {count} | od -An -tx1"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    lines = proc.stdout.strip().splitlines()
    for line in lines:
        print('  ', line)
    print("  → Search these lines for 'C3', 'C4', 'C5' (UTF-8) vs. 'B9' (CP1250).")
    # :contentReference[oaicite:3]{index=3}


def likely_utf8_filename(hexbytes: list):
    """
    REVISED:
    Examine a list of hex byte strings; return True if any byte looks like
    the start of a UTF-8 encoded non-ASCII character (C2–DF, E0–EF, F0–F7).
    """
    for hb in hexbytes:
        byte_val = int(hb, 16)
        # In UTF-8, multi-byte sequences start with 0xC2–0xF4
        if (0xC2 <= byte_val <= 0xF4):
            return True
    return False  # :contentReference[oaicite:4]{index=4}


def extract_tar(tar_path: Path, out_dir: Path):
    """
    REVISED:
    1) Inspect raw bytes of filenames to decide if archive metadata is UTF-8.
    2) If likely UTF-8, extract with tarfile.open(…, encoding='utf-8').
    3) Otherwise, extract raw and do CP1250→UTF-8 with convmv or fallback Python logic.
    """
    # Step 1: Get raw hex bytes for first line of tar listing
    print('Determining tarball filename encoding...')
    proc = subprocess.run(
        f"tar -tf '{tar_path}' | head -n1 | od -An -tx1 | head -n1",
        shell=True, capture_output=True, text=True
    )
    hexbytes = proc.stdout.strip().split()

    # REVISED: use improved detection instead of only the first byte
    is_utf8 = likely_utf8_filename(hexbytes)
    if is_utf8:
        print("  → Appears to be UTF-8 encoded filenames. Extracting with encoding='utf-8'.")
        with tarfile.open(tar_path, mode='r:gz', encoding='utf-8', errors='surrogateescape') as tar:
            tar.extractall(path=out_dir)
        # :contentReference[oaicite:5]{index=5}
    else:
        print("  → Filenames appear non-UTF-8. Extracting raw bytes under LC_ALL=C.")
        subprocess.run(
            ['bash', '-lc', f'LC_ALL=C tar -xzf "{tar_path}" -C "{out_dir}"'],
            check=True
        )  # :contentReference[oaicite:6]{index=6}

        # Attempt to install and run convmv; if not available, fallback to Python
        try:
            subprocess.run(['convmv', '--version'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            convmv_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            convmv_available = False

        if convmv_available:
            print("  → Running convmv to convert CP1250 → UTF-8 on all extracted filenames.")
            subprocess.run(
                ['convmv', '-f', 'cp1250', '-t', 'utf8', '-r', '--notest', str(out_dir)],
                check=True
            )  # :contentReference[oaicite:7]{index=7}
        else:
            print("  → `convmv` not found. Falling back to pure-Python renaming (CP1250→UTF-8).")
            for root, dirs, files in os.walk(out_dir, topdown=False):
                for fname in files:
                    old_path = Path(root) / fname
                    try:
                        raw_bytes = fname.encode('cp1250', errors='replace')
                        new_fname = raw_bytes.decode('utf-8', errors='replace')
                    except Exception:
                        # If the fallback fails, skip
                        continue
                    new_fname_nfc = unicodedata.normalize('NFC', new_fname)
                    if new_fname_nfc != fname:
                        old_path.rename(old_path.with_name(new_fname_nfc))
                for dname in dirs:
                    old_dir = Path(root) / dname
                    try:
                        raw_bytes = dname.encode('cp1250', errors='replace')
                        new_dname = raw_bytes.decode('utf-8', errors='replace')
                    except Exception:
                        continue
                    new_dname_nfc = unicodedata.normalize('NFC', new_dname)
                    if new_dname_nfc != dname:
                        old_dir.rename(old_dir.with_name(new_dname_nfc))
            # :contentReference[oaicite:8]{index=8}

    # Finally, normalize all extracted names to NFC
    for path in sorted(out_dir.rglob('*'), key=lambda p: len(str(p)), reverse=True):
        new_name = unicodedata.normalize('NFC', path.name)
        if new_name != path.name:
            path.rename(path.with_name(new_name))
            # :contentReference[oaicite:9]{index=9}


def read_csv_guess(path: Path):
    """
    Try decoding the CSV as UTF-8, CP1250, then ISO-8859-2. Return decoded text & encoding.
    """
    for enc in ('utf-8', 'cp1250', 'iso-8859-2'):
        try:
            with path.open(encoding=enc) as f:
                data = f.read()
            print(f'CSV decoded with {enc}')
            return data, enc
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError('Unable to decode CSV with utf-8, cp1250, or iso-8859-2')


def ensure_csv_utf8(path: Path):
    """
    If CSV is not UTF-8, rewrite it as UTF-8.
    """
    data, enc = read_csv_guess(path)
    if enc != 'utf-8':
        print(f'Converting CSV from {enc} → UTF-8')
        path.write_text(data, encoding='utf-8')
        # :contentReference[oaicite:10]{index=10}


def verify_files(csv_path: Path, data_dir: Path):
    """
    Compare each normalized CSV filename to actual files. Report any missing.
    """
    missing = []
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0 and row and row[0].strip().lower() in (
                    'path', 'image', 'file_name', 'filename'
            ):
                continue
            if not row:
                continue
            fname = unicodedata.normalize('NFC', row[0].strip())
            if not (data_dir / fname).exists():
                missing.append(fname)
    if missing:
        print('Missing files:', len(missing))
        print('First few missing:', missing[:10])
    else:
        print('All filenames match between CSV and extracted data.')


def main():
    tar_path = DATA_DIR / 'PL-20k-hand-labelled.tar.gz'
    csv_path = DATA_DIR / 'PL-20k-hand-labelled_labels.csv'
    extract_root = DATA_DIR

    download(TAR_URL, tar_path)
    download(CSV_URL, csv_path)

    inspect_tar_rawbytes(tar_path, count=5)
    extract_tar(tar_path, extract_root)
    ensure_csv_utf8(csv_path)
    verify_files(csv_path, extract_root / 'PL-20k-hand-labelled')


if __name__ == '__main__':
    main()
