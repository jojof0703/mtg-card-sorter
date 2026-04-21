# `scripts` Folder Guide (Simple English)

This folder has helper scripts you run directly.

Current script:

- `bin_from_path.py`  
  Input: one image path or one folder path  
  Output: detected card + bin + cold timing (cache OFF)

Examples:

```bash
python scripts/bin_from_path.py "data/Magic the gathering Iphone/Screenshot 2026-04-13 185409.png" --mode type
python scripts/bin_from_path.py "data/Magic the gathering Iphone" --mode type
```
