# MTG Card Sorter (Simple Guide)

This project reads a Magic card picture and tells you which **bin** it goes to.

The app can sort by:
- `type` (Creatures / Spells / Permanents / Lands)
- `color`
- `value`

---

## 1) What You Need

- Python installed
- Google Vision key file at:
  - `credentials/google-vision-key.json`
- Internet connection (for Scryfall card lookup)

Install packages:

```bash
pip install -r requirements.txt
```

---

## 2) Fastest Way (One File -> Bin + Time)

Use this script:

```bash
python scripts/bin_from_path.py "data/Magic the gathering Iphone/Screenshot 2026-04-13 185409.png" --mode type
```

What it prints:
- card name
- selected bin
- time in seconds and milliseconds

Important:
- this script runs with cache OFF (`decached` / cold)
- so the timing is real full processing time

---

## 3) Folder -> Sorted Output Folders

```bash
python -m src.cli scan-inbox --in "data/Magic the gathering Iphone" --out "data/sorted_phone_dataset" --mode type
```

This command:
1. reads all images in input folder
2. identifies each card
3. creates output folders by bin
4. copies each image into the correct folder

---

## 4) Main Folders

- Input photos: `data/Magic the gathering Iphone`
- Sorted output: `data/sorted_phone_dataset`
- Script for one path: `scripts/bin_from_path.py`
- Core code: `src/`

---

## 5) If Something Fails

- Check image is clear (name line and bottom text are visible)
- Make sure Vision key file exists at `credentials/google-vision-key.json`
- Make sure internet is available for Scryfall requests

---

## 6) Notes

- Different printings of the same card can be selected (set code can differ).
- Bin result is still correct for sorting workflow.
