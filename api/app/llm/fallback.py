"""A scorer that needs no model, no key and no network.

This exists so the demo cannot be ruined by someone else's free tier having a
bad afternoon. It runs when Groq is unconfigured, down, or rate-limited, and
it always produces a number.

It is deliberately crude and deliberately explainable: keyword overlap between
the profile's skills and the posting, plus three hard checks. Every rationale
line it writes is something a human can verify by reading the posting.
"""

import re
import time

from app.llm.base import Extraction, LLMOutcome, LLMProvider, ProfileSummary

# A small vocabulary is enough to recognise most of what a backend posting
# asks for. Anything in the user's own profile is added at match time, so the
# list does not have to be exhaustive to score that user well.
COMMON_SKILLS: frozenset[str] = frozenset(
    {
        "python", "java", "javascript", "typescript", "go", "golang", "rust", "ruby",
        "php", "c#", "c++", ".net", "kotlin", "swift", "scala", "elixir",
        "django", "flask", "fastapi", "rails", "spring", "express", "node.js", "nodejs",
        "react", "vue", "angular", "next.js", "svelte",
        "postgres", "postgresql", "mysql", "sqlite", "mongodb", "redis", "cassandra",
        "elasticsearch", "dynamodb", "sql", "nosql",
        "docker", "kubernetes", "terraform", "ansible", "jenkins", "github actions",
        "aws", "azure", "gcp", "linux", "nginx", "ci/cd",
        "celery", "rabbitmq", "kafka", "airflow", "dbt", "spark", "snowflake",
        "rest", "graphql", "grpc", "microservices", "websockets",
        "pytest", "git", "agile", "scrum", "html", "css", "tailwind",
        "machine learning", "pandas", "numpy", "pytorch", "tensorflow",
    }
)

# Without this, a profile saying "Postgres" scores zero against a posting
# saying "PostgreSQL", which is the kind of miss that makes the whole fallback
# look broken. Keys and values are both lowercase.
SKILL_ALIASES: dict[str, str] = {
    "postgresql": "postgres",
    "golang": "go",
    "nodejs": "node.js",
    "node": "node.js",
    "js": "javascript",
    "ts": "typescript",
    "k8s": "kubernetes",
    "gcp": "google cloud",
    "ci/cd": "ci",
    "rest": "rest api",
    "restful": "rest api",
}


def canonical(skill: str) -> str:
    """Fold known spellings of the same skill onto one name."""
    lowered = skill.strip().lower()
    return SKILL_ALIASES.get(lowered, lowered)


SENIORITY_HINTS = [
    ("lead", ("principal", "staff", "lead", "head of", "architect")),
    ("senior", ("senior", "sr.", "sr ")),
    ("junior", ("junior", "jr.", "jr ", "graduate", "entry level", "entry-level", "intern")),
    ("mid", ("mid-level", "mid level", "intermediate")),
]

# Ordered: an explicit "no remote" must beat the word "remote" appearing.
REMOTE_HINTS = [
    (
        "onsite",
        ("no remote", "not remote", "strictly onsite", "on-site only", "onsite only", "in office"),
    ),
    ("hybrid", ("hybrid",)),
    ("remote", ("fully remote", "100% remote", "remote-first", "work from home", "remote")),
    ("onsite", ("onsite", "on-site")),
]

YEARS_PATTERN = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?years?", re.I)

# Weighting: skills dominate, because that is what a candidate actually screens
# on. The remaining 30 covers experience and workplace fit.
SKILL_WEIGHT = 70
YEARS_WEIGHT = 20
LOCATION_WEIGHT = 10

# A gap this large is a blocker rather than a deduction - the brief's own rule.
YEARS_GAP_BLOCKER = 2


def _token_present(needle: str, haystack: str) -> bool:
    """Whole-token match that survives c++, c#, .net and node.js."""
    pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def _find_skills(text_lower: str, profile_skills: list[str]) -> list[str]:
    vocabulary = set(COMMON_SKILLS) | {s.lower() for s in profile_skills}
    found = [skill for skill in vocabulary if _token_present(skill, text_lower)]
    # Longest first, so "postgresql" reads before "sql" in the output.
    return sorted(found, key=lambda s: (-len(s), s))[:30]


