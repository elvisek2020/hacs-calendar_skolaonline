"""Kalendář rozvrhu ze Škola OnLine."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, CONF_STUDENT_NAME, DOMAIN, MANUFACTURER
from .coordinator import SkolaOnlineConfigEntry, SkolaOnlineCoordinator
from .parser import Lesson, lesson_description, lesson_summary


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkolaOnlineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Vytvoří kalendářovou entitu rozvrhu."""
    async_add_entities([SkolaOnlineTimetableCalendar(entry.runtime_data, entry)])


def _to_event(lesson: Lesson) -> CalendarEvent:
    """Převede hodinu na událost kalendáře."""
    return CalendarEvent(
        summary=lesson_summary(lesson),
        start=lesson.start,
        end=lesson.end,
        description=lesson_description(lesson),
        location=lesson.room,
        uid=lesson.uid,
    )


class SkolaOnlineTimetableCalendar(
    CoordinatorEntity[SkolaOnlineCoordinator], CalendarEntity
):
    """Kalendář s vyučovacími hodinami studenta."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_translation_key = "timetable"
    _attr_icon = "mdi:timetable"

    def __init__(
        self, coordinator: SkolaOnlineCoordinator, entry: SkolaOnlineConfigEntry
    ) -> None:
        """Inicializuje entitu."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.student_id}_timetable"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.student_id)},
            manufacturer=MANUFACTURER,
            name=entry.data.get(CONF_STUDENT_NAME) or entry.title,
            configuration_url=coordinator.client.base_url,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Vrátí právě probíhající nebo nejbližší příští hodinu."""
        now = dt_util.now()
        for lesson in self.coordinator.data or []:
            if lesson.is_canceled:
                continue
            if lesson.end > now:
                return _to_event(lesson)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Vrátí hodiny v požadovaném rozsahu."""
        return [
            _to_event(lesson)
            for lesson in self.coordinator.data or []
            if lesson.end > start_date and lesson.start < end_date
        ]
