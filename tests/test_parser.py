"""Testy převodu rozvrhu Škola OnLine na hodiny kalendáře.

Fixture kopíruje skutečný tvar odpovědi `/v1/timeTable` ověřený proti
reálnému serveru; jména osob jsou vymyšlená.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from conftest import load_module

parser = load_module("parser")

PRAGUE = ZoneInfo("Europe/Prague")


def hour(
    hour_id: str,
    begin: str,
    end: str,
    subject: tuple[str, str],
    *,
    room: str = "7.C - 306",
    teacher: str = "Mgr. Jana Nováková",
    caption: str = "1.",
    hour_type: tuple[str, str] = ("ROZVRH", "Rozvrh"),
    hour_kind: tuple[str, str, str] = ("", "", ""),
    group: tuple[str, str] | None = None,
) -> dict:
    """Sestaví jeden `schedule` ve tvaru, jaký vrací server."""
    groups = [
        {
            "id": "C1498043",
            "name": "VII.C",
            "kind": "c",
            "classId": "C1498043",
            "className": "VII.C",
        }
    ]
    if group is not None:
        groups.append(
            {
                "id": "C1510525",
                "name": group[0],
                "kind": group[1],
                "classId": "C1498043",
                "className": "VII.C",
            }
        )

    return {
        "scheduledHourId": hour_id,
        "scheduledHourOrder": 1,
        "beginTime": begin,
        "endTime": end,
        "hourType": {"id": hour_type[0], "description": hour_type[1]},
        "hourKind": {
            "id": hour_kind[0],
            "name": hour_kind[1],
            "description": hour_kind[2],
        },
        "subject": {
            "id": "C131038",
            "abbrev": subject[0],
            "name": subject[1],
            "kind": "p",
        },
        "groups": groups,
        "rooms": [{"id": "C21943", "abbrev": "7.C", "name": room}],
        "teachers": [
            {"id": "C3448479", "abbrev": "Nvk", "displayName": teacher}
        ],
        "detailHours": [
            {"id": "C1486", "name": caption, "order": 1, "timeFrom": "08:00:00"}
        ],
        "orderlyService": [],
    }


TIMETABLE = {
    "days": [
        {
            "schoolYearId": "C32725",
            "date": "2026-09-07T00:00:00",
            "schedules": [
                hour(
                    "C50225011",
                    "2026-09-07T08:55:00",
                    "2026-09-07T09:40:00",
                    ("M", "Matematika"),
                    caption="2.",
                    teacher="Mgr. Petr Svoboda",
                ),
                hour(
                    "C50225000",
                    "2026-09-07T08:00:00",
                    "2026-09-07T08:45:00",
                    ("Č", "Český jazyk a literatura"),
                    caption="1.",
                ),
            ],
        },
        {
            "schoolYearId": "C32725",
            "date": "2026-09-09T00:00:00",
            "schedules": [
                # Původní hodina, za kterou někdo zaskakuje.
                hour(
                    "C50225170",
                    "2026-09-09T11:50:00",
                    "2026-09-09T12:35:00",
                    ("Nj", "Německý jazyk"),
                    caption="5.",
                    teacher="Mgr. Adéla Dohnalová",
                    hour_type=("SUPLOVANA", "Suplovaná"),
                    group=("Nj7.C1", "g"),
                ),
                # Náhradní hodina na stejném čase.
                hour(
                    "C50310821",
                    "2026-09-09T11:50:00",
                    "2026-09-09T12:35:00",
                    ("Nj", "Německý jazyk"),
                    caption="5.",
                    teacher="Mgr. Marta Chludilová",
                    hour_type=("SUPLOVANI", "Suplování"),
                    hour_kind=("SUPLOVANI", "Suplování", "Suplování předmětu"),
                    group=("Nj7.C1", "g"),
                ),
            ],
        },
    ],
    "lessons": [
        {
            "id": "C1486",
            "caption": "1.",
            "beginTime": "1900-01-01T08:00:00",
            "endTime": "1900-01-01T08:45:00",
        }
    ],
}


def test_lessons_are_sorted_by_start() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)

    assert [lesson.subject for lesson in lessons] == [
        "Český jazyk a literatura",
        "Matematika",
        "Německý jazyk",
    ]


def test_datetime_valued_times_resolve_to_local_time() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)

    assert lessons[0].start == datetime(2026, 9, 7, 8, 0, tzinfo=PRAGUE)
    assert lessons[0].end == datetime(2026, 9, 7, 8, 45, tzinfo=PRAGUE)


def test_room_is_read_from_rooms_list() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)

    assert lessons[0].room == "7.C - 306"


def test_teacher_is_read_from_teachers_list() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)

    assert lessons[0].teacher == "Mgr. Jana Nováková"
    assert lessons[1].teacher == "Mgr. Petr Svoboda"


def test_hour_caption_comes_from_detail_hours() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)

    assert [lesson.hour_caption for lesson in lessons] == ["1.", "2.", "5."]


def test_substituted_lesson_is_replaced_by_the_substitution() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)
    german = [lesson for lesson in lessons if lesson.subject == "Německý jazyk"]

    # Server vrací obě hodiny na stejném čase; v kalendáři smí zůstat jedna.
    assert len(german) == 1
    assert german[0].teacher == "Mgr. Marta Chludilová"
    assert german[0].change == "Suplování předmětu"
    assert german[0].is_canceled is False


def test_only_split_groups_are_reported() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)

    # Celá třída (kind "c") o hodině nic neříká, dělená skupina ano.
    assert lessons[0].group is None
    assert lessons[2].group == "Nj7.C1"


def test_normal_lesson_has_no_change_note() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)

    assert lessons[0].change is None
    assert parser.lesson_description(lessons[0]) == (
        "Hodina: 1.\nUčitel: Mgr. Jana Nováková"
    )


def test_description_includes_group_and_change() -> None:
    lessons = parser.parse_timetable(TIMETABLE, PRAGUE)

    assert parser.lesson_description(lessons[2]) == (
        "Hodina: 5.\n"
        "Učitel: Mgr. Marta Chludilová\n"
        "Skupina: Nj7.C1\n"
        "Změna: Suplování předmětu"
    )


def test_substituted_lesson_survives_without_replacement() -> None:
    payload = {
        "days": [
            {
                "date": "2026-09-09T00:00:00",
                "schedules": [
                    hour(
                        "C1",
                        "2026-09-09T11:50:00",
                        "2026-09-09T12:35:00",
                        ("Nj", "Německý jazyk"),
                        hour_type=("SUPLOVANA", "Suplovaná"),
                    )
                ],
            }
        ]
    }

    lessons = parser.parse_timetable(payload, PRAGUE)

    assert len(lessons) == 1
    assert lessons[0].change == "Suplovaná"
    assert lessons[0].is_canceled is False


def test_school_event_is_named_by_hour_type() -> None:
    # Školní akce má prázdný `subject`; použitelný název je v `hourType`,
    # zatímco `hourKind.description` je několikařádkový úřední text.
    payload = {
        "days": [
            {
                "date": "2026-09-01T00:00:00",
                "schedules": [
                    {
                        "scheduledHourId": "C1",
                        "beginTime": "2026-09-01T08:00:00",
                        "endTime": "2026-09-01T08:45:00",
                        "subject": {},
                        "hourType": {
                            "id": "SKOLNI_AKCE",
                            "description": "Školní akce",
                            "displayName": "AKCE",
                        },
                        "hourKind": {
                            "id": "S_NAHRADOU_SKOL_AKCE",
                            "name": "S náhradou",
                            "description": "Školní akce bez náhradního vyučování",
                        },
                        "rooms": [],
                        "groups": [],
                        # Server u akce vypíše celý učitelský sbor.
                        "teachers": [
                            {"displayName": f"Učitel {index}"} for index in range(25)
                        ],
                        "detailHours": [{"name": "1.", "order": 1}],
                    }
                ],
            }
        ]
    }

    lesson = parser.parse_timetable(payload, PRAGUE)[0]

    assert lesson.subject == "Školní akce"
    assert lesson.teacher is None
    assert lesson.change == "Školní akce bez náhradního vyučování"


def test_cancelled_lesson_is_flagged_and_prefixed() -> None:
    payload = {
        "days": [
            {
                "date": "2026-09-09T00:00:00",
                "schedules": [
                    hour(
                        "C1",
                        "2026-09-09T11:50:00",
                        "2026-09-09T12:35:00",
                        ("F", "Fyzika"),
                        hour_type=("ODPADLA", "Odpadlá hodina"),
                    )
                ],
            }
        ]
    }

    lessons = parser.parse_timetable(payload, PRAGUE)

    assert lessons[0].is_canceled is True
    assert parser.lesson_summary(lessons[0]) == "Zrušeno: Fyzika"


def test_uid_is_stable_per_day_and_hour() -> None:
    first = parser.parse_timetable(TIMETABLE, PRAGUE)
    second = parser.parse_timetable(TIMETABLE, PRAGUE)

    assert [lesson.uid for lesson in first] == [lesson.uid for lesson in second]
    assert first[0].uid == "2026-09-07::C50225000"


def test_short_clock_times_are_still_accepted() -> None:
    payload = {
        "days": [
            {
                "date": "2026-09-10",
                "schedules": [
                    {
                        "scheduledHourId": "x",
                        "beginTime": "08:00",
                        "endTime": "08:45",
                        "subject": {"name": "Tělesná výchova"},
                        "rooms": [{"name": "Tělocvična"}],
                    }
                ],
            }
        ]
    }

    lessons = parser.parse_timetable(payload, PRAGUE)

    assert lessons[0].start == datetime(2026, 9, 10, 8, 0, tzinfo=PRAGUE)
    assert lessons[0].room == "Tělocvična"


def test_subject_falls_back_when_missing() -> None:
    payload = {
        "days": [
            {
                "date": "2026-09-10",
                "schedules": [{"beginTime": "08:00", "endTime": "08:45"}],
            }
        ]
    }

    assert parser.parse_timetable(payload, PRAGUE)[0].subject == "Hodina"


def test_malformed_payloads_do_not_raise() -> None:
    assert parser.parse_timetable(None, PRAGUE) == []
    assert parser.parse_timetable({}, PRAGUE) == []
    assert parser.parse_timetable({"days": "nope"}, PRAGUE) == []
    assert parser.parse_timetable({"days": [None, {"date": "x"}]}, PRAGUE) == []


def test_lesson_without_usable_time_is_skipped() -> None:
    payload = {
        "days": [
            {
                "date": "2026-09-10",
                "schedules": [
                    {"beginTime": "", "endTime": "08:45", "subject": {"name": "M"}},
                    {"beginTime": "08:00", "endTime": "07:00"},
                ],
            }
        ]
    }

    assert parser.parse_timetable(payload, PRAGUE) == []
