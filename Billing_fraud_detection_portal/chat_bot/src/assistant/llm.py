import re
import sqlite3

import pandas as pd
import streamlit as st
from groq import Groq
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_groq import ChatGroq

from . import config, prompts
from .database import init_db
from .pii import mask_pii
from .schema import COLUMN_DOCS


def groq_client() -> Groq:
    """Return a Groq client bound to the configured API key."""
    return Groq(api_key=config.API_KEY)


def _strip_sql(text: str) -> str:
    """Pull a bare SQL statement out of a model response (drop ``` fences/prose)."""
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE).strip()
    m = re.search(r"\b(SELECT|WITH)\b", text, flags=re.IGNORECASE)
    if m:
        text = text[m.start():]
    return text.rstrip().rstrip(";").strip()


def _history_messages(history: list[dict] | None, limit: int = 6) -> list[dict]:
    """Recent user/assistant turns as chat messages, so the model reads the real
    conversation and resolves follow-ups itself (no rule-based rewriting)."""
    msgs = []
    for turn in (history or [])[-limit:]:
        role, content = turn.get("role"), turn.get("content")
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content[:600]})
    return msgs


def generate_sql(message: str, columns: list[str], history: list[dict] | None = None,
                 feedback: str | None = None) -> str:
    """Ask the LLM to write a SQLite SELECT for the user's latest message.

    The recent conversation is passed as chat turns so the model understands
    follow-ups ("lowest one", "what about Medicare") natively, in context.
    ``feedback`` is the error from a previous attempt, injected for self-correction.
    """
    schema_lines = "\n".join(f"  - {c} ({COLUMN_DOCS[c]})" for c in columns)
    system = prompts.SQL_GENERATION_SYSTEM.format(table=config.TABLE, schema_lines=schema_lines)
    if feedback:
        system += prompts.SQL_RETRY_SUFFIX.format(feedback=feedback)
    messages = [{"role": "system", "content": system}]
    messages += _history_messages(history)
    messages.append({"role": "user", "content": message})
    resp = groq_client().chat.completions.create(
        model=config.MODEL,
        max_tokens=400,
        temperature=0,  # deterministic SQL
        messages=messages,
    )
    return _strip_sql(resp.choices[0].message.content or "")


@st.cache_resource(show_spinner=False)
def get_sql_tools() -> dict:
    """Build a LangChain ``SQLDatabaseToolkit`` over a PII-safe table; tools by name.

    A derived table (``claims_safe``) holds only the non-PII columns, and the
    ``SQLDatabase`` is restricted to it — so none of the toolkit's tools can see
    the protected PII columns. (A real table is used rather than a view because
    the SQLite SQLAlchemy dialect doesn't support view reflection.)
    """
    init_db()
    safe_cols = ", ".join(f'"{c}"' for c in COLUMN_DOCS)
    conn = sqlite3.connect(config.DB_PATH)
    try:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {config.SAFE_TABLE} AS SELECT {safe_cols} FROM {config.TABLE}"
        )
        conn.commit()
    finally:
        conn.close()
    db = SQLDatabase.from_uri(f"sqlite:///{config.DB_PATH}", include_tables=[config.SAFE_TABLE])
    llm = ChatGroq(model=config.MODEL, api_key=config.API_KEY, temperature=0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    return {tool.name: tool for tool in toolkit.get_tools()}


def check_sql(sql: str) -> str:
    """Refine a query via LangChain's QuerySQLCheckerTool before execution.

    A refine pass (not a validator) — the hard safety gate ``is_safe_select`` still
    runs afterwards. Falls back to the original SQL if the checker is unavailable.
    """
    try:
        checker = get_sql_tools().get("sql_db_query_checker")
        if checker is None:
            return sql
        refined = _strip_sql(checker.run(sql))
        return refined or sql
    except Exception:
        return sql  # never let the refine pass break the pipeline


def describe_capabilities(message: str, history: list[dict] | None = None) -> str:
    """Answer a META question (what am I / what data / how to use me).

    Grounded in the live ``COLUMN_DOCS`` schema so the description can't drift
    from what the dataset actually contains. No SQL is run — this is a scope/
    capability answer, routed here by ``classify_intent`` returning ``"meta"``.
    """
    schema_lines = "\n".join(f"  - {c}: {doc}" for c, doc in COLUMN_DOCS.items())
    system = prompts.CAPABILITIES_SYSTEM.format(schema_lines=schema_lines)
    messages = [{"role": "system", "content": system}]
    messages += _history_messages(history)
    messages.append({"role": "user", "content": message})
    resp = groq_client().chat.completions.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        temperature=config.TEMPERATURE,
        messages=messages,
    )
    return (resp.choices[0].message.content or "").strip()


def answer_from_results(message: str, sql: str, result_df: pd.DataFrame,
                        history: list[dict] | None = None) -> str:
    """Have the LLM turn the query results into a plain-language answer.

    The recent conversation is included so the answer is phrased in context. Rows
    are PII-masked before being sent to Groq, so even if a PII column ever reached
    this point it never leaves the box in the clear.
    """
    safe_df = mask_pii(result_df)
    preview = safe_df.head(50).to_string(index=False) if not safe_df.empty else "(no rows returned)"
    context = f"Question: {message}\n\nSQL executed:\n{sql}\n\nSQL result:\n{preview}"
    messages = [{"role": "system", "content": prompts.ANSWER_SYNTHESIS_SYSTEM}]
    messages += _history_messages(history)
    messages.append({"role": "user", "content": context})
    resp = groq_client().chat.completions.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        temperature=config.TEMPERATURE,
        messages=messages,
    )
    return (resp.choices[0].message.content or "").strip()