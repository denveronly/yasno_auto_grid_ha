"""Reads the group's schedule from Yasno; entities are refreshed every minute from it."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import STATUS_EMERGENCY, Outage, YasnoApi, YasnoError, day_status, outages
from .const import (
    CONF_DSO_ID,
    CONF_GROUP,
    CONF_HOUSE_ID,
    CONF_REGION_ID,
    CONF_STREET_ID,
    DOMAIN,
    FETCH_SECONDS,
    GROUP_CHECK_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class YasnoData:
    group: str
    group_data: dict[str, Any] = field(default_factory=dict)
    outages: list[Outage] = field(default_factory=list)
    fetched: datetime | None = None

    def current(self, now: datetime) -> Outage | None:
        return next((o for o in self.outages if o.start <= now < o.end), None)

    def next(self, now: datetime) -> Outage | None:
        return next((o for o in self.outages if o.start > now), None)

    @property
    def status_today(self) -> str | None:
        return day_status(self.group_data, "today")

    @property
    def status_tomorrow(self) -> str | None:
        return day_status(self.group_data, "tomorrow")

    @property
    def emergency(self) -> bool:
        return self.status_today == STATUS_EMERGENCY

    @property
    def updated_on(self) -> str | None:
        return self.group_data.get("updatedOn")


class YasnoCoordinator(DataUpdateCoordinator[YasnoData]):
    """Updates every minute (minutes to outage count down), reads Yasno every 10 minutes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=1), config_entry=entry)
        self.api = YasnoApi(async_get_clientsession(hass))
        self.entry = entry
        self._group: str = entry.data[CONF_GROUP]
        self._fetched_at = 0.0
        self._fetched: datetime | None = None
        self._group_checked_at = time.monotonic()  # the flow has just looked it up
        self._planned: dict[str, Any] | None = None

    async def _async_update_data(self) -> YasnoData:
        if self._planned is None or time.monotonic() - self._fetched_at >= FETCH_SECONDS:
            await self._check_group()
            try:
                self._planned = await self.api.planned(self.entry.data[CONF_REGION_ID], self.entry.data[CONF_DSO_ID])
            except YasnoError as err:
                if self._planned is None:
                    raise UpdateFailed(str(err)) from err
                _LOGGER.warning("Yasno is not answering, keeping the last schedule: %s", err)
            else:
                self._fetched_at = time.monotonic()
                self._fetched = dt_util.now()
        group_data = self._planned.get(self._group) if self._planned else None
        if not isinstance(group_data, dict):
            raise UpdateFailed(f"Yasno has no schedule for group {self._group}")
        return YasnoData(self._group, group_data, outages(group_data, dt_util.now()), self._fetched)

    async def _check_group(self) -> None:
        """Yasno moves houses between groups now and then: look the address up once a day."""
        data = self.entry.data
        if not data.get(CONF_HOUSE_ID) or time.monotonic() - self._group_checked_at < GROUP_CHECK_SECONDS:
            return
        try:
            group = await self.api.group(data[CONF_REGION_ID], data[CONF_DSO_ID], data[CONF_STREET_ID], data[CONF_HOUSE_ID])
        except YasnoError as err:
            _LOGGER.debug("Group lookup failed: %s", err)
            return
        self._group_checked_at = time.monotonic()
        if group and group != self._group:
            _LOGGER.warning("Yasno moved this address from group %s to %s", self._group, group)
            self._group = group
            self.hass.config_entries.async_update_entry(self.entry, data={**data, CONF_GROUP: group})
