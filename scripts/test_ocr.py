#!/usr/bin/env python3
"""
Run OCR on a single image and print the raw output.

Useful for quick testing: point at a card image, see what Vision extracts.
Also detects card border color (for fun) and opens the image in your
default viewer so you can compare.

Usage:
  python scripts/test_ocr.py                    # Uses default: first failure image
  python scripts/test_ocr.py path/to/card.png  # Your own image
"""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from src.services.vision_ocr import VisionOCR

# MTG border color reference (R, G, B) - approximate
MTG_COLORS = {
    "W": (248, 250, 255),   # White
    "U": (0, 85, 165),      # Blue
    "B": (45, 45, 45),      # Black
    "R": (210, 50, 50),     # Red
    "G": (0, 130, 70),      # Green
    "C": (220, 220, 215),   # Colorless / light gray (lands, artifacts)
}


def _luminance(rgb: tuple[int, int, int]) -> int:
    """Simple luminance: R+G+B. Used to find the lightest band (card border)."""
    return sum(rgb)


def _color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Euclidean distance in RGB space. Used to match border to nearest MTG color."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def detect_border_color(img_path: Path) -> str:
    """
    Sample pixel colors from card edges, pick lightest band (the border),
    return nearest MTG color (W/U/B/R/G/C). MTG cards have colored borders.
    """
    try:
        img = Image.open(img_path).convert("RGB")
    except Exception:
        return "unknown"

    w, h = img.size
    size = min(w, h)

    # Sample from 4 bands at 3%, 6%, 10%, 15% from the edge
    bands = []
    for pct in (0.03, 0.06, 0.10, 0.15):
        margin = max(2, int(size * pct))
        samples = []

        # Corners
        for x, y in [
            (margin, margin),
            (w - 1 - margin, margin),
            (margin, h - 1 - margin),
            (w - 1 - margin, h - 1 - margin),
        ]:
            samples.append(img.getpixel((x, y)))

        # Midpoints of each edge
        samples.append(img.getpixel((w // 2, margin)))
        samples.append(img.getpixel((w // 2, h - 1 - margin)))
        samples.append(img.getpixel((margin, h // 2)))
        samples.append(img.getpixel((w - 1 - margin, h // 2)))

        r = sum(s[0] for s in samples) // len(samples)
        g = sum(s[1] for s in samples) // len(samples)
        b = sum(s[2] for s in samples) // len(samples)
        avg = (r, g, b)
        bands.append((avg, _luminance(avg)))

    # Pick the band with highest luminance (the light card border, not dark outer frame)
    bands.sort(key=lambda x: -x[1])
    best_color = bands[0][0]

    # Find nearest MTG color
    best = min(MTG_COLORS.items(), key=lambda x: _color_distance(best_color, x[1]))
    return best[0]


def main():
    if len(sys.argv) < 2:
        # Default: first failure image
        img = Path("data/datasets/baseline_v1/images/lands/2e6c0b8d-c7a1-46aa-ae70-6b86c02315dc.png")
    else:
        img = Path(sys.argv[1])

    if not img.exists():
        print(f"Image not found: {img}")
        return 1

    img = img.resolve()
    print("=" * 60)
    print(f"OCR'ing: {img}")
    print(f"Filename: {img.name}")
    print("=" * 60)
    # Open image in default viewer so you can see what's being OCR'd
    try:
        if sys.platform == "win32":
            os.startfile(str(img))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(img)], check=False)
        else:
            subprocess.run(["xdg-open", str(img)], check=False)
    except Exception:
        pass
    border_color = detect_border_color(img)
    print(f"\n--- OCR output ---")
    ocr = VisionOCR(use_document=True)
    text = ocr.extract_text(img.read_bytes())
    print(text)
    print("--- end ---")
    print(f"\nDetected border color: {border_color}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