def _detect(text_lower: str, hints: list[tuple[str, tuple[str, ...]]], default: str) -> str:
    for value, needles in hints:
        if any(needle in text_lower for needle in needles):
            return value
    return default


def _min_years(text: str) -> int:
    matches = YEARS_PATTERN.findall(text)
    years = [int(m) for m in matches if int(m) <= 40]
    return min(years) if years else 0


def _title_and_company(text: str) -> tuple[str, str]:
    """Best effort from the first few lines. Empty beats invented."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", ""

    first = lines[0]
    company = ""

    at_match = re.search(r"\s+at\s+([A-Z][\w&.\- ]{1,40})", first)
    if at_match:
        company = at_match.group(1).strip().rstrip(".,")
        title = first[: at_match.start()].strip()
    else:
        title = re.split(r"\s+[-–|]\s+", first)[0].strip()

    if not company:
        for line in lines[1:4]:
            company_match = re.match(r"(?:company|employer)\s*:\s*(.+)", line, re.I)
            if company_match:
                company = company_match.group(1).strip()
                break

    return title[:120], company[:120]


class FallbackScorer(LLMProvider):
    """Keyword-overlap scoring. Same interface, no network."""

    name = "fallback"
    model = "keyword-overlap-v1"

    def extract_and_score(self, posting_text: str, profile: ProfileSummary) -> list[LLMOutcome]:
        started = time.monotonic()
        lowered = posting_text.lower()

        required = _find_skills(lowered, profile.skills)
        # Compared on canonical names so "Postgres" in the profile matches
        # "PostgreSQL" in the posting, but reported using the posting's own
        # spelling.
        have = {canonical(s) for s in profile.skills}
        matched = [s for s in required if canonical(s) in have]
        missing = [s for s in required if canonical(s) not in have]

        seniority = _detect(lowered, SENIORITY_HINTS, "unknown")
        remote = _detect(lowered, REMOTE_HINTS, "unknown")
        min_years = _min_years(posting_text)
        title, company = _title_and_company(posting_text)

        skill_score = (SKILL_WEIGHT * len(matched) / len(required)) if required else 0.0

        years_gap = max(0, min_years - profile.years_experience)
        if years_gap == 0:
            years_score = float(YEARS_WEIGHT)
        elif years_gap <= YEARS_GAP_BLOCKER:
            years_score = YEARS_WEIGHT * (1 - years_gap / (YEARS_GAP_BLOCKER + 1))
        else:
            years_score = 0.0

        wants_remote = any("remote" in loc.lower() for loc in profile.locations)
        location_ok = remote in ("remote", "hybrid", "unknown") or not wants_remote
        location_score = float(LOCATION_WEIGHT) if location_ok else 0.0

        score = int(round(skill_score + years_score + location_score))

        blockers: list[str] = []
        if years_gap > YEARS_GAP_BLOCKER:
            blockers.append(f"Needs {min_years} years; profile has {profile.years_experience}.")
        if required and not matched:
            blockers.append("None of the posting's listed skills appear in the profile.")
        if not location_ok:
            blockers.append(f"Posting is {remote}; profile targets remote work.")

        # The brief's rule: a posting that cannot be applied for scores low
        # regardless of what else matches.
        if blockers:
            score = min(score, 29)

        rationale: list[str] = []
        if matched:
            rationale.append("Profile matches: " + ", ".join(matched[:6]) + ".")
        if missing:
            rationale.append("Posting also asks for: " + ", ".join(missing[:6]) + ".")
        rationale.append(
            f"Requires {min_years} years; profile has {profile.years_experience}."
            if min_years
            else f"No explicit experience requirement; profile has {profile.years_experience} years."
        )

        extraction = Extraction(
            title=title,
            company=company,
            seniority=seniority,
            required_skills=required,
            min_years=min_years,
            location="",
            remote=remote,
            fit_score=score,
            rationale=rationale,
            blockers=blockers,
        )

        return [
            LLMOutcome(
                provider=self.name,
                model=self.model,
                ok=True,
                extraction=extraction,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        ]
