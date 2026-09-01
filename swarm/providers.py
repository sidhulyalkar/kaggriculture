from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    provider: str
    model: str
    metadata: dict[str, Any]


class ProviderError(RuntimeError):
    pass


class BaseProvider:
    name = "base"

    def complete(self, *, model: str, system: str, prompt: str, timeout_s: int) -> ProviderResponse:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseProvider):
    """Minimal chat-completions adapter for OpenAI-compatible endpoints.

    Endpoint and key are injected at runtime. Keeping this module stdlib-only makes the
    orchestration layer usable in constrained Kaggle/local environments.
    """

    def __init__(self, *, name: str, endpoint: str, api_key_env: str):
        self.name = name
        self.endpoint = endpoint
        self.api_key_env = api_key_env

    def complete(self, *, model: str, system: str, prompt: str, timeout_s: int) -> ProviderResponse:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ProviderError(f"Missing environment variable {self.api_key_env}")
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"{self.name} request failed: {exc}") from exc
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected {self.name} response shape") from exc
        return ProviderResponse(text=text, provider=self.name, model=model, metadata=payload.get("usage", {}))


class ManualProvider(BaseProvider):
    name = "manual"

    def __init__(self, outbox: str | Path):
        self.outbox = Path(outbox)
        self.outbox.mkdir(parents=True, exist_ok=True)

    def complete(self, *, model: str, system: str, prompt: str, timeout_s: int) -> ProviderResponse:
        del timeout_s
        index = len(list(self.outbox.glob("*.json")))
        path = self.outbox / f"request_{index:04d}.json"
        path.write_text(
            json.dumps({"model": model, "system": system, "prompt": prompt}, indent=2),
            encoding="utf-8",
        )
        return ProviderResponse(
            text="",
            provider=self.name,
            model=model,
            metadata={"exported_request": str(path)},
        )


def build_provider(name: str, *, manual_outbox: str | Path) -> BaseProvider:
    normalized = name.lower()
    if normalized == "openai":
        endpoint = os.environ.get("OPENAI_CHAT_COMPLETIONS_URL", "https://api.openai.com/v1/chat/completions")
        return OpenAICompatibleProvider(name="openai", endpoint=endpoint, api_key_env="OPENAI_API_KEY")
    if normalized == "nvidia":
        endpoint = os.environ.get("NVIDIA_CHAT_COMPLETIONS_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
        return OpenAICompatibleProvider(name="nvidia", endpoint=endpoint, api_key_env="NVIDIA_API_KEY")
    if normalized == "manual":
        return ManualProvider(manual_outbox)
    raise ProviderError(f"Unknown provider {name!r}")
