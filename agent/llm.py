"""Provider-agnostic LLM client with a persistent on-disk cache.

One interface, three backends — Anthropic, Gemini and OpenAI — chosen by ``LLM_PROVIDER``
in ``.env``. Nothing outside this module knows which provider is in use, so swapping
backends changes one environment variable rather than any agent code.

Caching
-------
Every call is keyed on a SHA-256 of the exact prompt **plus** the provider, model,
temperature and prompt version, and persisted under ``cache/agent/``. Re-running makes
zero API calls, and the offline test suite replays from the same cache. A cache entry
records everything needed to interpret it later: which model produced it, when, and what
it cost.

Because the key includes the model and prompt version, changing either produces new keys
rather than silently reusing responses from a different configuration.

Failure behaviour
-----------------
Fails loud. A missing key, an unsupported provider, an unparseable response and an
exhausted retry budget all raise. Nothing returns a default answer, because a plausible
fabricated response is far worse here than a crash.
"""

from __future__ import annotations

import hashlib
import json
import threading
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.config import LLM_PROVIDERS, settings

__all__ = [
    "LLMError",
    "LLMResponse",
    "LLMClient",
    "CACHE_VERSION",
]

#: Bump when the cache entry format changes. Part of every key, so old entries are never
#: silently reinterpreted under a new schema.
CACHE_VERSION = "v1"

#: Per-million-token prices, for the cost figure the report has to carry. Approximate and
#: recorded as such; the token counts themselves are exact.
_PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (15.00, 75.00),
    "gemini-2.5-flash": (0.30, 2.50),
    # Preview model: public pricing not confirmed at the time of writing. Priced here at
    # the 2.5-flash rate so the figure is not silently zero; token counts are exact and
    # the report states the price is an estimate.
    "gemini-3-flash-preview": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


class LLMError(RuntimeError):
    """Raised when a call cannot be completed or its response cannot be used."""


@dataclass
class LLMResponse:
    """One model response plus everything needed to audit it later."""

    text: str
    provider: str
    model: str
    temperature: float
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    from_cache: bool = False
    created_utc: str = ""
    latency_seconds: float = 0.0

    @property
    def estimated_cost_usd(self) -> float:
        """Approximate cost. Token counts are exact; the price table is not."""
        prices = _PRICES_USD_PER_MTOK.get(self.model)
        if prices is None:
            return 0.0
        return (
            self.input_tokens * prices[0] + self.output_tokens * prices[1]
        ) / 1_000_000


