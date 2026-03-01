"""
Google Cloud Vision OCR wrapper with caching.

Used by the dataset harness (ocr_eval) rather than the main pipeline.
Supports both DOCUMENT_TEXT_DETECTION (better for cards) and TEXT_DETECTION.
Caches OCR results to disk (one .txt file per image) so we don't re-call
the API when re-running evaluation. Cache key = image stem (from path).
"""

from pathlib import Path

from google.cloud import vision
from google.oauth2 import service_account

from src.config import get_vision_credentials_path


class VisionOCR:
    """
    Vision OCR with optional DOCUMENT_TEXT_DETECTION and caching.

    use_document=True uses DOCUMENT_TEXT_DETECTION (better for structured
    text like cards). use_document=False uses TEXT_DETECTION (simpler).
    """

    def __init__(self, use_document: bool = True):
        creds_path = get_vision_credentials_path()
        if creds_path.exists():
            creds = service_account.Credentials.from_service_account_file(str(creds_path))
            self._client = vision.ImageAnnotatorClient(credentials=creds)
        else:
            self._client = vision.ImageAnnotatorClient()
        self._use_document = use_document

    def extract_text(self, image_bytes: bytes) -> str:
        """
        Run OCR on image bytes. Returns extracted text as string.
        Uses DOCUMENT_TEXT_DETECTION or TEXT_DETECTION based on init.
        """
        image = vision.Image(content=image_bytes)
        if self._use_document:
            response = self._client.document_text_detection(image=image)
        else:
            response = self._client.text_detection(image=image)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        if self._use_document and response.full_text_annotation:
            return response.full_text_annotation.text.strip()
        if response.text_annotations:
            return response.text_annotations[0].description.strip()
        return ""

    def extract_text_cached(
        self,
        image_bytes: bytes,
        cache_path: Path,
    ) -> str:
        """
        Run OCR, using cache if present.

        If cache_path exists, read and return its contents (no API call).
        Otherwise run OCR, write to cache_path, return text.
        """
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8").strip()

        text = self.extract_text(image_bytes)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
        return text
