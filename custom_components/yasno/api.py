"""Yasno (DTEK) public blackout API: regions, address -> group lookup, planned outages.

The old https://api.yasno.com.ua/api/v1/pages/home/schedule-turn-off-electricity is gone;
the site uses app.yasno.ua now. Planned outages come per region and DSO as
{"1.1": {"today": {"slots": [...], "date": ..., "status": ...}, "tomorrow": {...},
"updatedOn": ...}, "1.2": ...}; a slot is {"start": 960, "end": 1200, "type": "Definite"}
with start/end in minutes from local midnight (24:00 = 1440).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

BASE = "https://app.yasno.ua/api/blackout-service/public/shutdowns"
REGIONS_URL = f"{BASE}/addresses/v2/regions"
STREETS_URL = f"{BASE}/addresses/v2/streets"
HOUSES_URL = f"{BASE}/addresses/v2/houses"
GROUP_URL = f"{BASE}/addresses/v2/group"
PLANNED_URL = f"{BASE}/regions/{{region_id}}/dsos/{{dso_id}}/planned-outages"

KYIV = ZoneInfo("Europe/Kyiv")
TIMEOUT = aiohttp.ClientTimeout(total=30)
HEADERS = {"Accept": "application/json", "User-Agent": "HomeAssistant-Yasno"}

SLOT_OUTAGE = "Definite"
STATUS_SCHEDULE = "ScheduleApplies"
STATUS_WAITING = "WaitingForSchedule"
STATUS_EMERGENCY = "EmergencyShutdowns"
STATUS_NO_OUTAGES = "NoOutages"


class YasnoError(Exception):
    """The Yasno API could not be reached or answered with something unexpected."""


class YasnoApi:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.get(url, params=params, headers=HEADERS, timeout=TIMEOUT) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise YasnoError(f"{url}: {err}") from err

    async def regions(self) -> list[dict[str, Any]]:
        """[{"id": 25, "value": "Київ", "dsos": [{"id": 902, "name": "..."}], ...}]"""
        data = await self._get(REGIONS_URL)
        if not isinstance(data, list):
            raise YasnoError("unexpected regions response")
        return data

    async def streets(self, region_id: int, dso_id: int, query: str) -> list[dict[str, Any]]:
        """[{"id": 123, "value": "вул. Хрещатик"}]"""
        data = await self._get(STREETS_URL, {"regionId": region_id, "dsoId": dso_id, "query": query})
        return data if isinstance(data, list) else []

    async def houses(self, region_id: int, dso_id: int, street_id: int, query: str) -> list[dict[str, Any]]:
        """[{"id": 456, "value": "22"}]"""
        params = {"regionId": region_id, "dsoId": dso_id, "streetId": street_id, "query": query}
        data = await self._get(HOUSES_URL, params)
        return data if isinstance(data, list) else []

    async def group(self, region_id: int, dso_id: int, street_id: int, house_id: int) -> str | None:
        """The outage group of a house, e.g. "3.1"; None when Yasno does not know it."""
        params = {"regionId": region_id, "dsoId": dso_id, "streetId": street_id, "houseId": house_id}
        data = await self._get(GROUP_URL, params)
        if not isinstance(data, dict) or data.get("group") in (None, ""):
            return None
        subgroup = data.get("subgroup")
        return f"{data['group']}.{subgroup}" if subgroup not in (None, "") else str(data["group"])

    async def planned(self, region_id: int, dso_id: int) -> dict[str, Any]:
        """Planned outages of every group of the region / DSO."""
        data = await self._get(PLANNED_URL.format(region_id=region_id, dso_id=dso_id))
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise YasnoError("unexpected planned outages response")
        return data


@dataclass(frozen=True)
class Outage:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60

    def as_dict(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


def _day(raw: dict[str, Any], fallback: date) -> date:
    text = str(raw.get("date") or "")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(KYIV).date() if "T" in text else date.fromisoformat(text[:10])
    except ValueError:
        return fallback


def day_status(group_data: dict[str, Any], key: str) -> str | None:
    raw = group_data.get(key)
    return raw.get("status") if isinstance(raw, dict) else None


def outages(group_data: dict[str, Any], now: datetime) -> list[Outage]:
    """Outages of today and tomorrow, adjacent slots merged (23:00-24:00 + 00:00-02:00 is one).
    Days waiting for a schedule or under emergency outages have no planned slots."""
    today = now.astimezone(KYIV).date()
    intervals: list[Outage] = []
    for key, fallback in (("today", today), ("tomorrow", today + timedelta(days=1))):
        raw = group_data.get(key)
        if not isinstance(raw, dict) or raw.get("status") in (STATUS_WAITING, STATUS_EMERGENCY, STATUS_NO_OUTAGES):
            continue
        midnight = datetime.combine(_day(raw, fallback), datetime.min.time(), KYIV)
        for slot in raw.get("slots") or []:
            try:
                if slot.get("type") != SLOT_OUTAGE:
                    continue
                start, end = int(slot["start"]), int(slot["end"])
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            if end > start:
                intervals.append(Outage(_local(midnight, start), _local(midnight, end)))
    intervals.sort(key=lambda o: o.start)
    merged: list[Outage] = []
    for item in intervals:
        if merged and item.start <= merged[-1].end:
            if item.end > merged[-1].end:
                merged[-1] = Outage(merged[-1].start, item.end)
        else:
            merged.append(item)
    return merged


def _local(midnight: datetime, minutes: int) -> datetime:
    """Wall-clock time of the day (not midnight + minutes, which is an hour off on DST days)."""
    day = midnight.date() + timedelta(days=minutes // 1440)
    minutes %= 1440
    return datetime(day.year, day.month, day.day, minutes // 60, minutes % 60, tzinfo=KYIV)
