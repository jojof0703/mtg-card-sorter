# `src` Folder Guide (Simple English)

This folder has the main program code.

If English is not your first language, use this map:

- `cli.py`  
  Terminal commands (`scan-inbox` command).

- `pipeline.py`  
  Main flow for one image:
  OCR -> parse text -> Scryfall lookup -> card record.

- `ocr.py`  
  Google Vision OCR call.

- `ocr_parser.py` and `ocr_parsing.py`  
  Turn OCR text into useful fields (name, set, collector number).

- `scryfall_client.py`  
  Calls Scryfall API and picks best matching card.

- `sorting.py`  
  Decides bin (`type`, `color`, `value`).

- `dataset/scan_inbox.py`  
  Batch mode for whole folder input and writing sorted output folders.

- `models.py`  
  Card data structure.

- `cache.py`  
  Local cache files to speed repeated runs.
