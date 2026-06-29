import re

import pandas as pd

from .schema import PII_COLUMNS


def _mask_value(col: str, value) -> str:
    """Redact a single PII value, keeping just enough to be recognizable."""
    s = str(value)
    if col == "SSN":
        return "***-**-****"  # fully redacted — never expose any SSN digits
    if col == "Email":
        name, _, domain = s.partition("@")
        return f"{name[:1]}***@{domain or '***'}"
    if col == "Phone":
        return f"***-***-{s[-4:]}" if len(s) >= 4 else "***-***-****"
    if col == "MemberName":
        parts = s.split()
        return " ".join(p[:1] + "***" for p in parts) if parts else "***"
    # DateOfBirth, StreetAddress, and any other identifier → fully redacted.
    return "[REDACTED]"


def mask_pii(data: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``data`` with any PII columns redacted (no-op if none)."""
    present = [c for c in data.columns if c in PII_COLUMNS]
    if not present:
        return data
    masked = data.copy()
    for col in present:
        masked[col] = masked[col].map(lambda v: _mask_value(col, v))
    return masked


# PII-shaped patterns to catch in free-text model output.
OUTPUT_PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "***-**-****"),                            # SSN
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[email redacted]"),                # email
    (re.compile(r"\b\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b"), "[phone redacted]"),   # phone
]


def scrub_output_pii(text: str) -> tuple[str, bool]:
    """Redact PII-looking substrings from model output.

    Returns ``(clean_text, found)`` where ``found`` is True if anything was
    redacted, so the caller can note that values were withheld.
    """
    clean = text
    found = False
    for pattern, repl in OUTPUT_PII_PATTERNS:
        clean, n = pattern.subn(repl, clean)
        if n:
            found = True
    return clean, found