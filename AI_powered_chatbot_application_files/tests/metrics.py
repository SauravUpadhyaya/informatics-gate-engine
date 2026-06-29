import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = PROJECT_ROOT / "src" / "cotiviti"
sys.path.insert(0, str(PKG_ROOT))


def _require_project_venv() -> None:
    """Turn the cryptic 'Unable to import numpy' into a clear interpreter hint."""
    try:
        import numpy  # noqa: F401
    except Exception:  # noqa: BLE001
        venv_py = PROJECT_ROOT / "venv" / "bin" / "python"
        sys.exit(
            "\n[interpreter error] numpy isn't importable under this Python:\n"
            f"    {sys.executable}\n\n"
            "You're almost certainly running a different interpreter than the project venv.\n"
            "Fix one of these ways:\n"
            f"  • Terminal:  {venv_py} {Path(__file__).relative_to(PROJECT_ROOT)}\n"
            "  • IDE: set the Python interpreter to that venv path "
            "(Settings → Project → Python Interpreter → Add Local → Existing).\n"
        )


_require_project_venv()

from assistant import config  # noqa: E402
from assistant.database import run_sql  # noqa: E402
from assistant.guardrails import is_safe_select  # noqa: E402
from assistant.llm import groq_client  # noqa: E402
from assistant.pii import mask_pii  # noqa: E402

# ── Golden set ────────────────────────────────────────────────────────────────
# expect_nonempty marks questions that MUST return rows (used for False Empty Rate).
GOLDEN = [
    {"q": "What is the total paid amount across all claims?", "expect_nonempty": True},
    {"q": "How many claims are pending?", "expect_nonempty": True},
    {"q": "Which DRG code has the highest total overpayment exposure?", "expect_nonempty": True},
    {"q": "List denied Medicare Advantage claims with their billed amounts", "expect_nonempty": True},
    {"q": "What is the average days in hospital for FWA-flagged claims?", "expect_nonempty": True},
    {"q": "Break down FWA alerts by type", "expect_nonempty": True},
]

# ── Lightweight LLM judges (Groq) ─────────────────────────────────────────────
_SCORE_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _judge(system: str, user: str) -> float:
    """Ask the model for a single 0..1 score and parse it (clamped)."""
    try:
        resp = groq_client().chat.completions.create(
            model=config.MODEL, max_tokens=8, temperature=0,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        m = _SCORE_RE.search(resp.choices[0].message.content or "")
        if not m:
            return float("nan")
        return max(0.0, min(1.0, float(m.group(1))))
    except Exception:
        return float("nan")


def judge_context_precision(question: str, keywords: list[str]) -> float:
    return _judge(
        "You score keyword extraction quality for a SQL analytics assistant. Given a "
        "question and the extracted keywords, output ONLY a number 0.0-1.0 = the fraction "
        "of keywords that are RELEVANT and USEFUL for querying (precision). 1.0 = all "
        "relevant, 0.0 = all noise.",
        f"Question: {question}\nExtracted keywords: {keywords}",
    )


def judge_faithfulness(question: str, answer: str, result_preview: str) -> float:
    return _judge(
        "You score faithfulness for a data assistant. Output ONLY a number 0.0-1.0 = the "
        "fraction of factual claims in the ANSWER that are supported by the DATA rows. "
        "If the answer states something the data contradicts or doesn't contain, lower the "
        "score. 1.0 = fully grounded, 0.0 = unsupported/hallucinated.",
        f"Question: {question}\n\nDATA (SQL result rows):\n{result_preview}\n\nANSWER:\n{answer}",
    )


def judge_answer_relevance(question: str, answer: str) -> float:
    return _judge(
        "You score answer relevance. Output ONLY a number 0.0-1.0 = how directly the ANSWER "
        "addresses the QUESTION (ignore correctness; judge focus/relevance only). 1.0 = "
        "directly answers, 0.0 = off-topic or evasive.",
        f"Question: {question}\n\nAnswer:\n{answer}",
    )


def _mean(xs: list[float]) -> float:
    vals = [x for x in xs if x == x]  # drop NaN
    return sum(vals) / len(vals) if vals else float("nan")


# ── Run ───────────────────────────────────────────────────────────────────────
def main() -> int:
    if not config.API_KEY:
        print("No Groq API key configured — metrics need the agent + judge. "
              "Set assistant/config.toml or GROQ_API_KEY.")
        return 1

    from assistant.agent import answer_question  # lazy (needs key)

    print("=" * 72)
    print("Cotiviti claims assistant — quality metrics")
    print("=" * 72)

    n = len(GOLDEN)
    executed_ok = 0
    guardrail_violations = 0
    false_empties = 0
    expect_nonempty_total = 0
    loops, latencies = [], []
    precision_scores, faithfulness_scores, relevance_scores = [], [], []

    for spec in GOLDEN:
        q = spec["q"]
        print(f"\n• {q}")
        result = answer_question(q)
        sql, answer = result["sql"], result["answer"]
        loops.append(result["loops"])
        latencies.append(result["latency"])

        # ── Structural ──
        safe = bool(sql) and is_safe_select(sql)
        if not safe:
            guardrail_violations += 1
        ran, rows = False, 0
        if safe:
            try:
                res_df = run_sql(sql)
                ran, rows = True, len(res_df)
                executed_ok += 1
            except Exception as e:  # noqa: BLE001
                print(f"   SQL error: {e}")
        if spec.get("expect_nonempty"):
            expect_nonempty_total += 1
            if ran and rows == 0:
                false_empties += 1
        print(f"   loops={result['loops']}  rows={rows}  latency={result['latency']:.2f}s  safe={safe}")

        # ── RAG quality (LLM judge) ──
        if ran:
            preview = mask_pii(res_df).head(30).to_string(index=False) if rows else "(no rows)"
            cp = judge_context_precision(q, result["keywords"])
            fa = judge_faithfulness(q, answer, preview)
            ar = judge_answer_relevance(q, answer)
            precision_scores.append(cp)
            faithfulness_scores.append(fa)
            relevance_scores.append(ar)
            print(f"   context_precision={cp:.2f}  faithfulness={fa:.2f}  answer_relevance={ar:.2f}")

    # ── Report ──
    esr = 100 * executed_ok / n
    gvr = 100 * guardrail_violations / n
    fer = (100 * false_empties / expect_nonempty_total) if expect_nonempty_total else 0.0
    avg_loops = _mean([float(x) for x in loops])

    print("\n" + "=" * 72)
    print("STRUCTURAL")
    print(f"  Execution Success Rate (ESR)      : {esr:.1f}%   ({executed_ok}/{n})")
    print(f"  Self-Healing Efficiency (avg loops): {avg_loops:.2f}   (target < 1.5)")
    print(f"  False Empty Rate                  : {fer:.1f}%   ({false_empties}/{expect_nonempty_total})")
    print(f"  SQL Guardrail Violation Rate      : {gvr:.1f}%   (must be 0%)")
    print("RAG QUALITY (0..1, LLM-judged)")
    print(f"  Context Precision                 : {_mean(precision_scores):.2f}")
    print(f"  Faithfulness                      : {_mean(faithfulness_scores):.2f}")
    print(f"  Answer Relevance                  : {_mean(relevance_scores):.2f}")
    print("PERFORMANCE")
    print(f"  Avg total latency                 : {_mean(latencies):.2f}s   (TTFT not measured — no streaming)")
    print("=" * 72)


    failed = esr < 100 or gvr > 0 or avg_loops >= 1.5
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
