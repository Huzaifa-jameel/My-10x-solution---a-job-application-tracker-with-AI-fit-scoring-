"""Turning a pasted posting into something storable.

Deliberately boring. Cleaning happens before hashing so that the same posting
pasted twice - once with stray blank lines or non-breaking spaces from a
browser copy - produces the same content_hash and is recognised as a duplicate.
"""

import hashlib
import re

# Copying from a job board drags in non-breaking spaces, zero-width joiners and
# assorted invisible junk. Normalise them to ordinary spaces before hashing.
_INVISIBLE = dict.fromkeys(map(ord, "\u00a0\u2007\u202f\u200b\u200c\u200d\ufeff"), " ")


def clean_text(raw: str) -> str:
    """Normalise whitespace without touching the words themselves."""
    text = raw.translate(_INVISIBLE)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of spaces/tabs, then runs of blank lines.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def content_hash(cleaned_text: str) -> str:
    """sha256 of the cleaned text, hex encoded.

    Identifies a re-ingest of the same posting and, later, keys the extraction
    cache so an identical posting costs no LLM call.
    """
    return hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
