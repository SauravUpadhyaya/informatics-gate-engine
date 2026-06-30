import streamlit as st

from . import config, prompts
from .llm import groq_client


@st.cache_resource(show_spinner=False)
def load_stop_words() -> set:
    """Return NLTK's English stop-word set, fetching the corpus once if needed.

    If the corpus isn't present, download it over a certifi CA bundle (works around
    macOS missing-cert errors), then load it.
    """
    import nltk
    from nltk.corpus import stopwords
    try:
        return set(stopwords.words("english"))
    except LookupError:
        try:
            import ssl
            import certifi
            ssl._create_default_https_context = lambda *a, **k: ssl.create_default_context(
                cafile=certifi.where()
            )
        except Exception:
            pass
        nltk.download("stopwords", quiet=True)
        return set(stopwords.words("english"))


STOP_WORDS = load_stop_words()


def extract_keywords(question: str) -> list[str]:
    """Return the important keywords from a question (stop words removed).

    Non-fatal: returns ``[]`` on any error, since retrieval still works off the
    raw question downstream.
    """
    try:
        resp = groq_client().chat.completions.create(
            model=config.MODEL, max_tokens=120, temperature=0,
            messages=[{"role": "user", "content": prompts.KEYWORD_EXTRACTION.format(question=question)}],
        )
        text = resp.choices[0].message.content or ""
        keywords = [kw.strip() for kw in text.split(",") if kw.strip()]
        # Deterministic backstop: drop any single-token stop words the model left in.
        return [kw for kw in keywords if kw.lower() not in STOP_WORDS]
    except Exception:
        return []