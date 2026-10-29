"""DTEK schedules (Kyiv region, DTEK KREM) from the outage-data-ua mirror.

The DTEK sites (dtek-krem.com.ua, …) sit behind bot protection; the mirror at
github.com/Baskerville42/outage-data-ua reads them with a headless browser every few
minutes and publishes the site's own data as JSON:

    fact.data   {"<unix midnight>": {"GPV1.1": {"1": "yes", ..., "24": "no"}}}  today, tomorrow
    fact.update "29.10.2026 20:25"
    preset.data {"GPV1.1": {"1": {"1": "maybe", ...}, ..., "7": {...}}}         weekday 1 = Monday

Hour "1" is 00:00-01:00. "no" = no power, "first" / "second" = no power the first / second
half hour; the weekly preset has "maybe", "mfirst", "msecond". Both are turned into the
Yasno shapes (slots in minutes from midnight) so the rest of the integration is shared.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import aiohttp

from .api import HEADERS, KYIV, SLOT_OUTAGE, STATUS_NO_OUTAGES, STATUS_SCHEDULE, STATUS_WAITING, TIMEOUT, YasnoError

DATA_URL = "https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/{region}.json"

# Kyiv and Dnipro come from Yasno itself; the mirror also has kyiv, dnipro and odesa.
REGIONS = {"kyiv-region": "Київська область"}

FACT_OFF = {"no": (0, 60), "first": (0, 30), "second": (30, 60)}
PRESET_OFF = {"maybe": (0, 60), "mfirst": (0, 30), "msecond": (30, 60), **FACT_OFF}


async def fetch(session: aiohttp.ClientSession, region: str) -> dict[str, Any]:
    url = DATA_URL.format(region=region)
    try:
        async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise YasnoError(f"{url}: {err}") from err
    if not isinstance(data, dict) or not isinstance(data.get("fact"), dict):
        raise YasnoError(f"{url}: unexpected response")
    return data


def groups(data: dict[str, Any]) -> list[str]:
    """Groups ("1.1", "2.2", …) the region has a schedule for."""
    found: set[str] = set()
    for day in _fact_days(data).values():
        found.update(day)
    found.update((data.get("preset") or {}).get("data") or {})
    return [g.removeprefix("GPV") for g in found if g.startswith("GPV")]


def group_data(data: dict[str, Any], group: str, now: datetime) -> dict[str, Any]:
    """Today / tomorrow of one group in the Yasno planned-outages shape."""
    today = now.astimezone(KYIV).date()
    days = {
        datetime.fromtimestamp(int(ts), KYIV).date(): hours
        for ts, hours in _fact_days(data).items()
        if str(ts).isdigit()
    }
    result: dict[str, Any] = {"updatedOn": _updated((data.get("fact") or {}).get("update"))}
    for key, day in (("today", today), ("tomorrow", today + timedelta(days=1))):
        hours = (days.get(day) or {}).get(f"GPV{group}")
        if not isinstance(hours, dict):
            result[key] = {"date": day.isoformat(), "status": STATUS_WAITING, "slots": []}
            continue
        slots = _slots(hours, FACT_OFF)
        status = STATUS_SCHEDULE if slots else STATUS_NO_OUTAGES
        result[key] = {"date": day.isoformat(), "status": status, "slots": slots}
    return result


def probable_data(data: dict[str, Any], group: str) -> dict[str, Any]:
    """The weekly preset of one group in the Yasno probable shape ({"slots": {"0": …}})."""
    week = (((data.get("preset") or {}).get("data")) or {}).get(f"GPV{group}") or {}
    return {"slots": {str(int(d) - 1): _slots(h, PRESET_OFF) for d, h in week.items() if str(d).isdigit() and isinstance(h, dict)}}


def _fact_days(data: dict[str, Any]) -> dict[str, Any]:
    days = (data.get("fact") or {}).get("data")
    return days if isinstance(days, dict) else {}


def _slots(hours: dict[str, Any], off: dict[str, tuple[int, int]]) -> list[dict[str, Any]]:
    slots = []
    for hour, value in hours.items():
        if not str(hour).isdigit() or value not in off:
            continue
        begin = (int(hour) - 1) * 60
        start, end = off[value]
        slots.append({"start": begin + start, "end": begin + end, "type": SLOT_OUTAGE})
    return sorted(slots, key=lambda s: s["start"])


def _updated(text: Any) -> str | None:
    try:
        return datetime.strptime(str(text), "%d.%m.%Y %H:%M").replace(tzinfo=KYIV).isoformat()
    except ValueError:
        return None
