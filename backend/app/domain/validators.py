"""Text validation for free-text input (chat questions, goal descriptions).

Anything a user types into the coach is sent to an LLM. If they paste their SSN, it
must be stopped here, before it ever leaves our server.

SSN format rules (Social Security Administration): area 000, 666 and 900-999 are never
issued; group 00 is never issued; serial 0000 is never issued.
"""

import re

# 9 digits, optionally split 3-2-4 by dashes or spaces, not part of a longer number.
_SSN_IN_TEXT = re.compile(r"(?<!\d)(\d{3})[- ]?(\d{2})[- ]?(\d{4})(?!\d)")


def is_valid_ssn(area: str, group: str, serial: str) -> bool:
    return (
        area not in ("000", "666")
        and not area.startswith("9")
        and group != "00"
        and serial != "0000"
    )


def contains_ssn(text: str) -> bool:
    return any(is_valid_ssn(*m) for m in _SSN_IN_TEXT.findall(text))


def reject_ssn(text: str) -> str:
    """Pydantic-friendly validator: raise ValueError (-> HTTP 422) if text has an SSN."""
    if contains_ssn(text):
        raise ValueError(
            "Please don't share your Social Security number. Capital Insight never needs it."
        )
    return text
