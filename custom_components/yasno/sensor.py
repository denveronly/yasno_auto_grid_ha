"""Group, minutes to the next outage, its length and times, schedule status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import YasnoConfigEntry
from .const import FAR_MINUTES
from .coordinator import YasnoData
from .entity import YasnoEntity


def _minutes_to_outage(d: YasnoData, now: datetime) -> int:
    nxt = d.next(now)
    return FAR_MINUTES if nxt is None else min(FAR_MINUTES, int((nxt.start - now).total_seconds() // 60))


def _next_duration(d: YasnoData, now: datetime) -> float | None:
    nxt = d.next(now)
    return round(nxt.minutes) if nxt else None


def _next_start(d: YasnoData, now: datetime) -> datetime | None:
    nxt = d.next(now)
    return nxt.start if nxt else None


def _power_on(d: YasnoData, now: datetime) -> datetime | None:
    """The end of the outage in effect, otherwise of the next one."""
    outage = d.current(now) or d.next(now)
    return outage.end if outage else None


def _slots(d: YasnoData, key: str) -> list[dict[str, Any]]:
    raw = d.group_data.get(key)
    return list(raw.get("slots") or []) if isinstance(raw, dict) else []


@dataclass(frozen=True, kw_only=True)
class YasnoSensorDescription(SensorEntityDescription):
    value: Callable[[YasnoData, datetime], Any]


SENSORS = (
    YasnoSensorDescription(key="group", icon="mdi:numeric", value=lambda d, now: d.group),
    YasnoSensorDescription(
        key="minutes_to_outage",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value=_minutes_to_outage,
    ),
    YasnoSensorDescription(
        key="outage_duration",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value=_next_duration,
    ),
    YasnoSensorDescription(
        key="next_outage", device_class=SensorDeviceClass.TIMESTAMP, icon="mdi:transmission-tower-off", value=_next_start
    ),
    YasnoSensorDescription(
        key="next_power_on", device_class=SensorDeviceClass.TIMESTAMP, icon="mdi:transmission-tower", value=_power_on
    ),
    YasnoSensorDescription(key="status", icon="mdi:calendar-clock", value=lambda d, now: d.status_today),
)


async def async_setup_entry(hass: HomeAssistant, entry: YasnoConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(YasnoSensor(entry.runtime_data, description) for description in SENSORS)


class YasnoSensor(YasnoEntity, SensorEntity):
    entity_description: YasnoSensorDescription

    def __init__(self, coordinator, description: YasnoSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data, dt_util.now())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        d, now = self.coordinator.data, dt_util.now()
        key = self.entity_description.key
        if key == "status":
            return {
                "group": d.group,
                "status_tomorrow": d.status_tomorrow,
                "today": _slots(d, "today"),
                "tomorrow": _slots(d, "tomorrow"),
                "outages": [o.as_dict() for o in d.outages],
                "updated_on": d.updated_on,
                "fetched": d.fetched.isoformat() if d.fetched else None,
            }
        if key in ("minutes_to_outage", "outage_duration"):
            nxt = d.next(now)
            return {"start": nxt.start.isoformat(), "end": nxt.end.isoformat()} if nxt else {"start": None, "end": None}
        return None
