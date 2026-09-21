"""Groq, over its OpenAI-compatible chat completions API.

No vendor SDK: the API is a single HTTP POST, and httpx with an explicit
timeout is easier to reason about than another dependency.
"""

import json
import logging
import time

import httpx

from app.config import settings
from app.llm.base import (
    REPAIRABLE_ERRORS,
    Extraction,
    LLMOutcome,
    LLMProvider,
    ProfileSummary,
)
from app.llm.prompts import REPAIR_INSTRUCTION, SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.base_url = settings.groq_base_url

    def extract_and_score(self, posting_text: str, profile: ProfileSummary) -> list[LLMOutcome]:
        """Up to two requests: the call, and one repair if it came back unusable.

        Returns every attempt rather than just the final one, because each
        request made is a row the cost log has to carry. The caller uses the
        last outcome and logs them all.
        """
        user_prompt = build_user_prompt(posting_text, profile, settings.llm_max_input_tokens)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        first = self._call(messages)
        if first.ok or first.error_kind not in REPAIRABLE_ERRORS:
            return [first]

        logger.info("groq reply unusable (%s), attempting one repair", first.error_kind)
        repair = self._call(
            [
                *messages,
                {"role": "assistant", "content": first.raw_response or ""},
                {"role": "user", "content": REPAIR_INSTRUCTION},
            ]
        )
        repair.attempts = 2
        # No third attempt. The caller marks the row extraction_failed and the
        # stored raw_response is there to be looked at.
        return [first, repair]

    def _call(self, messages: list[dict[str, str]]) -> LLMOutcome:
        """One request. Every failure mode returns an outcome, never raises.

        The caller logs a cost row for this outcome whether it succeeded or
        not, so an exception escaping here would lose the record of a call we
        actually paid for.
        """
        body = {
            "model": self.model,
            "temperature": 0,
            # A hint, not a guarantee - the response is validated regardless.
            "response_format": {"type": "json_object"},
            "messages": messages,
        }

        started = time.monotonic()
        try:
            with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=body,
                )
        except httpx.TimeoutException:
            return self._failure("timeout", started)
        except httpx.HTTPError as exc:
            logger.warning("groq transport error: %s", type(exc).__name__)
            return self._failure("transport_error", started)

        latency_ms = int((time.monotonic() - started) * 1000)

        if response.status_code == 429:
            return self._failure("rate_limited", started, latency_ms=latency_ms)
        if response.status_code >= 400:
            logger.warning("groq http %s", response.status_code)
            return self._failure(f"http_{response.status_code}", started, latency_ms=latency_ms)

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            usage = payload.get("usage") or {}
        except (ValueError, KeyError, IndexError):
            return self._failure("malformed_envelope", started, latency_ms=latency_ms)

        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)

        extraction, error_kind = parse_extraction(content)
        return LLMOutcome(
            provider=self.name,
            model=self.model,
            ok=extraction is not None,
            extraction=extraction,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            error_kind=error_kind,
            # Kept only when parsing failed, so a human can see what arrived.
            raw_response=None if extraction is not None else content[:4000],
        )

    def _failure(self, kind: str, started: float, latency_ms: int | None = None) -> LLMOutcome:
        return LLMOutcome(
            provider=self.name,
            model=self.model,
            ok=False,
            latency_ms=latency_ms if latency_ms is not None else int((time.monotonic() - started) * 1000),
            error_kind=kind,
        )


def parse_extraction(content: str) -> tuple[Extraction | None, str | None]:
    """Turn the model's text into a validated Extraction, or explain why not.

    Returns (extraction, error_kind). A failure here is an expected outcome,
    which is why it comes back as a value rather than an exception.
    """
    text = _strip_fences(content)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, "invalid_json"

    if not isinstance(data, dict):
        return None, "not_an_object"

    try:
        return Extraction.model_validate(data), None
    except Exception:
        return None, "schema_mismatch"


def _strip_fences(content: str) -> str:
    """Remove ```json fences a model adds despite being told not to."""
    text = content.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
