"""Input validation rules, as plain functions so they're easy to test and reuse.

Real SSN rules (Social Security Administration): the last 4 digits (the "serial")
are never 0000. We only ever handle the last 4 digits: collecting full SSNs would
add risk without adding any feature (data minimization).
"""

import re

_SSN_LAST4 = re.compile(r"\d{4}")


def validate_ssn_last4(value: str) -> str:
    value = value.strip()
    if not _SSN_LAST4.fullmatch(value):
        raise ValueError("must be exactly 4 digits")
    if value == "0000":
        raise ValueError("0000 is never issued as an SSN serial number")
    return value