class LLMClient:
    """A cached, provider-agnostic chat client.

    ``offline=True`` serves only from cache and raises on a miss, which is how the test
    suite guarantees it makes no network calls.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        prompt_version: str = "v1",
        cache_dir: Optional[Path] = None,
        offline: bool = False,
        max_retries: int = 3,
    ) -> None:
        self.provider = (provider or settings.LLM_PROVIDER).lower()
        if self.provider not in LLM_PROVIDERS:
            raise LLMError(
                f"unsupported provider {self.provider!r}; expected one of "
                f"{sorted(LLM_PROVIDERS)}"
            )
        self.model = model or settings.LLM_MODEL
        self.temperature = float(temperature)
        self.prompt_version = prompt_version
        self.offline = offline
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir or (settings.CACHE_DIR / "agent"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.calls_made = 0
        self.cache_hits = 0
        self.input_tokens = 0
        self.output_tokens = 0
        # Requests are issued concurrently, so the counters need a lock. The cache
        # itself is safe already: each entry is written to a temp file and renamed.
        self._lock = threading.Lock()

        self._client: Any = None

    # -- cache ---------------------------------------------------------------------------

    def cache_key(
        self, prompt: str, system: str = "", salt: str = "", max_tokens: int = 0
    ) -> str:
        """SHA-256 over everything that could change the response.

        ``salt`` exists so the self-consistency runs can force distinct keys for an
        identical prompt, which is the only honest way to measure whether the model
        agrees with itself.
        """
        payload = json.dumps(
            {
                "cache_version": CACHE_VERSION,
                "provider": self.provider,
                "model": self.model,
                "temperature": self.temperature,
                "prompt_version": self.prompt_version,
                "system": system,
                "prompt": prompt,
                "salt": salt,
                # Part of the key because it changes the response: a budget too small to
                # cover the model's internal reasoning truncates the answer, and that
                # truncated text must not be replayed once the budget is raised.
                "max_tokens": max_tokens,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        # Shard by the first two hex characters: 256 directories keeps any one of them
        # small enough that listing stays fast at tens of thousands of entries.
        shard = self.cache_dir / key[:2]
        shard.mkdir(parents=True, exist_ok=True)
        return shard / f"{key}.json"

    def _read_cache(self, key: str) -> Optional[LLMResponse]:
        path = self._cache_path(key)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMError(f"cache entry {path} is corrupt: {exc}") from exc
        payload.pop("estimated_cost_usd", None)
        response = LLMResponse(**payload)
        response.from_cache = True
        return response

    def _write_cache(self, key: str, response: LLMResponse) -> None:
        path = self._cache_path(key)
        payload = asdict(response)
        payload["from_cache"] = False
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        temp.replace(path)

    # -- providers -----------------------------------------------------------------------

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        key = settings.llm_api_key(self.provider)  # raises if missing; never logged

        if self.provider == "anthropic":
            import anthropic

            self._client = anthropic.Anthropic(api_key=key)
        elif self.provider == "gemini":
            from google import genai

            self._client = genai.Client(api_key=key)
        elif self.provider == "openai":
            import openai

            self._client = openai.OpenAI(api_key=key)
        else:  # pragma: no cover - guarded in __init__
            raise LLMError(f"unsupported provider {self.provider!r}")
        return self._client

    def _call_provider(
        self, prompt: str, system: str, max_tokens: int
    ) -> tuple[str, int, int]:
        """One raw provider call. Returns (text, input_tokens, output_tokens)."""
        client = self._ensure_client()

        if self.provider == "anthropic":
            message = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=self.temperature,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in message.content if getattr(block, "type", "") == "text"
            )
            return text, message.usage.input_tokens, message.usage.output_tokens

        if self.provider == "gemini":
            from google.genai import types

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system or None,
                    temperature=self.temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            usage = getattr(response, "usage_metadata", None)
            # Gemini 3 models reason internally before answering. Those thinking tokens
            # are billed as output and are drawn from the same max_output_tokens budget,
            # so they must be counted -- omitting them under-reports cost and hides the
            # reason a response was truncated.
            thoughts = getattr(usage, "thoughts_token_count", 0) or 0
            answer = getattr(usage, "candidates_token_count", 0) or 0
            finish = None
            if getattr(response, "candidates", None):
                finish = getattr(response.candidates[0], "finish_reason", None)
            if finish is not None and "MAX_TOKENS" in str(finish):
                raise LLMError(
                    f"response truncated at max_output_tokens ({thoughts} thinking + "
                    f"{answer} answer tokens); raise max_tokens"
                )
            return (response.text or "", getattr(usage, "prompt_token_count", 0) or 0,
                    thoughts + answer)

        if self.provider == "openai":
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            completion = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
            usage = completion.usage
            return (
                completion.choices[0].message.content or "",
                getattr(usage, "prompt_tokens", 0) or 0,
                getattr(usage, "completion_tokens", 0) or 0,
            )

        raise LLMError(f"unsupported provider {self.provider!r}")  # pragma: no cover

    # -- the public call -----------------------------------------------------------------

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
        salt: str = "",
    ) -> LLMResponse:
        """Return a completion, from cache when available.

        Raises rather than returning anything on failure: an exhausted retry budget, a
        missing key, or a cache miss while offline.
        """
        key = self.cache_key(prompt, system, salt, max_tokens)
        cached = self._read_cache(key)
        if cached is not None:
            with self._lock:
                self.cache_hits += 1
            return cached

        if self.offline:
            raise LLMError(
                f"cache miss for key {key[:12]}... and the client is offline; "
                "run scripts/run_agent.py to populate the cache"
            )

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            started = time.perf_counter()
            try:
                text, input_tokens, output_tokens = self._call_provider(
                    prompt, system, max_tokens
                )
            except Exception as exc:  # provider SDKs raise their own hierarchies
                last_error = exc
                if attempt == self.max_retries - 1:
                    break
                time.sleep(2.0 * (2**attempt))
                continue

            if not text.strip():
                last_error = LLMError("provider returned an empty response")
                if attempt == self.max_retries - 1:
                    break
                continue

            response = LLMResponse(
                text=text,
                provider=self.provider,
                model=self.model,
                temperature=self.temperature,
                prompt_version=self.prompt_version,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                from_cache=False,
                created_utc=datetime.now(timezone.utc).isoformat(),
                latency_seconds=round(time.perf_counter() - started, 3),
            )
            self._write_cache(key, response)
            with self._lock:
                self.calls_made += 1
                self.input_tokens += response.input_tokens
                self.output_tokens += response.output_tokens
            return response

        raise LLMError(
            f"{self.provider}/{self.model} failed after {self.max_retries} attempts: "
            f"{last_error}"
        ) from last_error

    # -- accounting ----------------------------------------------------------------------

    def usage_summary(self) -> dict[str, Any]:
        prices = _PRICES_USD_PER_MTOK.get(self.model)
        cost = (
            (self.input_tokens * prices[0] + self.output_tokens * prices[1]) / 1_000_000
            if prices else 0.0
        )
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "prompt_version": self.prompt_version,
            "api_calls": self.calls_made,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": round(cost, 4),
            "price_table_is_approximate": True,
        }
