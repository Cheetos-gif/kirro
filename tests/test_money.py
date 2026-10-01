import pytest

from agent.policies.money import charge_within_limits, mandate_amount_paise, parse_price, validate_ceiling_paise


@pytest.mark.parametrize("text,paise", [
    ("300", 30000), ("Rs 300", 30000), ("max 1,200", 120000), ("8k", 800000), ("2 lakh", 20000000), ("Rs. 450.50", 45050),
    ("up to 300", 30000),
])
def test_single_amount_ok(text, paise):
    p = parse_price(text)
    assert p.status == "ok" and p.paise == paise


@pytest.mark.parametrize("text", [
    "8 to 10k, ideally 8", "around 300", "300 or 400", "between 300 and 400", "300-400", "ideally 300",
])
def test_ranges_and_hedges_are_ambiguous_never_guessed(text):
    p = parse_price(text)
    assert p.status == "ambiguous" and p.paise is None


def test_absent_and_invalid():
    assert parse_price("").status == "absent"
    assert parse_price("whatever works").status == "absent"
    assert parse_price("0").status == "invalid"
    assert parse_price("50 lakh").status == "invalid"


@pytest.mark.parametrize("bad", [True, 12.5, "300", None, -5, 0])
def test_ceiling_must_be_positive_int(bad):
    assert validate_ceiling_paise(bad).status == "invalid"


def test_mandate_and_charge_guard():
    assert mandate_amount_paise(4, 30000) == 120000
    assert charge_within_limits(100000, 4, 30000, 120000)[0]
    assert not charge_within_limits(130000, 4, 30000, 120000)[0]  # above ceiling * group
    assert not charge_within_limits(100000, 4, 30000, 90000)[0]  # above mandate
    assert not charge_within_limits(0, 4, 30000, 120000)[0]
