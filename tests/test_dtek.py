"""DTEK (Kyiv region) through the outage-data-ua mirror; data in the shape of its kyiv-region.json."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.yasno import dtek
from custom_components.yasno.api import KYIV, outages
from custom_components.yasno.const import DOMAIN

TODAY = 1793224800  # 2026-10-29 00:00 Kyiv
TOMORROW = 1793311200


def _hours(off: dict[int, str]) -> dict[str, str]:
    return {str(h): off.get(h, "yes") for h in range(1, 25)}


def _week(off: dict[int, str]) -> dict[str, dict[str, str]]:
    return {str(d): _hours(off) for d in range(1, 8)}


DATA = {
    "regionId": "kyiv-region",
    "regionAffiliation": "Київська обл.",
    "fact": {
        "data": {
            str(TODAY): {
                # 00:00-01:00 off, 10:30-11:00 off, 14:00-14:30 off, 21:00-24:00 off
                "GPV2.2": _hours({1: "no", 11: "second", 15: "first", 22: "no", 23: "no", 24: "no"}),
                "GPV1.1": _hours({}),
            },
            str(TOMORROW): {
                "GPV2.2": _hours({1: "no", 2: "no", 13: "no"}),
                "GPV1.1": _hours({}),
            },
        },
        "update": "29.10.2026 20:25",
        "today": TODAY,
    },
    "preset": {
        "data": {
            "GPV2.2": _week({6: "mfirst", 7: "maybe", 8: "msecond"}),  # 05:00-05:30, 06:00-08:00
            "GPV1.1": _week({}),
        },
        "updateFact": "29.10.2026 20:25",
    },
}


def test_group_data_slots_and_status():
    now = datetime(2026, 10, 29, 12, 0, tzinfo=KYIV)
    data = dtek.group_data(DATA, "2.2", now)
    assert data["today"]["status"] == "ScheduleApplies"
    assert data["updatedOn"] == "2026-10-29T20:25:00+02:00"
    result = outages(data, now)
    assert [(o.start.strftime("%d %H:%M"), o.end.strftime("%d %H:%M")) for o in result] == [
        ("29 00:00", "29 01:00"),
        ("29 10:30", "29 11:00"),
        ("29 14:00", "29 14:30"),
        ("29 21:00", "30 02:00"),  # tonight runs into tomorrow's 00:00-02:00
        ("30 12:00", "30 13:00"),
    ]
    assert dtek.group_data(DATA, "1.1", now)["today"]["status"] == "NoOutages"
    # The day after tomorrow is not published yet.
    later = dtek.group_data(DATA, "2.2", datetime(2026, 10, 30, 12, 0, tzinfo=KYIV))
    assert later["tomorrow"]["status"] == "WaitingForSchedule"


def test_groups_and_probable():
    assert sorted(dtek.groups(DATA)) == ["1.1", "2.2"]
    probable = dtek.probable_data(DATA, "2.2")
    assert probable["slots"]["0"] == [
        {"start": 300, "end": 330, "type": "Definite"},
        {"start": 360, "end": 420, "type": "Definite"},
        {"start": 450, "end": 480, "type": "Definite"},
    ]


async def test_dtek_flow_and_entities(hass, freezer):
    freezer.move_to(datetime(2026, 10, 29, 20, 0, tzinfo=KYIV))
    with patch("custom_components.yasno.dtek.fetch", AsyncMock(return_value=DATA)):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "dtek"})
        assert result["step_id"] == "dtek_group"  # the only DTEK region is picked by itself
        options = [o["value"] for o in result["data_schema"].schema["group"].config["options"]]
        assert options == ["1.1", "2.2"]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"group": "2.2"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Київська область 2.2"
        await hass.async_block_till_done()

        states = {s.entity_id: s.state for s in hass.states.async_all()}
        prefix = "dtek_kiivska_oblast_2_2"
        assert states[f"sensor.{prefix}_minutes_to_outage"] == "60"
        assert states[f"sensor.{prefix}_outage_duration"] == "300"  # 21:00-02:00
        assert states[f"binary_sensor.{prefix}_grid_status"] == "on"
        assert states[f"binary_sensor.{prefix}_schedule"] == "on"
        assert states[f"sensor.{prefix}_outage_hours_today"] == "5.0"  # 1 + 0.5 + 0.5 + 3
        assert states[f"sensor.{prefix}_minutes_to_probable_outage"] == str(9 * 60)  # tomorrow 05:00
