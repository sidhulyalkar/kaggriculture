from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
from pathlib import Path
import random
import socket
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    provider: str
    model: str
    metadata: dict[str, Any]


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        retry_after_s: float | None = None,
    ):
        super().__init__(message)
        self.retryable = bool(retryable)
        self.status_code = status_code
        self.retry_after_s = retry_after_s


class BaseProvider:
    name = "base"

    def complete(self, *, model: str, system: str, prompt: str, timeout_s: int) -> ProviderResponse:
        raise NotImplementedError


def _retry_after_seconds(exc: urllib.error.HTTPError) -> float | None:
    raw = exc.headers.get("Retry-After") if exc.headers else None
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def _post_json(*, endpoint: str, api_key: str, body: dict[str, Any], timeout_s: int) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"provider returned invalid JSON: {exc}",
                retryable=True,
            ) from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-2000:]
        retryable = exc.code in {408, 425, 429, 500, 502, 503, 504}
        raise ProviderError(
            f"HTTP {exc.code}: {detail}",
            retryable=retryable,
            status_code=int(exc.code),
            retry_after_s=_retry_after_seconds(exc),
        ) from exc
    except (
        urllib.error.URLError,
        TimeoutError,
        socket.timeout,
        ConnectionError,
        http.client.HTTPException,
        OSError,
    ) as exc:
        raise ProviderError(
            f"provider transport failed: {type(exc).__name__}: {exc}",
            retryable=True,
        ) from exc


def _retryable_provider_error(exc: ProviderError) -> bool:
    if getattr(exc, "retryable", False):
        return True
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "http 408",
            "http 425",
            "http 429",
            "http 500",
            "http 502",
            "http 503",
            "http 504",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "connection reset",
            "remote end closed connection",
            "remote disconnected",
            "incomplete read",
        )
    )


def _retry_delay_s(exc: ProviderError, attempt: int) -> float:
    retry_after = getattr(exc, "retry_after_s", None)
    if retry_after is not None:
        base = retry_after
    else:
        base = float(os.environ.get("SWARM_PROVIDER_BACKOFF_BASE_S", "2.0")) * (2.0 ** attempt)
    cap = float(os.environ.get("SWARM_PROVIDER_MAX_BACKOFF_S", "30.0"))
    jitter = random.uniform(0.0, float(os.environ.get("SWARM_PROVIDER_BACKOFF_JITTER_S", "0.75")))
    return min(cap, max(0.0, base)) + jitter


def _post_json_with_retries(
    *, endpoint: str, api_key: str, body: dict[str, Any], timeout_s: int, attempts: int
) -> dict[str, Any]:
    total_attempts = max(1, int(attempts))
    last_error: ProviderError | None = None
    for attempt in range(total_attempts):
        try:
            return _post_json(endpoint=endpoint, api_key=api_key, body=body, timeout_s=timeout_s)
        except ProviderError as exc:
            last_error = exc
            if attempt + 1 >= total_attempts or not _retryable_provider_error(exc):
                raise
            time.sleep(_retry_delay_s(exc, attempt))
    assert last_error is not None
    raise last_error


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
        payload = _post_json_with_retries(
            endpoint=self.endpoint,
            api_key=api_key,
            body=body,
            timeout_s=timeout_s,
            attempts=int(os.environ.get("SWARM_OPENAI_ATTEMPTS", "3")),
        )
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

    @staticmethod
    def _model_request_policy(model: str) -> dict[str, Any]:
        """Return only NIM request fields that are known to be model-specific.

        The hosted NVIDIA catalog contains multiple chat templates. Treating every
        model as if it used Nemotron reasoning controls caused both V2-runner 400s
        and very long DeepSeek probe calls. Structured swarm jobs default to
        concise final-answer mode; the scientific reasoning itself is required in
        the visible experiment contract rather than hidden reasoning tokens.
        """
        normalized = model.lower()
        if "nemotron-3-ultra" in normalized:
            return {
                "chat_template_kwargs": {
                    "enable_thinking": False,
                    "force_nonempty_content": True,
                }
            }
        if "nemotron-3.5-lightning" in normalized:
            return {"chat_template_kwargs": {"enable_thinking": False}}
        if "deepseek-v4" in normalized:
            return {
                "chat_template_kwargs": {"thinking": False},
                "seed": int(os.environ.get("SWARM_NVIDIA_SEED", "42")),
            }
        return {}

    def complete(self, *, model: str, system: str, prompt: str, timeout_s: int) -> ProviderResponse:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise ProviderError("Missing environment variable NVIDIA_API_KEY")
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": float(os.environ.get("SWARM_NVIDIA_TEMPERATURE", "0.7")),
            "top_p": float(os.environ.get("SWARM_NVIDIA_TOP_P", "0.95")),
            "max_tokens": int(os.environ.get("SWARM_NVIDIA_MAX_TOKENS", "16384")),
            "stream": False,
        }
        body.update(self._model_request_policy(model))
        payload = _post_json_with_retries(
            endpoint=self.endpoint,
            api_key=api_key,
            body=body,
            timeout_s=timeout_s,
            attempts=int(os.environ.get("SWARM_NVIDIA_ATTEMPTS", "3")),
        )
        try:
            message = payload["choices"][0]["message"]
            text = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Unexpected NVIDIA NIM response shape") from exc
        if text is None:
            raise ProviderError("NVIDIA NIM returned an empty message content")
        metadata = dict(payload.get("usage", {}))
        if isinstance(message, dict) and message.get("reasoning_content"):
            metadata["reasoning_chars"] = len(str(message["reasoning_content"]))
        metadata["request_policy"] = self._model_request_policy(model)
        return ProviderResponse(text=str(text), provider=self.name, model=model, metadata=metadata)


class ManualProvider(BaseProvider):
    name = "manual"

    def __init__(self, outbox: str | Path):
        self.outbox = Path(outbox)
        self.outbox.mkdir(parents=True, exist_ok=True)

    def complete(self, *, model: str, system: str, prompt: str, timeout_s: int) -> ProviderResponse:
        del timeout_s
        path = self.outbox / f"request_{uuid4().hex}.json"
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
