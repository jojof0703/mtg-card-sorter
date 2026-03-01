# MTG Card Sorter

Sort Magic: The Gathering cards using **Google Cloud Vision OCR** and **Scryfall API**.

---

## For Complete Beginners

**What does this project do?** You take photos of MTG (Magic: The Gathering) cards, and the app identifies each card and sorts them into folders (by color, type, or value). No manual typing needed.

**Key terms:**
- **OCR** = Optical Character Recognition. Software that "reads" text from an image. We use Google's Vision API.
- **Scryfall** = A free online database of all MTG cards. We look up cards by name, set code (e.g. M21), and collector number (e.g. 123/280).
- **Set code** = Short identifier for a card set (e.g. M21 = Core Set 2021, DOM = Dominaria).
- **Collector number** = The card's number within its set (e.g. 123/280 means card 123 of 280).

**Project structure (where to look):**
- `src/cli.py` – Main entry point. Interactive menu and commands.
- `src/pipeline.py` – Core workflow: image → OCR → parse → Scryfall → card.
- `src/ocr_parsing.py` – Extracts name, set, collector number from OCR text (regex-heavy).
- `src/sorting.py` – Puts cards into 4 groups (color, type, or value).
- `src/models.py` – CardRecord: what a "card" looks like in our app.
- `src/cache.py` – Saves OCR and Scryfall results so we don't repeat API calls.
- `scripts/` – Helper scripts for testing and debugging.

---

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Google Cloud Vision**

   Place your service account JSON key at `credentials/google-vision-key.json`. The app loads it automatically from there (no env var needed).

3. **Run**

   - **CLI**: `python main.py` or `python -m src.cli`
   - **Web UI**: `python -m src.app` then open http://127.0.0.1:5000

## Pipeline

1. **Capture** – Take photos of cards (or use existing images).
2. **OCR** – Google Vision `DOCUMENT_TEXT_DETECTION` extracts text.
3. **Parse** – Extract collector number (e.g. `123/280` → `123`), set code (3-letter), and card name.
4. **Identify** – Scryfall lookup in order:
   - `GET /cards/{set}/{collector_number}` if set + number available
   - `GET /cards/named?fuzzy={name}` otherwise
   - `GET /cards/search?q={query}` if fuzzy fails; best match by similarity
5. **Store** – Results cached locally (OCR + Scryfall) so re-scanning is fast.
6. **Sort** – Choose one of 3 modes, each with 4 groups.

## Sort Modes

### A. Color Bucket

- **Mono-Color** – Exactly 1 color
- **Multi-Color** – 2+ colors
- **Colorless** – No colors (e.g. artifacts)
- **Lands** – `type_line` contains "Land" (always, even if colored)

### B. Card Type

- **Creatures** – Creature
- **Spells** – Instant or Sorcery
- **Permanents** – Artifact, Enchantment, or Planeswalker
- **Lands** – Land

### C. Value

- **Hits** – Mythic OR USD ≥ $10
- **Good Stuff** – Rare OR USD $2–$9.99
- **Playable Commons/Uncommons** – Uncommon OR USD $0.50–$1.99
- **Bulk** – Common OR USD &lt; $0.50 OR missing price

Uses the higher of `usd` and `usd_foil` when both exist.

## Error Handling

- **OCR fails** – Message: re-take photo with better lighting and fill frame.
- **Multiple Scryfall matches** – CLI shows top 3 candidates for manual selection.

## API Etiquette

- Scryfall requests use `User-Agent: MTGCardSorter/1.0 (School Project)`
- ~100 ms delay between Scryfall requests
- OCR and Scryfall results cached in `~/.mtg_card_sorter/`

---

## Dataset Harness (OCR Evaluation)

Reproducible Option B dataset: download Scryfall card images, run Vision OCR, measure identification accuracy.

### Setup

Same as above: place your service account JSON at `credentials/google-vision-key.json`.

### Build dataset

Downloads 4 groups (lands, creatures, artifacts, multicolor), 50 images per group by default:

```bash
python -m src.cli dataset build --name baseline_v1 --per_group 50 --out data/datasets
```

Use `--prints` (default) for different printings per card, or `--cards` for one per card name.

### Run OCR evaluation

Runs Vision OCR on dataset images, identifies cards via Scryfall, compares to ground truth:

```bash
python -m src.cli dataset ocr-eval --name baseline_v1 --out data/datasets --limit 200
```

### Output layout

```
data/datasets/<name>/
├── images/
│   ├── lands/
│   ├── creatures/
│   ├── artifacts/
│   └── multicolor/
├── metadata.jsonl      # One record per image
├── ocr/                # Cached OCR text (per image)
├── results.json        # Accuracy, by-group stats
└── failures.csv        # Failed identifications with details
```
