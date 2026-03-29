"""LLM completion with Gemini (AI Studio) + Groq fallback. No API keys in code."""

import time
import requests
from google import genai

import config

# Gemini model IDs in priority order — current as of March 2026.
# Per https://ai.google.dev/gemini-api/docs/models:
#   Gemini 2.5 Flash   — best price/performance for low-latency tasks (stable)
#   Gemini 3 Flash     — frontier-class, Preview
#   Gemini 2.5 Flash-Lite — fastest / cheapest in the 2.5 family (stable)
#   Gemini 3.1 Flash-Lite — frontier Preview, fast + cheap
# NOTE: "Gemini 2.5 Flash TTS" is a text-to-speech audio model — NOT for text tasks.
# 2.0 and 1.5 models are deprecated/shutting down and intentionally omitted.
_GEMINI_MODELS = [
    "gemini-2.5-flash",           # Gemini 2.5 Flash (stable)
    "gemini-2.5-flash-preview",   # preview alias in case stable isn't live yet for key
    "gemini-3-flash",             # Gemini 3 Flash (Preview)
    "gemini-3.0-flash",           # alternate ID for Gemini 3 Flash
    "gemini-2.5-flash-lite",      # Gemini 2.5 Flash-Lite (stable)
    "gemini-3.1-flash-lite",      # Gemini 3.1 Flash-Lite (Preview)
    "gemini-3.1-flash-lite-preview",
]

# Groq: separate free-tier quota (https://console.groq.com)
_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]

_GEMINI_ATTEMPTS_PER_MODEL = 3
_GEMINI_RETRY_DELAY_SEC = 12
_GEMINI_429_DELAY_SEC = 45

_GROQ_ATTEMPTS_PER_MODEL = 3
_GROQ_RETRY_DELAY_SEC = 15
_GROQ_429_DELAY_SEC = 60


def any_llm_configured() -> bool:
    return bool(config.GEMINI_API_KEY or config.GROQ_API_KEY)


def _sleep(msg: str, seconds: float) -> None:
    print(msg)
    time.sleep(seconds)


def _gemini_generate(prompt: str) -> str | None:
    if not config.GEMINI_API_KEY:
        return None
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    for model in _GEMINI_MODELS:
        for attempt in range(_GEMINI_ATTEMPTS_PER_MODEL):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                text = (resp.text or "").strip()
                if text:
                    print(f"  [LLM] OK via Gemini model: {model}")
                    return text
                print(f"  [LLM] Empty text from {model} (try {attempt + 1})")
            except Exception as e:
                err = str(e)
                short = err[:180].replace("\n", " ")
                print(f"  [LLM] Gemini {model} try {attempt + 1}: {short}")

                if "404" in err or "NOT_FOUND" in err.upper():
                    # Wrong model name for this project — skip to next model ID
                    break

                if "429" in err or "RESOURCE_EXHAUSTED" in err.upper():
                    _sleep(
                        f"  [LLM] Gemini rate-limited — waiting {_GEMINI_429_DELAY_SEC}s...",
                        _GEMINI_429_DELAY_SEC,
                    )
                    continue

            if attempt < _GEMINI_ATTEMPTS_PER_MODEL - 1:
                _sleep(
                    f"  [LLM] Retrying Gemini {model} in {_GEMINI_RETRY_DELAY_SEC}s...",
                    _GEMINI_RETRY_DELAY_SEC,
                )

    print("  [LLM] All Gemini model IDs failed.")
    return None


def _groq_generate(prompt: str) -> str | None:
    if not config.GROQ_API_KEY:
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    for model in _GROQ_MODELS:
        for attempt in range(_GROQ_ATTEMPTS_PER_MODEL):
            try:
                r = requests.post(
                    url,
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "max_tokens": 8192,
                    },
                    timeout=120,
                )

                if r.status_code == 429:
                    wait = _GROQ_429_DELAY_SEC * (attempt + 1)
                    _sleep(f"  [Groq] 429 — waiting {wait}s...", wait)
                    continue

                if r.status_code >= 400:
                    print(f"  [Groq] {model} HTTP {r.status_code}: {r.text[:200]}")
                    break

                data = r.json()
                choices = data.get("choices") or []
                if not choices:
                    print(f"  [Groq] {model}: no choices in response")
                    break

                text = (choices[0].get("message") or {}).get("content", "").strip()
                if text:
                    print(f"  [LLM] OK via Groq model: {model}")
                    return text

            except Exception as e:
                print(f"  [Groq] {model} try {attempt + 1}: {e}")

            if attempt < _GROQ_ATTEMPTS_PER_MODEL - 1:
                _sleep(
                    f"  [Groq] Retrying in {_GROQ_RETRY_DELAY_SEC}s...",
                    _GROQ_RETRY_DELAY_SEC,
                )

    print("  [LLM] All Groq models failed.")
    return None


def complete(prompt: str) -> str | None:
    """Run completion: prefer Gemini first unless LLM_GEMINI_FIRST is false, then Groq."""
    gemini_first = config.LLM_GEMINI_FIRST

    if gemini_first:
        out = _gemini_generate(prompt)
        if out:
            return out
        print("  [LLM] Falling back to Groq...")
        return _groq_generate(prompt)

    out = _groq_generate(prompt)
    if out:
        return out
    print("  [LLM] Falling back to Gemini...")
    return _gemini_generate(prompt)
