"""Where uploaded files live. They are stored encrypted, under a random name."""
import re
import uuid
from pathlib import Path

from . import crypto
from .errors import AppError

_NAME = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{1,6}$")


def save_upload(cfg, filename, data):
    folder = Path(cfg["UPLOAD_DIR"])
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()[:7]}"
    (folder / stored).write_bytes(crypto.encrypt(cfg, data))
    return stored


def load_upload(cfg, stored):
    """The original bytes of an upload, or None if it is not there."""
    if not stored or not _NAME.match(stored):
        return None
    path = Path(cfg["UPLOAD_DIR"]) / stored
    if not path.is_file():
        return None
    try:
        return crypto.decrypt(cfg, path.read_bytes())
    except Exception:
        raise AppError("The stored file could not be decrypted. Check CP_ENCRYPTION_KEY.", 500)
