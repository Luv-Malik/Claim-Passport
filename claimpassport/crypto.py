"""Encryption at rest for uploaded files and saved secrets (AES-256-GCM).

The key comes from CP_ENCRYPTION_KEY. If that is not set, a key is derived from CP_SECRET_KEY so files are
still encrypted, but a real install should set its own key and keep it safe: lose it and the files cannot be read.
Files written before encryption was added (no header) are still readable."""
import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"CPE1"
SECRET_PREFIX = "enc:"


def _key(cfg):
    material = (cfg.get("ENCRYPTION_KEY") or cfg.get("SECRET_KEY") or "").encode()
    info = b"claimpassport-files-v1" if cfg.get("ENCRYPTION_KEY") else b"claimpassport-files-derived-v1"
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(material)


def encrypt(cfg, data):
    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(_key(cfg)).encrypt(nonce, bytes(data), MAGIC)


def is_encrypted(blob):
    return bytes(blob[:4]) == MAGIC


def decrypt(cfg, blob):
    """Return the original bytes. Data without the header is returned as it is (older plaintext files)."""
    if not is_encrypted(blob):
        return bytes(blob)
    nonce, body = blob[4:16], blob[16:]
    return AESGCM(_key(cfg)).decrypt(nonce, body, MAGIC)


def seal_text(cfg, text):
    """Encrypt a short secret (for example a Slack webhook address) into a storable string."""
    return SECRET_PREFIX + base64.urlsafe_b64encode(encrypt(cfg, (text or "").encode())).decode()


def open_text(cfg, stored):
    if not stored:
        return ""
    if not stored.startswith(SECRET_PREFIX):
        return stored
    return decrypt(cfg, base64.urlsafe_b64decode(stored[len(SECRET_PREFIX):].encode())).decode()
