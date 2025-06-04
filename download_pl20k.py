import libarchive.public
import unicodedata
import csv
from pathlib import Path
import urllib.request

DATA_DIR = Path("My data")
TAR_URL = "https://github.com/perechen/htr_lexicography/raw/main/data/PL-20k-hand-labelled.tar.gz"
CSV_URL = "https://raw.githubusercontent.com/perechen/htr_lexicography/main/data/PL-20k-hand-labelled_labels.csv"
ARCHIVE_PATH = DATA_DIR / "PL-20k-hand-labelled.tar.gz"
CSV_PATH     = DATA_DIR / "PL-20k-hand-labelled_labels.csv"
EXTRACT_DIR  = DATA_DIR / "PL-20k-hand-labelled"

def download(url: str, dest: Path):
    if dest.exists():
        print(f"{dest} already exists, skipping download.")
        return
    print(f"Downloading {url} → {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)

def extract_with_libarchive(tar_path: Path, out_dir: Path, codec: str):
    """
    Extract using libarchive with a specific header_codec.
    """
    print(f"Extracting {tar_path.name} with header_codec='{codec}'")
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with libarchive.public.file_reader(str(tar_path), header_codec=codec) as archive:
            for entry in archive:
                # entry.pathname is already a Python str decoded with `codec`
                out_path = out_dir / unicodedata.normalize("NFC", entry.pathname)
                # Ensure parent directories exist
                out_path.parent.mkdir(parents=True, exist_ok=True)
                if entry.isdir:
                    continue
                with open(out_path, "wb") as f:
                    for block in entry.get_blocks():
                        f.write(block)
        return True
    except Exception as e:
        print(f"✘ Extraction with codec='{codec}' failed: {e}")
        return False

def ensure_csv_utf8(path: Path):
    """
    Read the CSV, detect its encoding among ('utf-8','cp1250','iso-8859-2'),
    and rewrite as UTF-8 if needed.
    """
    for enc in ("utf-8", "cp1250", "iso-8859-2"):
        try:
            text = path.read_text(encoding=enc)
            print(f"CSV decoded with {enc}")
            if enc != "utf-8":
                path.write_text(text, encoding="utf-8")
                print(f"Converted CSV from {enc} → utf-8")
            return
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("Cannot decode CSV with utf-8, cp1250, or iso-8859-2")

def verify_and_write_labels(csv_path: Path, images_dir: Path, out_labels: Path):
    """
    Verify every CSV filename exists in images_dir, then write train_labels.txt.
    """
    df_valid = []
    df_missing = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0 and row and row[0].strip().lower() in (
                "path", "image", "file_name", "filename"
            ):
                continue
            if not row or not row[0].strip():
                continue
            fname = unicodedata.normalize("NFC", row[0].strip())
            label = unicodedata.normalize("NFC", row[1].strip()) if len(row) > 1 else ""
            if (images_dir / fname).is_file():
                df_valid.append(f"{fname} {label}")
            else:
                df_missing.append(fname)
    print(f"✔ Found {len(df_valid)} matching files, {len(df_missing)} missing.")
    out_labels.write_text("\n".join(df_valid), encoding="utf-8")
    if df_missing:
        print("First few missing:", df_missing[:10])

def main():
    # 1) Download archive & CSV
    download(TAR_URL, ARCHIVE_PATH)
    download(CSV_URL, CSV_PATH)

    # 2) Ensure CSV is UTF-8
    ensure_csv_utf8(CSV_PATH)

    # 3) Try extracting with UTF-8, else fallback to CP1250
    if not extract_with_libarchive(ARCHIVE_PATH, EXTRACT_DIR, codec="utf-8"):
        print("Retrying extraction with CP1250 decoding...")
        if not extract_with_libarchive(ARCHIVE_PATH, EXTRACT_DIR, codec="cp1250"):
            raise RuntimeError("Both UTF-8 and CP1250 extraction failed.")

    # 4) Verify filenames and write train_labels.txt
    verify_and_write_labels(
        CSV_PATH,
        EXTRACT_DIR,
        out_labels=DATA_DIR / "train_labels.txt"
    )

if __name__ == "__main__":
    main()
