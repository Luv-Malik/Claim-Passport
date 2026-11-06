"""Configuration. Everything can be changed with environment variables (see .env.example)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_config(overrides=None):
    env = os.environ.get
    cfg = {
        "DB_PATH": env("CP_DB_PATH", str(BASE_DIR / "data" / "claimpassport.db")),
        "UPLOAD_DIR": env("CP_UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")),
        "SECRET_KEY": env("CP_SECRET_KEY", "dev-secret-change-me-before-real-use-0123456789"),
        "TOKEN_HOURS": int(env("CP_TOKEN_HOURS", "12")),
        # Optional LLM helper (suggestions only). Rules engine works fully without it.
        "ANTHROPIC_API_KEY": env("ANTHROPIC_API_KEY", ""),
        "USE_LLM": env("CP_USE_LLM", "1") == "1",
        "LLM_MODEL": env("CP_LLM_MODEL", "claude-sonnet-5-5"),
        "EXPIRY_WARN_DAYS": int(env("CP_EXPIRY_WARN_DAYS", "14")),
        "MAX_UPLOAD_MB": int(env("CP_MAX_UPLOAD_MB", "10")),
        "SEED_DEMO": env("CP_SEED_DEMO", "1") == "1",
    }
    if overrides:
        cfg.update(overrides)
    return cfg
