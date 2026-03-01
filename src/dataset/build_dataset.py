"""
Build controlled dataset from Scryfall for testing and evaluation.

We need a known set of card images with ground-truth metadata to:
- Measure OCR accuracy (did we parse the right name/set/number?)
- Test the full pipeline (OCR -> parse -> Scryfall -> sort)

This script downloads images from Scryfall into 4 groups: lands, creatures,
artifacts, multicolor. Each group has `per_group` images. Metadata (name,
set, collector number, etc.) is written to metadata.jsonl so we know
what each image "should" be identified as.
"""

import json
from pathlib import Path
from typing import Optional

from src.services.scryfall_client import ScryfallClient

GROUPS = [
    ("lands", "type:land"),
    ("creatures", "type:creature -type:land"),
    ("artifacts", "type:artifact -type:land"),
    ("multicolor", "is:multicolor -type:land"),
]


def _get_image_url(card: dict, face_index: Optional[int] = None) -> Optional[str]:
    """
    Get large image URL. For double-faced cards (DFC), use card_faces[face_index]
    since each face has its own image. Single-face cards use image_uris directly.
    """
    if face_index is not None:
        faces = card.get("card_faces") or []
        if face_index < len(faces):
            uris = faces[face_index].get("image_uris") or {}
            return uris.get("large")
    uris = card.get("image_uris") or {}
    return uris.get("large")


def _iter_card_images(card: dict) -> list[tuple[str, str]]:
    """Yield (scryfall_id_suffix, image_url) for each face. Suffix is '' or '_face0', '_face1'."""
    card_id = card.get("id", "")
    faces = card.get("card_faces")

    if not faces:
        url = _get_image_url(card)
        if url:
            return [(card_id, url)]
        return []

    result = []
    for i, face in enumerate(faces):
        uris = face.get("image_uris") or {}
        url = uris.get("large")
        if url:
            suffix = f"{card_id}_face{i}" if len(faces) > 1 else card_id
            result.append((suffix, url))
    return result if result else [(card_id, _get_image_url(card) or "")]


def build_dataset(
    name: str,
    per_group: int = 50,
    out_dir: Path = Path("data/datasets"),
    unique: str = "prints",
) -> Path:
    """
    Build dataset with 4 groups. Download images, write metadata.jsonl.

    unique="prints" means we get different printings of the same card (e.g.
    Lightning Bolt from M10 and M21). unique="cards" means one per card name.
    Returns path to dataset root (e.g. data/datasets/baseline_v1).
    """
    dataset_root = out_dir / name
    images_dir = dataset_root / "images"
    dataset_root.mkdir(parents=True, exist_ok=True)

    client = ScryfallClient()
    seen_ids: set[str] = set()
    metadata_records: list[dict] = []

    for group_slug, query in GROUPS:
        group_images = images_dir / group_slug
        group_images.mkdir(parents=True, exist_ok=True)
        count = 0

        for card in client.search_cards(query, unique=unique):
            if count >= per_group:
                break

            card_id = card.get("id", "")
            if card_id in seen_ids:
                continue

            for suffix, image_url in _iter_card_images(card):
                if not image_url:
                    continue
                if count >= per_group:
                    break

                # Use suffix as filename base (card_id or card_id_face0)
                filename = f"{suffix}.png"
                image_path = group_images / filename
                rel_image_path = f"images/{group_slug}/{filename}"

                client.download_image(image_url, image_path)

                expected_lookup = {}
                if card.get("set") and card.get("collector_number"):
                    expected_lookup["set"] = card["set"]
                    expected_lookup["collector_number"] = str(card["collector_number"])
                else:
                    expected_lookup["name"] = card.get("name", "")

                record = {
                    "dataset_name": name,
                    "group": group_slug,
                    "scryfall_id": card_id,
                    "name": card.get("name", ""),
                    "set": card.get("set", ""),
                    "collector_number": str(card.get("collector_number", "")),
                    "lang": card.get("lang", "en"),
                    "layout": card.get("layout", ""),
                    "image_path": rel_image_path,
                    "image_url": image_url,
                    "type_line": card.get("type_line", ""),
                    "colors": card.get("colors") or [],
                    "color_identity": card.get("color_identity") or [],
                    "mana_value": float(card.get("cmc", 0)),
                    "rarity": card.get("rarity", "common"),
                    "expected_lookup": expected_lookup,
                }
                metadata_records.append(record)
                count += 1

            seen_ids.add(card_id)

    metadata_path = dataset_root / "metadata.jsonl"
    with open(metadata_path, "w", encoding="utf-8") as f:
        for rec in metadata_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return dataset_root
