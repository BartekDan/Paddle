import csv
from pathlib import Path

# Paths
csv_path = Path('My data/PL-20k-hand-labelled_labels.csv')
label_txt_path = Path('My data/train_labels.txt')
dict_path = Path('My data/dict.txt')

unique_chars = set()

with csv_path.open(newline='', encoding='utf-8') as csvfile, \
     label_txt_path.open('w', encoding='utf-8') as outfile:
    reader = csv.reader(csvfile)
    for i, row in enumerate(reader):
        if i == 0 and row[0].strip().lower() in ("path", "image", "file_name", "filename"):
            continue
        if len(row) < 2:
            continue
        img_path = row[0].strip()
        label = row[1].strip()
        outfile.write(f"{img_path}\t{label}\n")
        for ch in label:
            unique_chars.add(ch)

# Write dictionary
char_list = sorted(unique_chars)
with dict_path.open('w', encoding='utf-8') as f:
    for ch in char_list:
        f.write(f"{ch}\n")

print(f"Wrote {label_txt_path} with {len(char_list)} unique chars")
