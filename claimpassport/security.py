"""Passwords, tokens, role permissions and PII masking."""
import datetime as dt
import hashlib
import hmac
import os
import re

import jwt

PBKDF2_ITERS = int(os.environ.get("CP_PBKDF2_ITERS", "120000"))   # tests lower this for speed
ROLES = ("creator", "reviewer", "manager", "admin")

# What each role may do. Keep this table small and readable: it is the heart of "human control".
PERMS = {
    "create_content": set(ROLES),
    "decide": set(ROLES),                              # accept / edit a suggestion
    "override": {"reviewer", "manager", "admin"},      # reject a locked or high-risk finding
    "approve": {"reviewer", "manager", "admin"},
    "approve_locked": {"reviewer", "admin"},           # legal-style claims need a reviewer
    "publish": {"manager", "admin"},
    "vault_edit": {"manager", "admin"},
    "watcher": {"manager", "admin"},
    "audit": {"manager", "admin"},
    "users": {"manager", "admin"},
    "users_edit": {"admin"},
    "insights": {"reviewer", "manager", "admin"},
    "settings": {"manager", "admin"},               # hybrid switch, scheduler, test alerts
    "integrations": {"admin"},                      # Slack and webhook addresses (secrets)
}


def can(role, action):
    return role in PERMS.get(action, set())


def hash_password(password, salt=None, iters=None):
    iters = iters or PBKDF2_ITERS
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iters).hex()
    return f"pbkdf2${iters}${salt}${digest}"


def verify_password(password, stored):
    try:
        _, iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc, digest)


def make_token(user, secret, hours=12):
    payload = {"sub": str(user["id"]), "role": user["role"],
               "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)}
    return jwt.encode(payload, secret, algorithm="HS256")


def read_token(token, secret):
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ---- PII masking: used before any text is sent to an external AI service ----
_PII = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("AADHAAR", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")),
]


def mask_pii(text):
    """Return (masked_text, number_of_items_masked)."""
    count = 0
    for label, rx in _PII:
        text, n = rx.subn(f"[{label}]", text)
        count += n
    return text, count
