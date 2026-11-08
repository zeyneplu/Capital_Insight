import pytest

from app.domain.validators import contains_ssn


@pytest.mark.parametrize(
    "text",
    ["my ssn is 123-45-6789", "123 45 6789 please", "use 123456789", "x:123-45-6789."],
)
def test_detects_ssn(text):
    assert contains_ssn(text)


@pytest.mark.parametrize(
    "text",
    [
        "How do I pay off $6,789 faster?",
        "call 972-555-01234",  # 11 digits: a phone-like number, not an SSN
        "000-12-3456",  # area 000 is never issued
        "666-12-3456",  # area 666 is never issued
        "912-34-5678",  # 9xx areas are never issued
        "123-00-4567",  # group 00 is never issued
        "123-45-0000",  # serial 0000 is never issued
        "account 1234567890",  # 10 digits
    ],
)
def test_ignores_non_ssn_numbers(text):
    assert not contains_ssn(text)
