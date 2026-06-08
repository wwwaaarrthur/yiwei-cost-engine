from agents.llm_client import LLMClient


def test_mock_mode_returns_none_text_and_fallback_trace():
    c = LLMClient(provider="mock")
    text, trace = c.chat(system="s", user="u")
    assert text is None
    assert trace["fallback"] is True
    assert trace["provider"] == "mock"
    assert "latency_ms" in trace and "model" in trace


def test_deepseek_without_key_degrades_to_mock(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)   # isolate from a real env key
    c = LLMClient(provider="deepseek", api_key=None)  # no key
    assert c.provider == "mock"          # degraded, no crash
    text, trace = c.chat(system="s", user="u")
    assert text is None and trace["fallback"] is True


def test_critic_falls_back_to_mock_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)   # isolate from a real env key
    from agents.critic_agent import CriticAgent
    # provider deepseek but no key → LLMClient degrades → critic uses _mock_call
    critic = CriticAgent(use_llm=True, provider="deepseek", api_key=None)
    context = {"price_range": {"p25": 1.0, "p50": 1.5, "p75": 2.0}, "flute_filter": "BC"}
    draft = {"recommended_price_per_m2": 1.5, "rationale": "median of precheck",
             "trade_offs": ["x"], "risks": []}
    out = critic.review(context, draft, "quote BC box")
    assert out["verdict"] in {"approve", "revise", "reject"}
    assert out["mode"] == "mock"   # degraded cleanly
