# MTG Inbox Dataset Builder

Build controlled datasets of Magic: The Gathering card images for sorting and OCR evaluation. Downloads images from **Scryfall**, organizes them into groups, seeds an inbox, and measures identification accuracy with **Google Cloud Vision OCR**.

---

## What This Project Does

This project focuses on the **programs that create the inbox dataset**—the images that get sorted. You can:

1. **Build a dataset** – Download card images from Scryfall into structured groups (lands, creatures, artifacts, multicolor) with ground-truth metadata
2. **Seed the inbox** – Copy sample images from the dataset into `data/inbox/` for demo or testing
3. **Organize by type** – Sort dataset images into Creatures/Spells/Permanents/Lands using metadata (no OCR)
4. **Rename files** – Convert UUID filenames to `Card Name (set).png` for readability
5. **Run OCR evaluation** – Measure how accurately Vision OCR + Scryfall identify cards from the dataset

The built dataset is the foundation: it provides known card images and metadata for inbox seeding, OCR benchmarking, and downstream sorting.

---

## Key Terms

- **Scryfall** – Free online database of all MTG cards. We download images and look up cards by name, set code (e.g. M21), and collector number.
- **Inbox** – `data/inbox/` where you place card images to be processed and sorted.
- **OCR** – Optical Character Recognition. Google Vision reads text from images so we can identify cards.
- **Set code** – Short identifier (e.g. M21 = Core Set 2021, DOM = Dominaria).
- **Collector number** – Card’s number within its set (e.g. 123/280).

---

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Google Cloud Vision**

   Place your service account JSON key at `credentials/google-vision-key.json`. The app loads it from there (no env var needed).

---

## Dataset Creation Pipeline

### 1. Build dataset

Downloads card images from Scryfall into 4 groups with metadata:

```bash
python -m src.cli dataset build --name baseline_v1 --per_group 50 --out data/datasets
```

- `--prints` (default): Different printings per card (e.g. Lightning Bolt from M10 and M21)
- `--cards`: One image per card name

### 2. Seed inbox

Copy random images from the dataset into the inbox for demo:

```bash
python -m src.cli scan-inbox --seed 5
```

Requires a built dataset at `data/datasets/baseline_v1/`.

### 3. Organize dataset by type (optional)

Sort downloaded images into Creatures/Spells/Permanents/Lands using metadata (no OCR):

```bash
python scripts/sort_dataset_by_type.py baseline_v1
```

Output: `data/datasets/baseline_v1/sorted_by_type/`.

### 4. Rename to card names (optional)

Convert UUID filenames to `Card Name (set).png` in inbox and sorted folders:

```bash
python scripts/rename_to_card_names.py
```

Use `--dry-run` to preview changes.

---

## OCR Evaluation

Measure how accurately Vision OCR + Scryfall identify cards from the dataset:

```bash
python -m src.cli dataset ocr-eval --name baseline_v1 --out data/datasets --limit 200
```

Output: `results.json` (accuracy, by-group stats), `failures.csv` (wrong/missed cards). Use `scripts/debug_ocr_failure.py` to inspect individual failures.

---

## Dataset Layout

```
data/datasets/<name>/
├── images/
│   ├── lands/
│   ├── creatures/
│   ├── artifacts/
│   └── multicolor/
├── metadata.jsonl      # Ground truth: name, set, collector_number, type_line, etc.
├── ocr/                # Cached OCR text (per image)
├── results.json        # OCR eval accuracy
├── failures.csv        # Failed identifications
└── sorted_by_type/     # Optional: Creatures/, Spells/, Permanents/, Lands/
```

---

## Downstream: Scan Inbox

Once the inbox has images (from seeding or your own photos), process and sort them:

```bash
python -m src.cli scan-inbox --inbox data/inbox --out data/sorted --mode type
```

Modes: `color`, `type`, or `value`. See `src/sorting.py` for group definitions.

---

## Project Structure

| Path | Purpose |
|------|---------|
| `src/dataset/build_dataset.py` | Download Scryfall images, write metadata.jsonl |
| `src/dataset/scan_inbox.py` | Seed inbox, scan images, OCR + sort |
| `src/dataset/ocr_eval.py` | Run OCR evaluation, compare to ground truth |
| `scripts/sort_dataset_by_type.py` | Organize dataset images by type (metadata only) |
| `scripts/rename_to_card_names.py` | UUID → `Card Name (set).png` |
| `scripts/debug_ocr_failure.py` | Inspect OCR eval failures |
| `src/ocr_parsing.py` | Parse name, set, collector number from OCR text |
| `src/services/vision_ocr.py` | Google Cloud Vision integration |

---

## API Etiquette

- Scryfall: `User-Agent: MTGCardSorter/1.0 (School Project)`, ~100 ms delay between requests
- OCR and Scryfall results cached in `~/.mtg_card_sorter/`
