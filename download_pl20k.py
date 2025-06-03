import csv
import tarfile
import unicodedata
from pathlib import Path
import urllib.request

DATA_DIR = Path('My data')
TAR_URL = 'https://github.com/perechen/htr_lexicography/raw/main/data/PL-20k-hand-labelled.tar.gz'
CSV_URL = 'https://raw.githubusercontent.com/perechen/htr_lexicography/main/data/PL-20k-hand-labelled_labels.csv'

def download(url: str, dest: Path):
    if dest.exists():
        print(f'{dest} already exists, skipping download.')
        return
    print(f'Downloading {url} -> {dest}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)

def inspect_tar_names(tar_path: Path, count: int = 5):
    print('Inspecting first filenames in tar:')
    with tarfile.open(tar_path, 'r:gz') as tar:
        for member in tar.getmembers()[:count]:
            print('  ', member.name)

def extract_tar(tar_path: Path, out_dir: Path):
    print(f'Extracting {tar_path} to {out_dir}')
    out_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, mode='r:gz', encoding='utf-8', errors='surrogateescape') as tar:
        tar.extractall(path=out_dir)

# Simple encoding detection for the CSV

def read_csv_guess(path: Path):
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
    data, enc = read_csv_guess(path)
    if enc != 'utf-8':
        print(f'Converting CSV from {enc} to UTF-8')
        path.write_text(data, encoding='utf-8')


def verify_files(csv_path: Path, data_dir: Path):
    missing = []
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0 and row and row[0].strip().lower() in (
                'path', 'image', 'file_name', 'filename'):
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
    extract_dir = DATA_DIR / 'PL-20k-hand-labelled'

    download(TAR_URL, tar_path)
    download(CSV_URL, csv_path)

    inspect_tar_names(tar_path)
    extract_tar(tar_path, extract_dir)

    ensure_csv_utf8(csv_path)
    verify_files(csv_path, extract_dir)

if __name__ == '__main__':
    main()
