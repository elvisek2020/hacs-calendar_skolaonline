"""Koordinátor stahování rozvrhu ze Škola OnLine."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SkolaOnlineAuthError, SkolaOnlineClient, SkolaOnlineError
from .const import DAYS_AFTER, DAYS_BEFORE, DOMAIN, UPDATE_INTERVAL
from .parser import Lesson, parse_timetable

_LOGGER = logging.getLogger(__name__)

type SkolaOnlineConfigEntry = ConfigEntry[SkolaOnlineCoordinator]


class SkolaOnlineCoordinator(DataUpdateCoordinator[list[Lesson]]):
    """Stahuje rozvrh a drží ho pro kalendářovou entitu."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SkolaOnlineConfigEntry,
        client: SkolaOnlineClient,
        student_id: str,
    ) -> None:
        """Inicializuje koordinátor."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self.student_id = student_id

    async def _async_update_data(self) -> list[Lesson]:
        """Načte rozvrh pro aktuální a příští týden."""
        now = dt_util.now()
        today = now.date()
        date_from = today - timedelta(days=DAYS_BEFORE)
        date_to = today + timedelta(days=DAYS_AFTER)

        try:
            payload = await self.client.async_get_timetable(
                self.student_id, date_from, date_to
            )
        except SkolaOnlineAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SkolaOnlineError as err:
            raise UpdateFailed(str(err)) from err

        lessons = parse_timetable(payload, now.tzinfo or dt_util.UTC)
        _LOGGER.debug("Načteno %d hodin rozvrhu", len(lessons))
        return lessons
