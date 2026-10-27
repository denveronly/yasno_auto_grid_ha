"""Calendar: planned outages, and probable ones on days without a published schedule."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import YasnoConfigEntry
from .api import KYIV
from .entity import YasnoEntity

SUMMARIES = {
    "uk": ("Відключення", "Можливе відключення"),
    "ru": ("Отключение", "Возможное отключение"),
}
DEFAULT_SUMMARIES = ("Outage", "Probable outage")


async def async_setup_entry(hass: HomeAssistant, entry: YasnoConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([YasnoCalendar(entry.runtime_data)])


class YasnoCalendar(YasnoEntity, CalendarEntity):
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "outages")

    def _events(self) -> list[CalendarEvent]:
        d = self.coordinator.data
        planned, probable = SUMMARIES.get(self.hass.config.language, DEFAULT_SUMMARIES)
        events = [CalendarEvent(o.start, o.end, planned) for o in d.outages]
        events += [
            CalendarEvent(o.start, o.end, probable, description=f"{d.group}")
            for o in d.probable
            if o.start.astimezone(KYIV).date() not in d.planned_days and not any(p.start < o.end and p.end > o.start for p in d.outages)
        ]
        return sorted(events, key=lambda e: e.start)

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        return next((e for e in self._events() if e.end > now), None)

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [e for e in self._events() if e.start < end_date and e.end > start_date]
