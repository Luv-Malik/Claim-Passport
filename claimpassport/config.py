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
        # Database: a PostgreSQL address (CP_DATABASE_URL) wins over the SQLite file above.
        "DATABASE_URL": env("CP_DATABASE_URL", env("DATABASE_URL", "")),
        # Uploaded files and saved secrets are encrypted. Set your own key for a real install.
        "ENCRYPTION_KEY": env("CP_ENCRYPTION_KEY", ""),
        # Hybrid verification (meaning-level search + cited AI judge) default; admins can switch it in Settings.
        "HYBRID": env("CP_HYBRID", "0") == "1",
        "EMBEDDING_MODEL": env("CP_EMBEDDING_MODEL", ""),
        # Alerts. Email needs an SMTP server; Slack and webhook addresses are set in Settings (admin) or here.
        "PUBLIC_URL": env("CP_PUBLIC_URL", "http://127.0.0.1:5000").rstrip("/"),
        "SMTP_HOST": env("CP_SMTP_HOST", ""),
        "SMTP_PORT": int(env("CP_SMTP_PORT", "587")),
        "SMTP_USER": env("CP_SMTP_USER", ""),
        "SMTP_PASSWORD": env("CP_SMTP_PASSWORD", ""),
        "SMTP_FROM": env("CP_SMTP_FROM", "claim-passport@localhost"),
        "SMTP_TLS": env("CP_SMTP_TLS", "starttls"),          # starttls | ssl | none
        "SLACK_WEBHOOK_URL": env("CP_SLACK_WEBHOOK_URL", ""),
        "WEBHOOK_URL": env("CP_WEBHOOK_URL", ""),
        "WEBHOOK_SECRET": env("CP_WEBHOOK_SECRET", ""),
        # Scheduler: scans for expiring and changed facts on its own. Use ONE worker (or set 0 on the others).
        "SCHEDULER": env("CP_SCHEDULER", "1") == "1",
        "SCAN_INTERVAL_HOURS": float(env("CP_SCAN_INTERVAL_HOURS", "24")),
        "DIGEST_WEEKDAY": int(env("CP_DIGEST_WEEKDAY", "0")),   # 0 = Monday
    }
    if overrides:
        cfg.update(overrides)
    return cfg
