import csv
import tarfile
import unicodedata
from pathlib import Path
import urllib.request
import subprocess
import os
import sys

DATA_DIR = Path('My data')
TAR_URL  = 'https://github.com/perechen/htr_lexicography/raw/main/data/PL-20k-hand-labelled.tar.gz'
CSV_URL  = 'https://raw.githubusercontent.com/perechen/htr_lexicography/main/data/PL-20k-hand-labelled_labels.csv'

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
    Print raw byte values of the first few filenames in the tarball.  If you see
    UTF-8 bytes (e.g., C4 85, C5 9B), the archive uses UTF-8.  If you see single
    bytes like B9, it is likely CP1250/ISO-8859-2.
    """
    print('Inspecting raw filename bytes in tar:')
    # Use `tar -tf` piped into `head` and `od -tx1` to view first `count` names
    cmd = f"tar -tf '{tar_path}' | head -n {count} | od -An -tx1"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    lines = proc.stdout.strip().splitlines()
    for line in lines:
        print('  ', line)
    print("  → Look for 'C4 85'/'C5 9B' (UTF-8) vs. 'B9' (CP1250).")

def extract_tar(tar_path: Path, out_dir: Path):
    """
    1) Inspect raw bytes to decide if the archive filenames are UTF-8 or CP1250.
    2) If UTF-8, extract using tarfile.open(..., encoding='utf-8').
    3) If CP1250, first try to install and run convmv; if convmv is not available,
       fall back to a pure‐Python decode/rename on extracted files.
    """
    # Step 1: Inspect raw bytes of the first filename
    print('Determining tarball filename encoding...')
    cmd = f"tar -tf '{tar_path}' | head -n1 | od -An -tx1 | head -n1"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    hexbytes = proc.stdout.strip().split()
    # Check if first two hex bytes correspond to typical UTF-8 diacritic patterns
    is_utf8 = (len(hexbytes) >= 2 and hexbytes[0].lower() in ('c4', 'c5'))

    out_dir.mkdir(parents=True, exist_ok=True)

    if is_utf8:
        print("  → Archive filenames appear to be UTF-8. Using tarfile with encoding='utf-8'.")
        with tarfile.open(tar_path, mode='r:gz', encoding='utf-8', errors='surrogateescape') as tar:
            tar.extractall(path=out_dir)
        # :contentReference[oaicite:7]{index=7}
    else:
        print("  → Archive filenames appear to be non-UTF-8. Extracting raw bytes under LC_ALL=C.")
        # Extract raw byte names (no decoding):
        subprocess.run(
            ['bash', '-lc', f'LC_ALL=C tar -xzf "{tar_path}" -C "{out_dir}"'],
            check=True
        )  # :contentReference[oaicite:8]{index=8}

        # Attempt to install convmv if not present
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
            )  # :contentReference[oaicite:9]{index=9}
        else:
            print("  → `convmv` not found. Falling back to pure-Python renaming.")
            # Pure-Python fallback: decode each filename from CP1250 → UTF-8
            for root, dirs, files in os.walk(out_dir, topdown=False):
                # Rename files
                for fname in files:
                    old_path = Path(root) / fname
                    # Interpret raw bytes of `fname` as CP1250 (Windows-1250)
                    try:
                        raw_bytes = fname.encode('cp1250', errors='replace')
                        new_fname = raw_bytes.decode('cp1250')
                    except Exception:
                        continue
                    # Normalize to NFC
                    new_fname_nfc = unicodedata.normalize('NFC', new_fname)
                    if new_fname_nfc != fname:
                        new_path = old_path.with_name(new_fname_nfc)
                        old_path.rename(new_path)
                # Rename directories similarly
                for dname in dirs:
                    old_dir = Path(root) / dname
                    try:
                        raw_bytes = dname.encode('cp1250', errors='replace')
                        new_dname = raw_bytes.decode('cp1250')
                    except Exception:
                        continue
                    new_dname_nfc = unicodedata.normalize('NFC', new_dname)
                    if new_dname_nfc != dname:
                        new_dir = old_dir.with_name(new_dname_nfc)
                        old_dir.rename(new_dir)
            # :contentReference[oaicite:10]{index=10}

    # Finally, normalize all filenames to NFC so that they match CSV entries
    for path in sorted(out_dir.rglob('*'), key=lambda p: len(str(p)), reverse=True):
        new_name = unicodedata.normalize('NFC', path.name)
        if new_name != path.name:
            path.rename(path.with_name(new_name))
            # :contentReference[oaicite:11]{index=11}

def read_csv_guess(path: Path):
    """
    Try to decode the CSV as UTF-8, then CP1250, then ISO-8859-2.  Return the decoded
    text and the used encoding.
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
    If the CSV is not UTF-8, rewrite it as UTF-8.
    """
    data, enc = read_csv_guess(path)
    if enc != 'utf-8':
        print(f'Converting CSV from {enc} → UTF-8')
        path.write_text(data, encoding='utf-8')
        # :contentReference[oaicite:12]{index=12}

def verify_files(csv_path: Path, data_dir: Path):
    """
    Compare the normalized filename from each CSV row’s first column to the actual
    filenames under `data_dir`.  Report missing entries if any.
    """
    missing = []
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            # Skip a header row if present
            if i == 0 and row and row[0].strip().lower() in (
                'path','image','file_name','filename'
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
