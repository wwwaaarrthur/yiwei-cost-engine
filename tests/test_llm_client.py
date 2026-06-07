from agents.llm_client import LLMClient


def test_mock_mode_returns_none_text_and_fallback_trace():
    c = LLMClient(provider="mock")
    text, trace = c.chat(system="s", user="u")
    assert text is None
    assert trace["fallback"] is True
    assert trace["provider"] == "mock"
    assert "latency_ms" in trace and "model" in trace


def test_deepseek_without_key_degrades_to_mock():
    c = LLMClient(provider="deepseek", api_key=None)  # no key
    assert c.provider == "mock"          # degraded, no crash
    text, trace = c.chat(system="s", user="u")
    assert text is None and trace["fallback"] is True
