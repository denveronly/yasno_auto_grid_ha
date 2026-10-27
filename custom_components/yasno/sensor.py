"""Group, minutes to the next outage / to power on, its length and times, hours without
power today / tomorrow, the weekly probable schedule."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import YasnoConfigEntry
from .api import KYIV
from .const import DOMAIN, FAR_MINUTES
from .coordinator import YasnoData
from .entity import YasnoEntity


def _minutes_to_outage(d: YasnoData, now: datetime) -> int:
    nxt = d.next(now)
    return FAR_MINUTES if nxt is None else min(FAR_MINUTES, int((nxt.start - now).total_seconds() // 60))


def _minutes_to_power_on(d: YasnoData, now: datetime) -> int:
    """Minutes until the outage in effect ends; 0 while there is power by the schedule."""
    outage = d.current(now)
    return math.ceil((outage.end - now).total_seconds() / 60) if outage else 0


def _minutes_to_probable(d: YasnoData, now: datetime) -> int:
    nxt = d.probable_next(now)
    return FAR_MINUTES if nxt is None else min(FAR_MINUTES, int((nxt.start - now).total_seconds() // 60))


def _probable_start(d: YasnoData, now: datetime) -> datetime | None:
    nxt = d.probable_next(now)
    return nxt.start if nxt else None


def _day(now: datetime, offset: int):
    return now.astimezone(KYIV).date() + timedelta(days=offset)


def _hours(offset: int) -> Callable[[YasnoData, datetime], float | None]:
    """Hours without power on the day; unknown until its schedule is published."""
    def value(d: YasnoData, now: datetime) -> float | None:
        day = _day(now, offset)
        if day not in d.planned_days:
            return None
        return round(sum(o.minutes for o in d.day_outages(day)) / 60, 1)
    return value


def _count(offset: int) -> Callable[[YasnoData, datetime], int | None]:
    def value(d: YasnoData, now: datetime) -> int | None:
        day = _day(now, offset)
        return len(d.day_outages(day)) if day in d.planned_days else None
    return value


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
        key="minutes_to_power_on",
        icon="mdi:timer-check-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value=_minutes_to_power_on,
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
    YasnoSensorDescription(
        key="outage_hours_today",
        icon="mdi:clock-alert-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value=_hours(0),
    ),
    YasnoSensorDescription(
        key="outage_hours_tomorrow",
        icon="mdi:clock-alert-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value=_hours(1),
    ),
    YasnoSensorDescription(key="outages_today", icon="mdi:counter", value=_count(0)),
    YasnoSensorDescription(key="outages_tomorrow", icon="mdi:counter", value=_count(1)),
    YasnoSensorDescription(
        key="minutes_to_probable_outage",
        icon="mdi:timer-alert-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value=_minutes_to_probable,
    ),
    YasnoSensorDescription(
        key="next_probable_outage",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-alert",
        value=_probable_start,
    ),
    YasnoSensorDescription(
        key="schedule_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:update",
        value=lambda d, now: d.updated,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: YasnoConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    # 0.1.0 had a "Schedule status" text sensor; it is the "Schedule" binary sensor now.
    registry = er.async_get(hass)
    if old := registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_status"):
        registry.async_remove(old)
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
        if key in ("minutes_to_outage", "outage_duration"):
            return _times(d.next(now))
        if key == "minutes_to_power_on":
            return _times(d.current(now))
        if key in ("minutes_to_probable_outage", "next_probable_outage"):
            return {**_times(d.probable_next(now)), "outages": [o.as_dict() for o in d.probable]}
        if key in ("outage_hours_today", "outage_hours_tomorrow", "outages_today", "outages_tomorrow"):
            day = _day(now, 0 if key.endswith("today") else 1)
            return {"outages": [o.as_dict() for o in d.day_outages(day)]}
        return None


def _times(outage) -> dict[str, str | None]:
    return {"start": outage.start.isoformat(), "end": outage.end.isoformat()} if outage else {"start": None, "end": None}
