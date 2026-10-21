"""Thin LLM client over plain HTTP: Gemini (free tier), Groq (free tier) or Anthropic."""
import requests

from .util import env, extract_json, log, retry


def _ok(r: requests.Response) -> requests.Response:
    """raise_for_status, but keep the provider's error message (it says what is wrong)."""
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
    return r


class LLM:
    def __init__(self, cfg: dict):
        c = cfg["llm"]
        if c.get("chain"):
            self.chain = [tuple(x) for x in c["chain"]]
        else:
            self.chain = [(c["provider"], c["model"])]
            if c.get("fallback_provider"):
                self.chain.append((c["fallback_provider"], c["fallback_model"]))

    def text(self, prompt: str, system: str = "", max_tokens: int = 8192, json_mode: bool = False) -> str:
        errors = []
        for provider, model in self.chain:
            try:
                call = getattr(self, f"_{provider}")
                return retry(lambda: call(model, prompt, system, max_tokens, json_mode),
                             what=f"{provider}:{model}", base_delay=10)  # free tiers limit per minute
            except Exception as e:  # noqa: BLE001
                log.warning("Provider %s failed: %s", provider, e)
                errors.append(f"{provider}/{model}: {e}")
        raise RuntimeError("All LLM providers failed -> " + " | ".join(errors))

    def json(self, prompt: str, system: str = "", max_tokens: int = 8192):
        prompt += "\n\nReturn ONLY valid JSON, no commentary."
        for attempt in range(3):
            raw = self.text(prompt, system, max_tokens, json_mode=True)
            try:
                return extract_json(raw)
            except Exception as e:  # noqa: BLE001
                log.warning("Bad JSON from model (attempt %d): %s", attempt + 1, e)
        raise RuntimeError("Model kept returning invalid JSON")

    # --- providers -------------------------------------------------------

    def _gemini(self, model, prompt, system, max_tokens, json_mode):
        key = env("GEMINI_API_KEY", required=True)
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            # newer Gemini models "think" first and that counts against the output budget
            "generationConfig": {"maxOutputTokens": max(max_tokens, 32768), "temperature": 0.9},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key}, json=body, timeout=300)
        _ok(r)
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    def _groq(self, model, prompt, system, max_tokens, json_mode):
        key = env("GROQ_API_KEY", required=True)
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}]
        body = {"model": model, "messages": msgs, "max_tokens": min(max_tokens, 8000), "temperature": 0.9}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {key}"}, json=body, timeout=300)
        _ok(r)
        return r.json()["choices"][0]["message"]["content"]

    def _anthropic(self, model, prompt, system, max_tokens, json_mode):
        key = env("ANTHROPIC_API_KEY", required=True)
        body = {"model": model, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                          json=body, timeout=600)
        _ok(r)
        return "".join(b.get("text", "") for b in r.json()["content"])
