from datetime import date

from agent.state import fields as F

TODAY = date(2026, 10, 1)
CAT = [
    {"event_id": "a", "name": "Badminton", "aliases": ["badminton"], "generic_aliases": ["court"]},
    {"event_id": "t", "name": "Tennis", "aliases": ["tennis"], "generic_aliases": ["court"]},
]


def test_any_network_is_not_a_date():
    assert F.parse_weekday_date("any network works", TODAY).status == "absent"


def test_weekdays_english_and_hinglish():
    assert F.parse_weekday_date("Saturday", TODAY).value == "2026-10-03"
    assert F.parse_weekday_date("Shanivaar ko", TODAY).value == "2026-10-03"
    assert F.parse_weekday_date("kal", TODAY).value == "2026-10-02"
    assert F.parse_weekday_date("2026-09-01", TODAY).status == "invalid"
    assert F.parse_weekday_date("saturday or sunday", TODAY).status == "ambiguous"


def test_group_size():
    assert F.parse_group_size("4 people").value == 4
    assert F.parse_group_size("char log").value == 4
    assert F.parse_group_size("for 2").value == 2
    assert F.parse_group_size("40 people").status == "invalid"
    assert F.parse_group_size("4", bare_ok=True).value == 4
    assert F.parse_group_size("4").status == "absent"


def test_event_generic_word_is_ambiguous_not_guessed():
    p = F.parse_event("court chahiye", CAT)
    assert p.status == "ambiguous" and len(p.extra["options"]) == 2
    assert F.parse_event("tennis court", CAT).value == "t"
    assert F.parse_event("something else", CAT).status == "absent"


def test_time_window_does_not_eat_price_ranges():
    assert F.parse_time_window("7-9 am").value == {"start_hour_min": 7, "start_hour_max": 9}
    assert F.parse_time_window("budget 8 to 10k").status == "absent"
