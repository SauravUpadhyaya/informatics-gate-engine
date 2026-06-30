import re

from . import config, prompts
from .llm import groq_client
from .schema import PII_COLUMNS

# ── SQL safety gate ───────────────────────────────────────────────────────────
_FORBIDDEN_SQL = r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|PRAGMA|VACUUM)\b"


def is_safe_select(sql: str) -> bool:
    """Allow only a single read-only SELECT/WITH that touches no PII."""
    if ";" in sql.strip().rstrip(";"):
        return False  # no multiple statements
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, flags=re.IGNORECASE):
        return False
    if re.search(_FORBIDDEN_SQL, sql, flags=re.IGNORECASE) is not None:
        return False
    # Block "SELECT *" / "alias.*" — a wildcard would pull the protected PII columns.
    if re.search(r"select\s+(\w+\.)?\*", sql, flags=re.IGNORECASE):
        return False
    # Block any explicit reference to a PII column.
    if any(re.search(rf"\b{re.escape(col)}\b", sql, flags=re.IGNORECASE) for col in PII_COLUMNS):
        return False
    return True


# ── Input topic/safety guard ──────────────────────────────────────────────────
INJECTION_PATTERNS = [
    r"ignore (?:all |the )?(?:previous|above|prior|earlier) (?:instructions?|prompts?|rules?)",
    r"disregard (?:all |the )?(?:previous|above|prior|earlier)",
    r"forget (?:all |the |your )?(?:previous|above|prior|earlier|instructions?)",
    r"(?:reveal|show|print|repeat|leak) (?:me )?(?:your |the )?(?:system |hidden |initial )?(?:prompt|instructions?)",
    r"system prompt",
    r"\bjailbreak\b",
    r"\bDAN\b",
    r"developer mode",
    r"pretend (?:to be|you are|you're)",
    r"act as (?:if |though )",
    r"override (?:your |the )?(?:rules?|instructions?|guardrails?|restrictions?)",
    r"bypass (?:your |the )?(?:rules?|filters?|guardrails?|restrictions?)",
]
PII_REQUEST_PATTERNS = [
    r"\bssn\b", r"social security", r"\bemail\b", r"phone(?: number)?",
    r"home address", r"street address", r"date of birth", r"\bdob\b",
    r"member name", r"patient name", r"full name", r"member's name",
]

_OFF_TOPIC_MSG = ("⚠️ I can only help with questions about the claims dataset — payment "
                  "integrity, overpayments, FWA alerts, DRG codes, and claim status.")


def screen_input(question: str) -> tuple[bool, str]:
    """Deterministic first-pass screen. Returns ``(ok, reason)``."""
    low = question.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, low):
            return False, ("⚠️ That looks like an attempt to change how I work. I can only help "
                           "with questions about the claims dataset — payment integrity, "
                           "overpayments, FWA alerts, DRG codes, and claim status.")
    for pat in PII_REQUEST_PATTERNS:
        if re.search(pat, low):
            return False, ("⚠️ I can't share personal identifiers (names, SSNs, emails, phone "
                           "numbers, addresses, dates of birth). Ask about claims, overpayments, "
                           "FWA alerts, DRG codes, or payment integrity instead.")
    return True, ""


def classify_topic(question: str, history: list[dict] | None = None) -> tuple[bool, str]:
    """Lightweight LLM intent check that the question is on-topic. Fails open.

    The recent conversation is supplied so the classifier judges the latest
    message IN CONTEXT — a bare follow-up like "the highest one?" reads as
    off-topic alone but is clearly on-topic continuing a DRG/overpayment thread.
    This is what makes follow-ups survive the guard regardless of whether the
    upstream contextualization step managed to rewrite them.
    """
    try:
        resp = groq_client().chat.completions.create(
            model=config.MODEL,
            max_tokens=5,
            temperature=0,
            messages=[
                {"role": "system", "content": prompts.TOPIC_CLASSIFIER_SYSTEM},
                {"role": "user", "content": prompts.TOPIC_CLASSIFIER_USER.format(
                    history=_convo_str(history), question=question)},
            ],
        )
        verdict = (resp.choices[0].message.content or "").strip().upper()
        if verdict.startswith("BLOCK"):
            return False, _OFF_TOPIC_MSG
        return True, ""
    except Exception:
        return True, ""  # fail open: never block legitimate use on a classifier error


def _convo_str(history: list[dict] | None) -> str:
    """Render recent turns as 'role: content' lines for a classifier prompt."""
    return "\n".join(
        f"{m['role']}: {m['content']}"
        for m in (history or [])
        if m.get("role") in ("user", "assistant") and m.get("content")
    ) or "(no prior conversation)"


def classify_intent(question: str, history: list[dict] | None = None) -> str:
    """Route a message to one of ``"data"`` | ``"meta"`` | ``"off_topic"``.

    A context-aware LLM router so the assistant can answer questions about the
    DATA it serves *and* questions about ITSELF (capabilities / how to use it),
    while still blocking genuinely off-topic or unsafe input. Judged in context
    so follow-ups survive. Fails OPEN to ``"data"`` — the deterministic
    injection/PII screen (``screen_input``) is the hard safety gate, so a
    classifier error can never let an attack through.
    """
    try:
        resp = groq_client().chat.completions.create(
            model=config.MODEL,
            max_tokens=5,
            temperature=0,
            messages=[
                {"role": "system", "content": prompts.INTENT_CLASSIFIER_SYSTEM},
                {"role": "user", "content": prompts.TOPIC_CLASSIFIER_USER.format(
                    history=_convo_str(history), question=question)},
            ],
        )
        verdict = (resp.choices[0].message.content or "").strip().upper()
        if verdict.startswith("META"):
            return "meta"
        if verdict.startswith("OFF"):
            return "off_topic"
        return "data"
    except Exception:
        return "data"  # fail open: the deterministic screen already blocked attacks


def guard_input(question: str, history: list[dict] | None = None) -> tuple[bool, str]:
    """Full input guardrail: deterministic screen, then LLM topic classifier.

    ``history`` lets the topic classifier judge follow-ups in conversational
    context; the deterministic screen stays per-message (injection/PII never
    become acceptable because of context).
    """
    ok, reason = screen_input(question)
    if not ok:
        return ok, reason
    return classify_topic(question, history)