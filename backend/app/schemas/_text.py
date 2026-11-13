"""Text sanitisation helpers shared by schema validators (leaf module, ruling R9).

Lives in the schema layer so that schemas never import from app.domain.
"""

import re

MAX_TITLE_LENGTH = 80

_TAGS = re.compile(r"<[^>]*>")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_SPACE = re.compile(r"\s+")


def sanitize_title(s: str) -> str:
    """Strip HTML tags and control chars, collapse whitespace, trim, cap at 80 chars."""
    s = _TAGS.sub("", s)
    s = _CONTROL.sub(" ", s)
    s = _SPACE.sub(" ", s).strip()
    return s[:MAX_TITLE_LENGTH].rstrip()
