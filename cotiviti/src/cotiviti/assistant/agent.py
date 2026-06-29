import time
from typing import Optional, TypedDict

import pandas as pd
import streamlit as st
from langgraph.graph import StateGraph, START, END

from . import config, prompts
from .database import run_sql
from .guardrails import classify_intent, is_safe_select, screen_input, _OFF_TOPIC_MSG
from .keywords import extract_keywords
from .llm import answer_from_results, check_sql, describe_capabilities, generate_sql, groq_client
from .retrieval import retrieve_relevant_columns


# ── Stage 1: conversational contextualization ─────────────────────────────────
def contextualize(question: str, history: list[dict] | None = None) -> str:
    """Resolve a (possibly follow-up) message into a standalone question.

    First turn (no history) → return the message unchanged (no LLM call), so clear
    questions are never mangled. With history, an LLM rewrites follow-ups using the
    conversation; on any error it falls back to the raw message.
    """
    history = history or []
    if not history:
        return question
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    try:
        resp = groq_client().chat.completions.create(
            model=config.MODEL, max_tokens=120, temperature=0,
            messages=[{"role": "user",
                       "content": prompts.CONTEXTUALIZE_QUESTION.format(history=convo, question=question)}],
        )
        return (resp.choices[0].message.content or "").strip() or question
    except Exception:
        return question  # non-fatal: treat the raw message as standalone


# ── Stage 3: LangGraph text-to-SQL pipeline ───────────────────────────────────
class SQLAgentState(TypedDict):
    message: str                       # the user's latest message (raw) — what we answer
    history: list[dict]                # recent conversation turns, for the model to read
    retrieval_query: str               # standalone phrasing, used only for column retrieval
    keywords: list[str]                # distilled codes / clinical terms
    columns: list[str]                 # ChromaDB-retrieved relevant columns
    sql: Optional[str]                 # current candidate query
    sql_history: list[str]             # every query tried (for transparency/debug)
    result_df: Optional[pd.DataFrame]  # rows from a successful execution
    rows: int                          # row count of the result
    error_feedback: Optional[str]      # last execution/validation error (drives retry)
    loop_count: int                    # number of generator passes so far
    answer: Optional[str]              # final natural-language answer


def _extract_node(state: SQLAgentState) -> dict:
    """NODE 1 — pull the important keywords (from the standalone retrieval phrasing)."""
    return {"keywords": extract_keywords(state["retrieval_query"]), "loop_count": 0, "error_feedback": None}


def _retrieve_node(state: SQLAgentState) -> dict:
    """NODE 2 — retrieve the most relevant columns from ChromaDB (query + keywords)."""
    query = state["retrieval_query"]
    if state.get("keywords"):
        query = f"{query} {' '.join(state['keywords'])}"
    return {"columns": retrieve_relevant_columns(query)}


def _generate_node(state: SQLAgentState) -> dict:
    """NODE 3 — generate (or regenerate) SQL for the latest message, IN CONVERSATION.

    The generator receives the recent turns plus the raw latest message, so it
    resolves follow-ups itself instead of relying on a lossy rewritten question.
    """
    sql = generate_sql(state["message"], state["columns"],
                        history=state.get("history"), feedback=state.get("error_feedback"))
    sql = check_sql(sql)  # LangChain QuerySQLCheckerTool refine pass
    return {
        "sql": sql,
        "sql_history": state.get("sql_history", []) + [sql],
        "loop_count": state.get("loop_count", 0) + 1,
    }


def _execute_node(state: SQLAgentState) -> dict:
    """NODE 4 — guardrail-validate then execute; capture any error for the retry loop."""
    sql = state.get("sql") or ""
    if not is_safe_select(sql):
        return {"result_df": None,
                "error_feedback": "Query was rejected by the safety guardrail "
                                  "(must be a single read-only SELECT with no PII columns)."}
    try:
        result_df = run_sql(sql)
        return {"result_df": result_df, "rows": len(result_df), "error_feedback": None}
    except Exception as e:
        return {"result_df": None, "error_feedback": f"{type(e).__name__}: {e}"}


