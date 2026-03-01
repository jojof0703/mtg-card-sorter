"""
Google Cloud Vision OCR for MTG card images.

OCR = Optical Character Recognition. We send an image to Google's Vision API,
and it returns the text it "sees" in the image. For a card photo, that's
typically the card name, type line, rules text, and (at the bottom) the
collector number and set code.

Requires: Google Cloud credentials in credentials/google-vision-key.json.
The Vision API is a paid service (with free tier). We use DOCUMENT_TEXT_DETECTION
which is better for structured text (like cards) than plain TEXT_DETECTION.
"""

from pathlib import Path
from typing import Optional

from google.cloud import vision
from google.oauth2 import service_account

from src.config import get_vision_credentials_path


def _get_client() -> vision.ImageAnnotatorClient:
    """
    Create Vision client. Uses service account JSON from credentials/ if present,
    otherwise falls back to default credentials (e.g. GOOGLE_APPLICATION_CREDENTIALS).
    """
    creds_path = get_vision_credentials_path()
    if creds_path.exists():
        creds = service_account.Credentials.from_service_account_file(str(creds_path))
        return vision.ImageAnnotatorClient(credentials=creds)
    return vision.ImageAnnotatorClient()


def extract_text_from_image(image_path: str | Path) -> Optional[str]:
    """
    Run DOCUMENT_TEXT_DETECTION on a local image file.

    Reads the file, sends it to Vision API, returns the extracted text as
    a single string (with newlines). Raises on API errors or missing file.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    with open(path, "rb") as f:
        content = f.read()

    image = vision.Image(content=content)
    client = _get_client()
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    if response.full_text_annotation:
        return response.full_text_annotation.text.strip()
    return None


def extract_text_from_bytes(data: bytes) -> Optional[str]:
    """Run DOCUMENT_TEXT_DETECTION on raw image bytes (e.g. from an upload)."""
    image = vision.Image(content=data)
    client = _get_client()
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    if response.full_text_annotation:
        return response.full_text_annotation.text.strip()
    return None
