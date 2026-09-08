"""Převod odpovědi rozvrhu Škola OnLine na hodiny s absolutním časem.

Modul je záměrně bez závislosti na Home Assistantu, aby se dal testovat
samostatně.

Tvar odpovědi `/v1/timeTable` ověřený proti reálnému serveru::

    {"days": [{"date": "2026-09-07T00:00:00",
               "schedules": [{"scheduledHourId": "C50225000",
                              "beginTime": "2026-09-07T08:00:00",
                              "endTime": "2026-09-07T08:45:00",
                              "hourType": {"id": "ROZVRH", ...},
                              "hourKind": {"id": "", ...},
                              "subject": {"abbrev": "Č", "name": "Český jazyk"},
                              "rooms": [{"abbrev": "7.C", "name": "7.C - 306"}],
                              "teachers": [{"displayName": "Mgr. Nikol Ch."}],
                              "groups": [{"name": "Nj7.C1", "kind": "g"}],
                              "detailHours": [{"name": "1.", "order": 1}]}]}],
     "lessons": [{"id": "C1486", "caption": "1.", ...}]}

Neoficiální API se může změnit, proto se u každého pole zkouší více variant
názvu a nerozpoznané údaje se tiše vynechají.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo
from typing import Any

# Typy hodin, které server vrací v `hourType.id`.
HOUR_TYPE_NORMAL = "ROZVRH"
# Původní hodina, za kterou někdo zaskakuje. Server ji vrací zároveň
# s náhradní hodinou na stejném čase, takže by v kalendáři vznikl duplikát.
HOUR_TYPE_SUBSTITUTED = "SUPLOVANA"
# Náhradní hodina, ta se opravdu koná.
HOUR_TYPE_SUBSTITUTION = "SUPLOVANI"

CANCEL_KEYWORDS = ("odpad", "zrušen", "zrusen", "cancel", "removed")

# U školní akce server vypíše celý učitelský sbor, což v kalendáři nic neříká.
# Běžná hodina má jednoho učitele, dělená výjimečně dva.
MAX_TEACHERS = 3


@dataclass(frozen=True)
class Lesson:
    """Jedna vyučovací hodina s vyřešeným časem."""

    uid: str
    start: datetime
    end: datetime
    subject: str
    subject_abbrev: str | None
    room: str | None
    teacher: str | None
    group: str | None
    hour_caption: str | None
    change: str | None
    is_canceled: bool
    hour_type: str | None


def _first_text(source: Any, *keys: str) -> str | None:
    """Vrátí první neprázdný textový údaj z dictu podle zadaných klíčů."""
    if not isinstance(source, dict):
        return None
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return None


def _texts_from_list(source: Any, key: str, *fields: str) -> list[str]:
    """Vytáhne texty ze seznamu podobjektů, například z `rooms` nebo `teachers`."""
    items = source.get(key) if isinstance(source, dict) else None
    if not isinstance(items, list):
        return []
    return [text for item in items if (text := _first_text(item, *fields))]


def _parse_date(value: Any) -> date | None:
    """Rozparsuje datum dne, ať přijde jako datum nebo jako datetime."""
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
    return None


def _parse_clock(value: Any) -> time | None:
    """Rozparsuje čas, ať přijde jako `HH:MM`, nebo jako celý datetime."""
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    else:
        return parsed.time()

    parts = text.split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2].split(".")[0]) if len(parts) > 2 else 0
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return None
    return time(hour, minute, second)


def _teacher_name(schedule: dict[str, Any]) -> str | None:
    """Vytáhne jméno učitele; server jich u dělených hodin vrací víc."""
    if names := _texts_from_list(
        schedule, "teachers", "displayName", "name", "abbrev"
    ):
        return ", ".join(names) if len(names) <= MAX_TEACHERS else None

    if name := _first_text(
        schedule.get("teacher"), "displayName", "fullName", "name", "abbrev"
    ):
        return name

    return _first_text(schedule, "teacherName", "teacherDisplayName")


def _room_name(schedule: dict[str, Any]) -> str | None:
    """Vytáhne učebnu. Delší `name` nese i číslo dveří, proto má přednost."""
    if names := _texts_from_list(schedule, "rooms", "name", "abbrev"):
        return ", ".join(names)
    return _first_text(schedule.get("room"), "name", "abbrev")


def _group_name(schedule: dict[str, Any]) -> str | None:
    """Vrátí název dělené skupiny, například jazykové.

    Skupiny s `kind` `c` označují celou třídu, což u každé hodiny nic
    neříká, proto se vynechají.
    """
    groups = schedule.get("groups")
    if not isinstance(groups, list):
        return None

    names = [
        name
        for group in groups
        if isinstance(group, dict)
        and group.get("kind") == "g"
        and (name := _first_text(group, "name", "abbrev"))
    ]
    return ", ".join(names) if names else None


def _hour_caption(schedule: dict[str, Any]) -> str | None:
    """Vrátí pořadí hodiny, například `1.`."""
    if captions := _texts_from_list(schedule, "detailHours", "name", "caption"):
        return captions[0]
    return _first_text(schedule, "hourCaption", "caption", "hourLabel")


def _hour_type(schedule: dict[str, Any]) -> str | None:
    """Vrátí identifikátor typu hodiny (`ROZVRH`, `SUPLOVANI`, …)."""
    hour_type = schedule.get("hourType")
    if isinstance(hour_type, dict):
        value = hour_type.get("id")
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _hour_type_label(schedule: dict[str, Any]) -> str | None:
    """Vrátí krátký název typu hodiny, například `Školní akce`.

    Používá se jako náhrada za předmět. Školní akce a podobné bloky mají
    `subject` prázdný a smysluplný název nesou právě tady.
    """
    return _first_text(schedule.get("hourType"), "description", "displayName")


def _change_text(schedule: dict[str, Any]) -> str | None:
    """Vrátí popis změny v rozvrhu, pokud nejde o běžnou hodinu."""
    if _hour_type(schedule) == HOUR_TYPE_NORMAL:
        # Běžná hodina; `hourKind` je v takovém případě prázdný objekt.
        return _first_text(schedule.get("hourKind"), "description", "name")

    for key in ("hourKind", "hourType"):
        if text := _first_text(schedule.get(key), "description", "name"):
            return text

    return _first_text(
        schedule, "changeDescription", "changeType", "substitutionDescription"
    )


def _is_canceled(schedule: dict[str, Any], change: str | None) -> bool:
    """Rozhodne, jestli hodina odpadá úplně."""
    for key in ("isCanceled", "isCancelled", "canceled", "removed"):
        if schedule.get(key) is True:
            return True

    haystack = f"{_hour_type(schedule) or ''} {change or ''}".lower()
    return any(keyword in haystack for keyword in CANCEL_KEYWORDS)


def _drop_superseded(lessons: list[Lesson]) -> list[Lesson]:
    """Zahodí původní hodiny, za které už server vrací náhradu.

    Suplovaná hodina přijde spolu s náhradní na stejném čase. Bez tohohle
    kroku by v kalendáři byly dvě události přes sebe.
    """
    substituted_slots = {
        (lesson.start, lesson.end)
        for lesson in lessons
        if lesson.hour_type == HOUR_TYPE_SUBSTITUTION
    }

    return [
        lesson
        for lesson in lessons
        if not (
            lesson.hour_type == HOUR_TYPE_SUBSTITUTED
            and (lesson.start, lesson.end) in substituted_slots
        )
    ]


def parse_timetable(payload: Any, zone: tzinfo) -> list[Lesson]:
    """Převede odpověď `/v1/timeTable` na seznam hodin řazený podle času."""
    if not isinstance(payload, dict):
        return []

    days = payload.get("days")
    if not isinstance(days, list):
        return []

    lessons: list[Lesson] = []

    for day in days:
        if not isinstance(day, dict):
            continue
        day_date = _parse_date(day.get("date"))
        if day_date is None:
            continue

        schedules = day.get("schedules")
        if not isinstance(schedules, list):
            continue

        for index, schedule in enumerate(schedules):
            if not isinstance(schedule, dict):
                continue

            begin = _parse_clock(schedule.get("beginTime"))
            end = _parse_clock(schedule.get("endTime"))
            if begin is None:
                continue
            if end is None:
                end = begin

            start_dt = datetime.combine(day_date, begin, tzinfo=zone)
            end_dt = datetime.combine(day_date, end, tzinfo=zone)
            if end_dt <= start_dt:
                # Hodina bez rozumného konce by v kalendáři zmizela.
                continue

            subject = schedule.get("subject")
            subject_name = _first_text(subject, "name", "abbrev")
            change = _change_text(schedule)

            if subject_name is None:
                # Krátký název typu hodiny je čitelnější než popis změny,
                # který u školních akcí bývá na několik řádků.
                subject_name = _hour_type_label(schedule) or change or "Hodina"

            hour_id = schedule.get("scheduledHourId") or index
            lessons.append(
                Lesson(
                    uid=f"{day_date.isoformat()}::{hour_id}",
                    start=start_dt,
                    end=end_dt,
                    subject=subject_name,
                    subject_abbrev=_first_text(subject, "abbrev"),
                    room=_room_name(schedule),
                    teacher=_teacher_name(schedule),
                    group=_group_name(schedule),
                    hour_caption=_hour_caption(schedule),
                    change=change,
                    is_canceled=_is_canceled(schedule, change),
                    hour_type=_hour_type(schedule),
                )
            )

    lessons = _drop_superseded(lessons)
    lessons.sort(key=lambda lesson: (lesson.start, lesson.end, lesson.subject.lower()))
    return lessons


def lesson_description(lesson: Lesson) -> str | None:
    """Sestaví čitelný popis hodiny pro kalendář."""
    parts = [
        f"Hodina: {lesson.hour_caption}" if lesson.hour_caption else None,
        f"Učitel: {lesson.teacher}" if lesson.teacher else None,
        f"Skupina: {lesson.group}" if lesson.group else None,
        f"Změna: {lesson.change}" if lesson.change else None,
    ]
    description = "\n".join(part for part in parts if part)
    return description or None


def lesson_summary(lesson: Lesson) -> str:
    """Sestaví název události v kalendáři."""
    if lesson.is_canceled:
        return f"Zrušeno: {lesson.subject}"
    return lesson.subject


__all__ = ["Lesson", "lesson_description", "lesson_summary", "parse_timetable"]