def _route_after_execute(state: SQLAgentState) -> str:
    """Conditional edge — succeed → synthesize; else retry until the budget runs out."""
    if state.get("error_feedback") is None and state.get("result_df") is not None:
        return "synthesize"
    if state.get("loop_count", 0) < config.MAX_SQL_ATTEMPTS:
        return "regenerate"
    return "synthesize"  # exhausted retries → synthesizer emits a graceful fallback


def _synthesize_node(state: SQLAgentState) -> dict:
    """NODE 5 — turn the result rows into a plain-language answer (PII-masked upstream)."""
    if state.get("result_df") is not None and state.get("error_feedback") is None:
        answer = answer_from_results(state["message"], state["sql"], state["result_df"],
                                     history=state.get("history"))
    else:
        answer = ("⚠️ I couldn't build a working query for that after several attempts. "
                  "Please try rephrasing your question.")
    return {"answer": answer}


@st.cache_resource(show_spinner=False)
def get_sql_agent():
    """Compile the LangGraph pipeline once and reuse it across reruns."""
    g = StateGraph(SQLAgentState)
    g.add_node("extractor", _extract_node)
    g.add_node("retriever", _retrieve_node)
    g.add_node("generator", _generate_node)
    g.add_node("executor", _execute_node)
    g.add_node("synthesizer", _synthesize_node)

    g.add_edge(START, "extractor")
    g.add_edge("extractor", "retriever")
    g.add_edge("retriever", "generator")
    g.add_edge("generator", "executor")
    g.add_conditional_edges(
        "executor",
        _route_after_execute,
        {"regenerate": "generator", "synthesize": "synthesizer"},
    )
    g.add_edge("synthesizer", END)
    return g.compile()


def _result(status: str, answer: str, raw: str, standalone: str, latency: float,
            final: Optional[dict] = None) -> dict:
    """Assemble the uniform return dict the UI/tests consume."""
    final = final or {}
    return {
        "status": status,                       # "ok" | "blocked"
        "answer": answer,
        "raw_question": raw,
        "standalone": standalone,
        "latency": latency,
        "sql": final.get("sql") or "",
        "columns": final.get("columns", []),
        "rows": final.get("rows", 0),
        "keywords": final.get("keywords", []),
        "loops": final.get("loop_count", 0),
    }


def answer_question(question: str, history: list[dict] | None = None) -> dict:
    """Contextualize → guard → run the pipeline; return uniform display fields.

    ``status`` is "ok" for a normal answer or "blocked" for a guardrail rejection,
    so the caller can render each appropriately.
    """
    started = time.perf_counter()

    # 1. A standalone phrasing (used only for column retrieval + the topic guard).
    standalone = contextualize(question, history)
    raw_ok, raw_reason = screen_input(question)
    std_ok, std_reason = screen_input(standalone)
    if not raw_ok or not std_ok:
        return _result("blocked", raw_reason or std_reason, question, standalone,
                       time.perf_counter() - started)

    intent = classify_intent(standalone, history=history)
    if intent == "off_topic":
        return _result("blocked", _OFF_TOPIC_MSG, question, standalone,
                       time.perf_counter() - started)
    if intent == "meta":
        answer = describe_capabilities(question, history)
        return _result("ok", answer, question, standalone, time.perf_counter() - started)

    final = get_sql_agent().invoke({
        "message": question,
        "history": history or [],
        "retrieval_query": standalone,
        "keywords": [], "columns": [], "sql": None, "sql_history": [],
        "result_df": None, "rows": 0, "error_feedback": None, "loop_count": 0, "answer": None,
    })
    return _result("ok", final.get("answer") or "", question, standalone,
                   time.perf_counter() - started, final)
