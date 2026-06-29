"""Cotiviti Health Plan Ops Assistant — application package.

Layered modules (each depends only on those above it):

    config      paths, model settings, table names, API key
    schema      queryable column docs + protected PII columns
    database    synthetic data + SQLite store (seed, load, run_sql, KPIs)
    retrieval   ChromaDB schema vector store (relevant-column retrieval)
    pii         mask DataFrame PII + scrub PII from model output
    llm         Groq client + text-to-SQL steps (generate / check / answer)
    guardrails  is_safe_select + input topic/safety guard
    keywords    NLTK stop words + LLM keyword extraction
    agent       LangGraph self-correcting pipeline (answer_question)
    ui          Streamlit view layer (header, sidebar, dashboard, chat)

The Streamlit page (``pages/app2.py``) wires these together.
"""

from .agent import answer_question

__all__ = ["answer_question"]