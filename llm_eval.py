"""Eval the LLM review layer's outputs against human-anchored labels.

Measures what aggregate accuracy can't: does the critic RECALL real risks, REQUEST
missing info, pick the right verdict, and avoid overreach/hallucination? Deterministic
string-anchored scoring first (cheap, reproducible); an optional LLM-judge can be added
later but MUST be validated against these human anchors (TPR/TNR), per the no-blind-judge rule.

Run: python3 llm_eval.py   (mock baseline without key; real with DEEPSEEK_API_KEY set)
"""
import json
import os
import re

from agents.critic_agent import CriticAgent


# ─────────────────────────────────────────────────────────────────────────
# Per-case scoring (recall / missing-info / verdict / overreach)
# ─────────────────────────────────────────────────────────────────────────
def _blob(critic_out: dict) -> str:
    parts = [critic_out.get("recommendation_to_user", "")]
    parts += [i.get("detail", "") for i in critic_out.get("issues", [])]
    return " ".join(parts).lower()


def score_case(critic_out: dict, expected: dict) -> dict:
    text = _blob(critic_out)
    risks = expected.get("must_flag_risk_keywords", [])
    risk_hits = sum(1 for k in risks if k.lower() in text)
    risk_recall = (risk_hits / len(risks)) if risks else 1.0
    miss = expected.get("must_request_missing", [])
    miss_hits = sum(1 for k in miss if k.lower() in text)
    miss_recall = (miss_hits / len(miss)) if miss else 1.0
    verdict_correct = critic_out.get("verdict") == expected.get("expected_verdict")
    overreach = any(bad.lower() in text for bad in expected.get("must_not_claim", []))
    return {"risk_recall": round(risk_recall, 3), "missing_recall": round(miss_recall, 3),
            "verdict_correct": verdict_correct, "overreach": overreach}


# ─────────────────────────────────────────────────────────────────────────
# Deterministic guardrails (must pass regardless of content quality)
# ─────────────────────────────────────────────────────────────────────────
ALLOWED_VERDICTS = {"approve", "revise", "reject"}
# Overreach = critic SETTING a final price, not explaining/echoing the analysis price.
# Deliberately narrow: "median price of X is recommended" (explanation) must NOT match.
_PRICE_SET = re.compile(r"(final price (is|=|:)|i (set|am setting|will set|have set) the (final )?price|定价为)", re.I)


def check_guardrails(critic_out: dict) -> dict:
    """Deterministic safety checks the LLM output must pass regardless of content quality."""
    text = critic_out.get("recommendation_to_user", "")
    return {
        "valid_verdict": critic_out.get("verdict") in ALLOWED_VERDICTS,
        "sets_price": bool(_PRICE_SET.search(text)),   # critic must NOT own final price
        "parse_failed": bool(critic_out.get("parse_failed")),
    }


# ─────────────────────────────────────────────────────────────────────────
# Runner + trace summary
# ─────────────────────────────────────────────────────────────────────────
def run_eval(cases_path: str, provider: str = "deepseek", api_key: str = None) -> dict:
    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)
    critic = CriticAgent(use_llm=True, provider=provider, api_key=api_key)
    mode = "real" if (critic._llm and critic._llm.provider != "mock") else "mock"
    rows, lat = [], []
    for c in cases:
        out = critic.review(c["context"], c["draft"], c["query"])
        s = score_case(out, c["expected"])
        g = check_guardrails(out)
        tr = out.get("trace", {}) or {}
        lat.append(tr.get("latency_ms", 0))
        rows.append({"id": c["id"], **s, **g, "model": tr.get("model", mode)})
    n = len(rows)
    avg = lambda k: round(sum(r[k] for r in rows) / n, 3) if n else 0.0
    return {
        "n_cases": n, "mode": mode,
        "avg_risk_recall": avg("risk_recall"), "avg_missing_recall": avg("missing_recall"),
        "verdict_accuracy": round(sum(r["verdict_correct"] for r in rows) / n, 3) if n else 0.0,
        "overreach_count": sum(r["sets_price"] or r["overreach"] for r in rows),
        "invalid_verdict_count": sum(not r["valid_verdict"] for r in rows),
        "avg_latency_ms": round(sum(lat) / n) if n else 0,
        "rows": rows,
    }


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    rep = run_eval(os.path.join(here, "data", "llm_eval_cases.json"),
                   provider="deepseek", api_key=os.environ.get("DEEPSEEK_API_KEY"))
    print(f"\n=== LLM Review Eval ({rep['mode']} mode, n={rep['n_cases']}) ===")
    print(f"  risk-recall            : {rep['avg_risk_recall']}")
    print(f"  missing-recall         : {rep['avg_missing_recall']}")
    print(f"  verdict-accuracy       : {rep['verdict_accuracy']}")
    print(f"  overreach (price/claim): {rep['overreach_count']}  (must be 0)")
    print(f"  invalid verdicts       : {rep['invalid_verdict_count']}")
    print(f"  avg latency ms         : {rep['avg_latency_ms']}")
    for r in rep["rows"]:
        print(f"    {r['id']:26} recall={r['risk_recall']} verdict_ok={r['verdict_correct']} "
              f"price_overreach={r['sets_price']} model={r['model']}")
