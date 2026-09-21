"""The one prompt this project sends, and the text budgeting around it.

One prompt, one output shape. Everything the model is allowed to say is in
the schema; everything it is asked to do is here.
"""

import json

from app.llm.base import MAX_BLOCKER_ITEMS, MAX_RATIONALE_ITEMS, ProfileSummary

# Rough conversion used to keep input under the configured token ceiling.
# gpt-oss has no public tokenizer we can pin, so this approximates the usual
# ~4 characters per token and errs on the side of sending less.
CHARS_PER_TOKEN = 4

SYSTEM_PROMPT = f"""You extract structured data from job postings and score how well \
they match one candidate.

Return ONLY a JSON object with exactly these keys:
  title            string  - the role title, "" if absent
  company          string  - the hiring company, "" if absent
  seniority        string  - one of: junior, mid, senior, lead, unknown
  required_skills  array   - technologies and skills the posting requires
  min_years        integer - minimum years of experience required, 0 if unstated
  location         string  - the location as written, "" if absent
  remote           string  - one of: onsite, hybrid, remote, unknown
  fit_score        integer - 0 to 100, how well this candidate fits
  rationale        array   - at most {MAX_RATIONALE_ITEMS} short strings explaining the score
  blockers         array   - at most {MAX_BLOCKER_ITEMS} short strings naming hard mismatches

Scoring guidance:
  - Weigh overlap between the candidate's skills and the required skills most heavily.
  - A years-of-experience gap of more than two years is a blocker, not a deduction.
  - A location or remote-mode conflict is a blocker.
  - A posting the candidate clearly cannot apply for scores below 30, whatever else matches.

Write the rationale for the candidate, in plain language, naming specifics rather \
than generalities. Do not invent requirements that are not in the posting.
Output JSON only, with no commentary and no markdown fences."""


def build_user_prompt(posting_text: str, profile: ProfileSummary, max_input_tokens: int) -> str:
    """Assemble the candidate side and the posting into one message.

    The posting is truncated, not the profile: the profile is small and is the
    thing being matched against, so losing part of it would silently change
    the score.
    """
    candidate = {
        "skills": profile.skills,
        "years_experience": profile.years_experience,
        "target_roles": profile.target_roles,
        "locations": profile.locations,
    }
    # A short CV extract helps the rationale read specifically; the full CV is
    # neither needed nor sent.
    cv_extract = profile.cv_text.strip()[:1500]

    header = (
        "CANDIDATE PROFILE:\n"
        + json.dumps(candidate, ensure_ascii=False)
        + (f"\n\nCV EXTRACT:\n{cv_extract}" if cv_extract else "")
        + "\n\nJOB POSTING:\n"
    )

    budget_chars = max_input_tokens * CHARS_PER_TOKEN
    remaining = budget_chars - len(header) - len(SYSTEM_PROMPT)
    posting = truncate(posting_text, max(500, remaining))
    return header + posting


def truncate(text: str, max_chars: int) -> str:
    """Cut to a character budget, marking the cut so the model knows."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[posting truncated]"
