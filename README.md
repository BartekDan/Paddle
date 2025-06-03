# Paddle OCR Training with Custom Data

This repository contains a minimal example showing how to train a PaddleOCR
recognition model on a custom dataset stored under `My data/`.

Run `download_pl20k.py` to download the sample dataset and normalize all
filenames to UTF-8 so they match the accompanying CSV labels:

```bash
python3 download_pl20k.py
```

The script extracts `PL-20k-hand-labelled.tar.gz` and converts any decomposed
Unicode sequences in file paths to their canonical NFC form.

## Preparing the Dataset

Run `prepare_paddleocr_data.py` to convert the CSV labels into the format
expected by PaddleOCR and to generate a character dictionary:

```bash
python3 prepare_paddleocr_data.py
```

This script reads `My data/PL-20k-hand-labelled_labels.csv` and writes two files
in the same directory:

- `train_labels.txt` – each line has `image_path\tlabel`
- `dict.txt` – one unique character per line

The script also normalizes all filenames and CSV entries to Unicode NFC form so
that paths in `train_labels.txt` match the actual files on disk.

## Training

A training configuration is provided at
`PaddleOCR-main/configs/rec/my_rec_train.yml`. Start training with:

```bash
cd PaddleOCR-main
python3 tools/train.py -c configs/rec/my_rec_train.yml
```

The config expects images referenced in `train_labels.txt` to be relative to the
`My data` directory. For evaluation, it uses `eval_labels.txt` from the same
directory as the validation split.
