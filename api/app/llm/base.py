"""The provider interface and the one output shape the model must produce.

Abstracted from the start, which is the single exception to this project's
"two implementations before an interface" rule: swapping providers is a live
risk (Groq retired the Llama 3.x chat models during this build), and there is
always a second implementation anyway - the deterministic fallback scorer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Parse failures are worth one corrective retry. Transport failures are not:
# a 429 retried immediately is still a 429, and that is what the deterministic
# fallback scorer exists for.
REPAIRABLE_ERRORS = frozenset({"invalid_json", "not_an_object", "schema_mismatch"})

Seniority = Literal["junior", "mid", "senior", "lead", "unknown"]
RemoteMode = Literal["onsite", "hybrid", "remote", "unknown"]

MAX_RATIONALE_ITEMS = 3
MAX_BLOCKER_ITEMS = 5


class Extraction(BaseModel):
    """Exactly what the model is allowed to return.

    Every constraint here is enforced on our side. Provider-side JSON mode is a
    hint, not a guarantee, and a model's arithmetic is never trusted.
    """

    title: str = ""
    company: str = ""
    seniority: Seniority = "unknown"
    required_skills: list[str] = Field(default_factory=list)
    min_years: int = 0
    location: str = ""
    remote: RemoteMode = "unknown"
    fit_score: int = 0
    rationale: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    @field_validator("fit_score")
    @classmethod
    def clamp_score(cls, value: int) -> int:
        """Clamp rather than reject: a 105 is a usable 100, not a failed call."""
        return max(0, min(100, value))

    @field_validator("min_years")
    @classmethod
    def clamp_years(cls, value: int) -> int:
        return max(0, min(70, value))

    @field_validator("rationale")
    @classmethod
    def cap_rationale(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()][:MAX_RATIONALE_ITEMS]

    @field_validator("blockers")
    @classmethod
    def cap_blockers(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()][:MAX_BLOCKER_ITEMS]

    @field_validator("required_skills")
    @classmethod
    def tidy_skills(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for skill in value:
            cleaned = skill.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                out.append(cleaned)
        return out[:30]


@dataclass
class ProfileSummary:
    """The candidate side of the comparison, flattened for the prompt.

    Deliberately not the ORM object: this is the only shape that reaches the
    provider, which makes it obvious what leaves the building.
    """

    skills: list[str] = field(default_factory=list)
    years_experience: int = 0
    target_roles: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    cv_text: str = ""


@dataclass
class LLMOutcome:
    """The result of one attempt, success or failure.

    A parse failure is an ordinary outcome carried in this object, not an
    exception that kills the worker - so the caller can log the cost row and
    decide whether to retry.
    """

    provider: str
    model: str
    ok: bool
    extraction: Extraction | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    error_kind: str | None = None
    raw_response: str | None = None
    attempts: int = 1


class LLMProvider(ABC):
    """One narrow job: posting text plus a profile, in; validated JSON, out."""

    name: str
    model: str

    @abstractmethod
    def extract_and_score(self, posting_text: str, profile: ProfileSummary) -> LLMOutcome:
        raise NotImplementedError


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    """Cost of one call from the per-model rates in config.

    Groq's free tier bills nothing, so these rates are 0.0 and this returns
    0.0. The number is logged anyway: the discipline of measuring is the point,
    and the day the rate stops being zero, nothing else has to change.
    """
    from app.config import settings

    return (
        prompt_tokens * settings.llm_input_cost_per_mtok_usd
        + completion_tokens * settings.llm_output_cost_per_mtok_usd
    ) / 1_000_000
