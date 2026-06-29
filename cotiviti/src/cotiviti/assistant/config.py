import os
from pathlib import Path

import streamlit as st
import toml


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.toml"
DB_PATH = BASE_DIR / "claims.db"
CHROMA_PATH = BASE_DIR / "chroma_db"

TABLE = "claims"
SAFE_TABLE = "claims_safe"            # derived table holding only non-PII columns
BOOL_COLS = ["OverpaymentFlag", "FWAFlag"]  # round-trip through SQLite as 0/1

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 1024
TEMPERATURE = 0.3

SCHEMA_COLLECTION = "claims_schema"
TOP_K_COLUMNS = 8                     # most-relevant columns fed to the SQL generator

MAX_SQL_ATTEMPTS = 3                 

PLACEHOLDER_VALUES = {"PASTE_YOUR_GROQ_KEY_HERE", "", "YOUR_KEY_HERE"}


def is_real_key(key: str) -> bool:
    """True only for a non-placeholder Groq key (Groq keys start with ``gsk_``)."""
    return bool(key) and key not in PLACEHOLDER_VALUES and key.startswith("gsk_")


def load_api_key() -> tuple[str | None, str | None]:
    """Resolve the Groq API key from the first source that provides one.

    Priority: ``config.toml`` → Streamlit secrets → ``GROQ_API_KEY`` env var.
    Returns ``(key, source_label)`` or ``(None, None)``.
    """
    if CONFIG_PATH.exists():
        try:
            key = toml.load(CONFIG_PATH).get("groq", {}).get("api_key", "")
            if is_real_key(key):
                return key, "config.toml"
        except Exception:
            pass

    try:
        key = st.secrets["groq"]["api_key"]
        if is_real_key(key):
            return key, ".streamlit/secrets.toml"
    except Exception:
        pass

    key = os.environ.get("GROQ_API_KEY", "")
    if is_real_key(key):
        return key, "environment variable"

    return None, None


API_KEY, KEY_SOURCE = load_api_key()