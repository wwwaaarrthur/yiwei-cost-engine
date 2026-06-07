import os

from llm_eval import score_case, check_guardrails, run_eval

CASES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "llm_eval_cases.json")


def test_risk_recall_and_verdict():
    expected = {"must_flag_risk_keywords": ["BC", "MAPE"], "must_request_missing": ["lamination"],
                "expected_verdict": "revise", "must_not_claim": ["sets final price"]}
    critic_out = {"verdict": "revise",
                  "issues": [{"detail": "BC flute 49% MAPE not flagged"}],
                  "recommendation_to_user": "review caveats: BC MAPE; please confirm lamination"}
    s = score_case(critic_out, expected)
    assert s["risk_recall"] == 1.0        # both "BC" and "MAPE" present in text
    assert s["verdict_correct"] is True
    assert s["missing_recall"] == 1.0     # "lamination" present
    assert s["overreach"] is False


def test_guardrails_flag_schema_and_price_overreach():
    bad = {"verdict": "maybe", "recommendation_to_user": "final price is ¥9.9/m²"}
    g = check_guardrails(bad)
    assert g["valid_verdict"] is False                 # 'maybe' not allowed
    assert g["sets_price"] is True                     # critic must NOT set price
    good = {"verdict": "approve", "issues": [], "recommendation_to_user": "approved, see caveats"}
    g2 = check_guardrails(good)
    assert g2["valid_verdict"] is True and g2["sets_price"] is False


def test_run_eval_on_cases_file_mock_mode(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)   # force mock, deterministic
    report = run_eval(CASES, provider="deepseek", api_key=None)
    assert report["n_cases"] == 10
    assert 0.0 <= report["avg_risk_recall"] <= 1.0
    assert "avg_latency_ms" in report and report["mode"] == "mock"
    assert report["overreach_count"] >= 0
