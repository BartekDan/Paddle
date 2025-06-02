# Paddle OCR Training with Custom Data

This repository contains a minimal example showing how to train a PaddleOCR
recognition model on a custom dataset stored under `My data/`.

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

## Training

A training configuration is provided at
`PaddleOCR-main/configs/rec/my_rec_train.yml`. Start training with:

```bash
cd PaddleOCR-main
python3 tools/train.py -c configs/rec/my_rec_train.yml
```

The config expects images referenced in `train_labels.txt` to be relative to the
`My data` directory.
