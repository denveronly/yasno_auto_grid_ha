"""Reads the group's schedule from Yasno; entities are refreshed every minute from it."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    KYIV,
    STATUS_EMERGENCY,
    STATUS_NO_OUTAGES,
    STATUS_SCHEDULE,
    Outage,
    YasnoApi,
    YasnoError,
    day_status,
    outages,
    planned_days,
    probable_group,
    probable_outages,
)
from . import dtek
from .const import (
    CONF_DSO_ID,
    CONF_GROUP,
    CONF_HOUSE_ID,
    CONF_REGION,
    CONF_REGION_ID,
    CONF_SOURCE,
    CONF_STREET_ID,
    DOMAIN,
    FETCH_SECONDS,
    GROUP_CHECK_SECONDS,
    PROBABLE_FETCH_SECONDS,
    SOURCE_DTEK,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class YasnoData:
    group: str
    group_data: dict[str, Any] = field(default_factory=dict)
    outages: list[Outage] = field(default_factory=list)
    fetched: datetime | None = None
    probable: list[Outage] = field(default_factory=list)  # weekly probable schedule, next 8 days
    planned_days: set[date] = field(default_factory=set)  # days with a published schedule

    def current(self, now: datetime) -> Outage | None:
        return next((o for o in self.outages if o.start <= now < o.end), None)

    def next(self, now: datetime) -> Outage | None:
        return next((o for o in self.outages if o.start > now), None)

    def probable_current(self, now: datetime) -> Outage | None:
        return next((o for o in self.probable if o.start <= now < o.end), None)

    def probable_next(self, now: datetime) -> Outage | None:
        return next((o for o in self.probable if o.start > now), None)

    def day_outages(self, day: date) -> list[Outage]:
        """Planned outages overlapping the day, cut to it."""
        start = datetime.combine(day, datetime.min.time(), KYIV)
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), KYIV)
        return [Outage(max(o.start, start), min(o.end, end)) for o in self.outages if o.start < end and o.end > start]

    @property
    def tomorrow_published(self) -> bool:
        return self.status_tomorrow in (STATUS_SCHEDULE, STATUS_NO_OUTAGES)

    @property
    def updated(self) -> datetime | None:
        try:
            return dt_util.parse_datetime(str(self.updated_on)) if self.updated_on else None
        except ValueError:
            return None

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
    """Updates every minute (minutes to outage count down), reads Yasno / DTEK every 10 minutes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=1), config_entry=entry)
        self.api = YasnoApi(async_get_clientsession(hass))
        self.entry = entry
        self._group: str = entry.data[CONF_GROUP]
        self._fetched_at = 0.0
        self._fetched: datetime | None = None
        self._group_checked_at = time.monotonic()  # the flow has just looked it up
        self._planned: dict[str, Any] | None = None
        self._probable: dict[str, Any] = {}
        self._probable_at = -PROBABLE_FETCH_SECONDS
        self._dtek: dict[str, Any] | None = None

    async def _async_update_data(self) -> YasnoData:
        if self.entry.data.get(CONF_SOURCE) == SOURCE_DTEK:
            return await self._update_dtek()
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
        if time.monotonic() - self._probable_at >= PROBABLE_FETCH_SECONDS:
            await self._fetch_probable()
        group_data = self._planned.get(self._group) if self._planned else None
        if not isinstance(group_data, dict):
            raise UpdateFailed(f"Yasno has no schedule for group {self._group}")
        now = dt_util.now()
        data = self.entry.data
        probable = probable_group(self._probable, data[CONF_REGION_ID], data[CONF_DSO_ID], self._group)
        return YasnoData(
            self._group,
            group_data,
            outages(group_data, now),
            self._fetched,
            probable_outages(probable, now),
            planned_days(group_data, now),
        )

    async def _update_dtek(self) -> YasnoData:
        """One file has both the schedule and the weekly preset of every group."""
        if self._dtek is None or time.monotonic() - self._fetched_at >= FETCH_SECONDS:
            try:
                self._dtek = await dtek.fetch(async_get_clientsession(self.hass), self.entry.data[CONF_REGION])
            except YasnoError as err:
                if self._dtek is None:
                    raise UpdateFailed(str(err)) from err
                _LOGGER.warning("DTEK schedule is not available, keeping the last one: %s", err)
            else:
                self._fetched_at = time.monotonic()
                self._fetched = dt_util.now()
        now = dt_util.now()
        group_data = dtek.group_data(self._dtek, self._group, now)
        return YasnoData(
            self._group,
            group_data,
            outages(group_data, now),
            self._fetched,
            probable_outages(dtek.probable_data(self._dtek, self._group), now),
            planned_days(group_data, now),
        )

    async def _fetch_probable(self) -> None:
        """The weekly probable schedule changes rarely; without it only its entities are empty."""
        self._probable_at = time.monotonic()
        try:
            self._probable = await self.api.probable(self.entry.data[CONF_REGION_ID], self.entry.data[CONF_DSO_ID])
        except YasnoError as err:
            self._probable_at -= PROBABLE_FETCH_SECONDS - FETCH_SECONDS  # try again in 10 minutes
            _LOGGER.warning("Probable outages are not available: %s", err)

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
