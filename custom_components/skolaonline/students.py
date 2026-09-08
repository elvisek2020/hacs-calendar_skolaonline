"""Zjištění studentů, ke kterým účet Škola OnLine vidí rozvrh.

Modul je bez závislosti na Home Assistantu, aby se dal testovat samostatně.

Odpověď `/v1/user` má dva tvary. Studentský účet popisuje sám sebe
(`personID`, `fullName`). Rodičovský účet má `userType: "parent"` a děti
v poli `children`; jeho vlastní `personID` žádný rozvrh nemá a
`/v1/timeTable` by na něj odpověděl HTTP 403.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

USER_TYPE_PARENT = "parent"


@dataclass(frozen=True)
class Student:
    """Student, ke kterému účet vidí rozvrh."""

    student_id: str
    name: str


def _child_to_student(child: Any) -> Student | None:
    """Převede jednu položku z `children` na studenta."""
    if not isinstance(child, dict):
        return None

    child_id = child.get("id")
    if not child_id:
        return None

    name = child.get("displayName") or child.get("firstName") or str(child_id)
    if class_name := child.get("className"):
        name = f"{name} ({class_name})"

    return Student(str(child_id), str(name))


def students_from_user(user: Any, fallback_name: str = "") -> list[Student]:
    """Vrátí studenty, jejichž rozvrh lze pod tímto účtem načíst."""
    if not isinstance(user, dict):
        return []

    children = user.get("children")
    if isinstance(children, list) and children:
        students = [
            student
            for child in children
            if (student := _child_to_student(child)) is not None
        ]
        if students:
            return students

    if user.get("userType") == USER_TYPE_PARENT:
        # Rodič bez použitelných dětí; na vlastní personID rozvrh nedostane.
        return []

    student_id = user.get("personID") or user.get("personId")
    if not student_id:
        return []

    name = user.get("fullName") or fallback_name or str(student_id)
    student_class = user.get("class")
    if isinstance(student_class, dict) and (
        class_name := student_class.get("abbrev") or student_class.get("name")
    ):
        name = f"{name} ({class_name})"

    return [Student(str(student_id), str(name))]
