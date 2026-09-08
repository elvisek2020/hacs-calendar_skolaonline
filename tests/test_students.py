"""Testy zjištění studentů z odpovědi `/v1/user`.

Tvary odpovědí odpovídají reálnému serveru; jména jsou vymyšlená.
"""

from __future__ import annotations

from conftest import load_module

students = load_module("students")

PARENT = {
    "userUID": "C903/C2940066",
    "personID": "C2940066",
    "fullName": "Jan Rodič",
    "detailName": "rodič",
    "userType": "parent",
    "userTypeText": "Rodič",
    "children": [
        {
            "id": "C3203407",
            "displayName": "Matěj Rodič",
            "firstName": "Matěj",
            "lastName": "Rodič",
            "classId": "C1498043",
            "className": "VII.C",
        }
    ],
}

STUDENT = {
    "userUID": "C903/C111",
    "personID": "C111",
    "fullName": "Matěj Rodič",
    "userType": "student",
    "class": {"abbrev": "VII.C", "name": "Sedmá C"},
}


def test_parent_account_returns_children() -> None:
    found = students.students_from_user(PARENT)

    assert found == [students.Student("C3203407", "Matěj Rodič (VII.C)")]


def test_parent_personid_is_never_used() -> None:
    # /v1/timeTable vrací na rodičovské personID HTTP 403.
    found = students.students_from_user(PARENT)

    assert all(item.student_id != PARENT["personID"] for item in found)


def test_parent_with_several_children() -> None:
    payload = PARENT | {
        "children": [
            *PARENT["children"],
            {"id": "C999", "displayName": "Anna Rodič", "className": "III.A"},
        ]
    }

    found = students.students_from_user(payload)

    assert [item.name for item in found] == [
        "Matěj Rodič (VII.C)",
        "Anna Rodič (III.A)",
    ]


def test_parent_without_children_yields_nothing() -> None:
    assert students.students_from_user(PARENT | {"children": []}) == []
    assert students.students_from_user({"userType": "parent"}) == []


def test_student_account_returns_itself_with_class() -> None:
    found = students.students_from_user(STUDENT)

    assert found == [students.Student("C111", "Matěj Rodič (VII.C)")]


def test_student_without_class_still_works() -> None:
    found = students.students_from_user({"personID": "C111", "fullName": "Matěj"})

    assert found == [students.Student("C111", "Matěj")]


def test_fallback_name_is_used_when_server_sends_none() -> None:
    found = students.students_from_user({"personID": "C111"}, "prihlasovaci_jmeno")

    assert found[0].name == "prihlasovaci_jmeno"


def test_child_without_id_is_skipped() -> None:
    payload = {"children": [{"displayName": "Bez ID"}, None], "userType": "parent"}

    assert students.students_from_user(payload) == []


def test_malformed_payloads_do_not_raise() -> None:
    assert students.students_from_user(None) == []
    assert students.students_from_user({}) == []
    assert students.students_from_user("nope") == []
