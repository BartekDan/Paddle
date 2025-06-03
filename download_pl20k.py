import csv
import tarfile
import unicodedata
from pathlib import Path
import urllib.request
import subprocess  # MODIFIED: For low-level filename inspection on Linux

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
    MODIFIED: Inspect the raw byte sequences of the first few filenames
    inside the tar to detect if they are UTF-8 (e.g., bytes C4 85 → "ą") or
    a legacy encoding like CP1250/ISO-8859-2 (e.g., byte B9 → "ą").
    """
    print('Inspecting raw filename bytes in tar:')
    # Use `tar -tf` piped into `head` and `od -An -tx1` to view first <count> names
    proc = subprocess.run(
        [
            'tar', '-tf', str(tar_path),
            '|', 'head', f'-n{count}',
            '|', 'od', '-An', '-tx1'
        ],
        shell=True,  # :contentReference[oaicite:1]{index=1}
        capture_output=True, text=True
    )
    raw = proc.stdout.strip().splitlines()
    for line in raw:
        print('  ', line)
    print("  → Look for byte patterns like 'C4 85' or 'C5 9B' (UTF-8) vs. 'B9' (CP1250).")

def extract_tar(tar_path: Path, out_dir: Path):
    """
    Extraction must respect the archive’s actual filename encoding:
      1. If rawbytes inspection (inspect_tar_rawbytes) shows UTF-8 metadata, use:
         tarfile.open(..., encoding='utf-8').
      2. Otherwise, extract under LC_ALL=C and then fix filenames via convmv.
    """
    # MODIFIED: First inspect raw bytes to decide which encoding to use
    # We run a quick subprocess to check for a UTF-8 BOM in the first filename
    # (In practice, one could parse the first line’s hex output as in inspect_tar_rawbytes)
    print('Determining tarball filename encoding...')
    proc = subprocess.run(
        f"tar -tf '{tar_path}' | head -n1 | od -An -tx1 | head -n1",
        shell=True, capture_output=True, text=True
    )
    hexbytes = proc.stdout.strip().split()
    is_utf8 = False
    # If the first two bytes match a typical UTF-8 diacritic (e.g., C4, C5), assume UTF-8
    if len(hexbytes) >= 2 and hexbytes[0].lower() in ('c4', 'c5'):
        is_utf8 = True

    if is_utf8:
        print("  → Archive filenames appear to be UTF-8. Extracting with encoding='utf-8'.")
        with tarfile.open(tar_path, mode='r:gz', encoding='utf-8', errors='surrogateescape') as tar:
            tar.extractall(path=out_dir)
        # :contentReference[oaicite:2]{index=2}
    else:
        print("  → Archive filenames appear to be non-UTF-8. Extracting raw bytes under LC_ALL=C.")
        # Extract raw (no decoding) by invoking system tar under C locale
        subprocess.run(
            ['bash', '-lc', f'LC_ALL=C tar -xzf "{tar_path}" -C "{out_dir}"'],
            check=True
        )  # :contentReference[oaicite:3]{index=3}

        print("  → Running convmv to convert CP1250 → UTF-8 on all extracted filenames.")
        subprocess.run(
            ['convmv', '-f', 'cp1250', '-t', 'utf8', '-r', '--notest', str(out_dir)],
            check=True
        )  # :contentReference[oaicite:4]{index=4}

    # Normalize extracted filenames to NFC so that CSV matching works
    for path in sorted(out_dir.rglob('*'), key=lambda p: len(str(p)), reverse=True):
        new_name = unicodedata.normalize('NFC', path.name)
        if new_name != path.name:
            path.rename(path.with_name(new_name))
            # :contentReference[oaicite:5]{index=5}

def read_csv_guess(path: Path):
    """
    MODIFIED: Try common encodings (UTF-8, CP1250, ISO-8859-2). If none work,
    raise an error. This ensures CSV filenames (with diacritics) are read correctly.
    """
    for enc in ('utf-8', 'cp1250', 'iso-8859-2'):
        try:
            with path.open(encoding=enc) as f:
                data = f.read()
            print(f'CSV decoded with {enc}')
            return data, enc
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError('csv', b'', 0, 1, 'Unable to decode with common encodings')

def ensure_csv_utf8(path: Path):
    """
    If the CSV is not already UTF-8, convert it using the detected encoding.
    """
    data, enc = read_csv_guess(path)
    if enc != 'utf-8':
        print(f'Converting CSV from {enc} → UTF-8')
        path.write_text(data, encoding='utf-8')
        # :contentReference[oaicite:6]{index=6}

def verify_files(csv_path: Path, data_dir: Path):
    """
    Iterates through the CSV’s first column (filename), normalizes to NFC, and
    checks existence in data_dir. Reports missing files if any.
    """
    missing = []
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            # Skip header if detected
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
        print('First few:', missing[:10])
    else:
        print('All filenames match between CSV and extracted data.')

def main():
    tar_path = DATA_DIR / 'PL-20k-hand-labelled.tar.gz'
    csv_path = DATA_DIR / 'PL-20k-hand-labelled_labels.csv'
    extract_root = DATA_DIR

    download(TAR_URL, tar_path)
    download(CSV_URL, csv_path)

    # MODIFIED: Inspect raw filename bytes (not just decoded names) before extraction
    inspect_tar_rawbytes(tar_path, count=5)

    extract_tar(tar_path, extract_root)
    ensure_csv_utf8(csv_path)
    verify_files(csv_path, extract_root / 'PL-20k-hand-labelled')

if __name__ == '__main__':
    main()
