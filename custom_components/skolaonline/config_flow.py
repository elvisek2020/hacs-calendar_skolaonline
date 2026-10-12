"""Konfigurační dialog integrace Škola OnLine."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import SkolaOnlineAuthError, SkolaOnlineClient, SkolaOnlineError
from .const import CONF_STUDENT_ID, CONF_STUDENT_NAME, DOMAIN
from .students import Student, students_from_user

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class SkolaOnlineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Průvodce přidáním účtu Škola OnLine."""

    VERSION = 1

    def __init__(self) -> None:
        """Připraví stav sdílený mezi kroky průvodce."""
        self._username: str = ""
        self._password: str = ""
        self._students: list[Student] = []

    async def _async_validate(self, username: str, password: str) -> list[Student]:
        """Přihlásí se a vrátí studenty, ke kterým účet vidí rozvrh.

        Studentský účet vrací sám sebe, rodičovský své děti.
        """
        client = SkolaOnlineClient(
            async_get_clientsession(self.hass), username, password
        )
        await client.async_login()
        return students_from_user(await client.async_get_user(), username)

    async def _async_create_for(self, student: Student) -> ConfigFlowResult:
        """Založí config entry pro vybraného studenta."""
        await self.async_set_unique_id(student.student_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=student.name,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_STUDENT_ID: student.student_id,
                CONF_STUDENT_NAME: student.name,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zpracuje ruční přidání účtu."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            try:
                students = await self._async_validate(self._username, self._password)
            except SkolaOnlineAuthError:
                errors["base"] = "invalid_auth"
            except SkolaOnlineError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - poslední záchyt, jinak spadne UI
                _LOGGER.exception("Neočekávaná chyba při přihlášení")
                errors["base"] = "unknown"
            else:
                if not students:
                    errors["base"] = "no_student"
                elif len(students) == 1:
                    return await self._async_create_for(students[0])
                else:
                    self._students = students
                    return await self.async_step_student()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_student(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nechá vybrat dítě, když jich rodičovský účet vidí víc."""
        if user_input is not None:
            chosen = user_input[CONF_STUDENT_ID]
            student = next(item for item in self._students if item.student_id == chosen)
            return await self._async_create_for(student)

        schema = vol.Schema(
            {
                vol.Required(CONF_STUDENT_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=student.student_id, label=student.name
                            )
                            for student in self._students
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )

        return self.async_show_form(step_id="student", data_schema=schema)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Spustí opětovné přihlášení po vypršení údajů."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Vyžádá nové heslo ke stávajícímu účtu."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            username = entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                students = await self._async_validate(username, password)
            except SkolaOnlineAuthError:
                errors["base"] = "invalid_auth"
            except SkolaOnlineError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Neočekávaná chyba při opětovném přihlášení")
                errors["base"] = "unknown"
            else:
                if not students:
                    errors["base"] = "no_student"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_PASSWORD: password}
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )
