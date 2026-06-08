"""Provider-agnostic LLM client — DeepSeek (OpenAI-compatible) with mandatory mock fallback.

Keeps the AI-review layer provider-agnostic and ALWAYS degradable to mock so the public
demo never breaks without a key. Every call returns a trace (provider/model/latency/usage/
fallback) so AI usage is observable, not a black box. Key comes only from env — never repo.
"""
import os
import time
from typing import Optional, Tuple


class LLMClient:
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"

    def __init__(self, provider: str = "mock", model: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.provider = provider
        self.model = model or ("deepseek-v4-pro" if provider == "deepseek" else "mock")
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self._client = None
        if self.provider == "deepseek":
            if not self._api_key:
                self.provider = "mock"            # degrade: no key
            else:
                try:
                    from openai import OpenAI
                    self._client = OpenAI(api_key=self._api_key,
                                          base_url=self.DEEPSEEK_BASE_URL)
                except ImportError:
                    self.provider = "mock"        # degrade: no sdk

    def chat(self, system: str, user: str, max_tokens: int = 2048) -> Tuple[Optional[str], dict]:
        """Return (text|None, trace). text is None in mock mode → caller uses its own mock."""
        trace = {"provider": self.provider, "model": self.model,
                 "latency_ms": 0, "fallback": False, "usage": None}
        if self.provider == "mock" or self._client is None:
            trace["fallback"] = True
            return None, trace
        t0 = time.time()
        try:
            resp = self._client.chat.completions.create(
                model=self.model, max_tokens=max_tokens, temperature=0,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                response_format={"type": "json_object"},
            )
            trace["latency_ms"] = round((time.time() - t0) * 1000)
            u = getattr(resp, "usage", None)
            if u:
                trace["usage"] = {"prompt": u.prompt_tokens, "completion": u.completion_tokens}
            return resp.choices[0].message.content, trace
        except Exception as e:
            trace["latency_ms"] = round((time.time() - t0) * 1000)
            trace["fallback"] = True
            trace["error"] = f"{type(e).__name__}: {e}"
            return None, trace
