"""Grid status, schedule today / tomorrow, emergency and probable outages."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import YasnoConfigEntry
from .api import STATUS_SCHEDULE
from .const import DOMAIN
from .entity import YasnoEntity


async def async_setup_entry(hass: HomeAssistant, entry: YasnoConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    # 0.1.0 had "Outage now" (on = no power); "Grid status" replaces it the other way round.
    registry = er.async_get(hass)
    if old := registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_outage_now"):
        registry.async_remove(old)
    async_add_entities(
        [YasnoGridStatus(coordinator), YasnoEmergency(coordinator), YasnoProbableNow(coordinator), YasnoTomorrow(coordinator),
         YasnoSchedule(coordinator, "today"), YasnoSchedule(coordinator, "tomorrow")]
    )


class YasnoGridStatus(YasnoEntity, BinarySensorEntity):
    """On while there is power by the schedule, off during a scheduled outage."""

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "grid_status")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.current(dt_util.now()) is None

    @property
    def icon(self) -> str:
        return "mdi:transmission-tower" if self.is_on else "mdi:transmission-tower-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        outage = self.coordinator.data.current(dt_util.now())
        return {"start": outage.start.isoformat(), "end": outage.end.isoformat()} if outage else {"start": None, "end": None}


class YasnoEmergency(YasnoEntity, BinarySensorEntity):
    """On while Yasno reports emergency outages (the schedule does not apply)."""

    _attr_icon = "mdi:alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "emergency")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.emergency


class YasnoProbableNow(YasnoEntity, BinarySensorEntity):
    """On during an outage of the weekly probable schedule."""

    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "probable_outage_now")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.probable_current(dt_util.now()) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        outage = self.coordinator.data.probable_current(dt_util.now())
        return {"start": outage.start.isoformat(), "end": outage.end.isoformat()} if outage else {"start": None, "end": None}


class YasnoTomorrow(YasnoEntity, BinarySensorEntity):
    """On once Yasno has published tomorrow's schedule."""

    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "tomorrow_published")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.tomorrow_published


class YasnoSchedule(YasnoEntity, BinarySensorEntity):
    """On when outages go by the schedule that day (ScheduleApplies); off with no outages,
    while waiting for the schedule or under emergency outages. The raw status is an attribute."""

    def __init__(self, coordinator, day: str) -> None:
        super().__init__(coordinator, "schedule" if day == "today" else "schedule_tomorrow")
        self._day = day

    @property
    def _status(self) -> str | None:
        d = self.coordinator.data
        return d.status_today if self._day == "today" else d.status_tomorrow

    @property
    def is_on(self) -> bool:
        return self._status == STATUS_SCHEDULE

    @property
    def icon(self) -> str:
        return "mdi:calendar-clock" if self.is_on else "mdi:calendar-blank-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        raw = d.group_data.get(self._day)
        attrs: dict[str, Any] = {
            "status": self._status,
            "slots": list(raw.get("slots") or []) if isinstance(raw, dict) else [],
        }
        if self._day == "today":
            attrs |= {
                "group": d.group,
                "outages": [o.as_dict() for o in d.outages],
                "updated_on": d.updated_on,
                "fetched": d.fetched.isoformat() if d.fetched else None,
            }
        return attrs
