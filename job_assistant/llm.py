from __future__ import annotations

import re

import httpx

from . import config


class OllamaError(RuntimeError):
    pass


def _strip_thinking(text: str) -> str:
    text = text.strip()
    think_open = "<" + "think>"
    think_close = "</" + "think>"
    if think_open in text:
        text = re.sub(
            re.escape(think_open) + r".*?" + re.escape(think_close),
            "",
            text,
            flags=re.DOTALL,
        ).strip()
    if text.startswith("```markdown"):
        text = text[11:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def check_ollama() -> None:
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        raise OllamaError(
            "Ollama is not running. Start it with: ollama serve\n"
            f"Then pull your model: ollama pull {config.OLLAMA_MODEL}"
        ) from exc


def complete(system: str, user: str, *, extra: str = "") -> str:
    """Single chat completion via local Ollama."""
    check_ollama()
    content = user + (f"\n\n{extra}" if extra else "")
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        "stream": False,
        "options": {"num_ctx": config.OLLAMA_NUM_CTX},
    }
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    with httpx.Client(timeout=config.OLLAMA_TIMEOUT_SECONDS) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    message = data.get("message", {}).get("content", "")
    if not message:
        raise OllamaError("Empty response from Ollama")
    return _strip_thinking(message)
