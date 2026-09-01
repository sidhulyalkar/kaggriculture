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


def _post_json(*, endpoint: str, api_key: str, body: dict[str, Any], timeout_s: int) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-2000:]
        raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProviderError(f"provider request failed: {exc}") from exc


class OpenAIResponsesProvider(BaseProvider):
    name = "openai"

    def __init__(self, endpoint: str = "https://api.openai.com/v1/responses"):
        self.endpoint = endpoint

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        chunks: list[str] = []
        for item in payload.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text = content.get("text")
                    if text:
                        chunks.append(str(text))
        if not chunks and isinstance(payload.get("output_text"), str):
            chunks.append(payload["output_text"])
        if not chunks:
            raise ProviderError("OpenAI Responses payload contained no output_text")
        return "\n".join(chunks)

    def complete(self, *, model: str, system: str, prompt: str, timeout_s: int) -> ProviderResponse:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("Missing environment variable OPENAI_API_KEY")
        body: dict[str, Any] = {
            "model": model,
            "instructions": system,
            "input": prompt,
            "reasoning": {"effort": os.environ.get("SWARM_OPENAI_REASONING", "high")},
        }
        payload = _post_json(endpoint=self.endpoint, api_key=api_key, body=body, timeout_s=timeout_s)
        return ProviderResponse(
            text=self._output_text(payload),
            provider=self.name,
            model=model,
            metadata=dict(payload.get("usage", {})),
        )


class NvidiaNimProvider(BaseProvider):
    name = "nvidia"

    def __init__(self, endpoint: str = "https://integrate.api.nvidia.com/v1/chat/completions"):
        self.endpoint = endpoint

    def complete(self, *, model: str, system: str, prompt: str, timeout_s: int) -> ProviderResponse:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise ProviderError("Missing environment variable NVIDIA_API_KEY")
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": int(os.environ.get("SWARM_NVIDIA_MAX_TOKENS", "16384")),
            "stream": False,
        }
        payload = _post_json(endpoint=self.endpoint, api_key=api_key, body=body, timeout_s=timeout_s)
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Unexpected NVIDIA NIM response shape") from exc
        return ProviderResponse(
            text=str(text),
            provider=self.name,
            model=model,
            metadata=dict(payload.get("usage", {})),
        )


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
        endpoint = os.environ.get("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses")
        return OpenAIResponsesProvider(endpoint=endpoint)
    if normalized == "nvidia":
        endpoint = os.environ.get("NVIDIA_CHAT_COMPLETIONS_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
        return NvidiaNimProvider(endpoint=endpoint)
    if normalized == "manual":
        return ManualProvider(manual_outbox)
    raise ProviderError(f"Unknown provider {name!r}")
