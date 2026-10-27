"""Outage now (by the schedule) and emergency outages."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import YasnoConfigEntry
from .entity import YasnoEntity


async def async_setup_entry(hass: HomeAssistant, entry: YasnoConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([YasnoOutageNow(coordinator), YasnoEmergency(coordinator)])


class YasnoOutageNow(YasnoEntity, BinarySensorEntity):
    """On while a scheduled outage is in effect."""

    _attr_icon = "mdi:transmission-tower-off"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "outage_now")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.current(dt_util.now()) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        outage = self.coordinator.data.current(dt_util.now())
        return {"start": outage.start.isoformat(), "end": outage.end.isoformat()} if outage else {"start": None, "end": None}


class YasnoEmergency(YasnoEntity, BinarySensorEntity):
    """On while Yasno reports emergency outages (the schedule does not apply)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "emergency")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.emergency
