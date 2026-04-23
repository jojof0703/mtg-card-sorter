"""
Project config: credentials paths, etc.

Central place for configuration. Right now we only have the path to
Google Vision credentials. Putting it here makes it easy to change
(e.g. for different environments) without hunting through the codebase.
"""

from pathlib import Path

# Project root (parent of src/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default credentials path: credentials/google-vision-key.json
DEFAULT_CREDENTIALS_PATH = _PROJECT_ROOT / "credentials" / "google-vision-key.json"


def get_vision_credentials_path() -> Path:
    """
    Path to Google Vision service account JSON.

    Default: credentials/google-vision-key.json in the project root.
    You get this file from Google Cloud Console when you enable the Vision API
    and create a service account. Never commit it to git (it contains secrets).
    """
    return DEFAULT_CREDENTIALS_PATH

# Serial communication settings for Arduino
SERIAL_PORT = "COM3"  # Double-check this in Arduino IDE (Tools > Port)
SERIAL_BAUD = 9600
