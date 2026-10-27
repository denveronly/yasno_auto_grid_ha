from datetime import datetime
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.yasno.api import KYIV
from custom_components.yasno.const import DOMAIN

from .test_api import DAY

# Monday..Sunday: 12:00-15:00 every day; Wednesday (2026-10-28) also 18:00-20:00.
WEEK = {str(d): [{"start": 720, "end": 900, "type": "Definite"}] for d in range(7)}
WEEK["2"] = WEEK["2"] + [{"start": 1080, "end": 1200, "type": "Definite"}]
PROBABLE = {"25": {"dsos": {"902": {"groups": {"3.1": {"slots": WEEK}}}}}}

REGIONS = [
    {"id": 25, "value": "Київ", "dsos": [{"id": 902, "name": "ДТЕК Київські електромережі"}]},
    {"id": 3, "value": "Дніпро", "dsos": [{"id": 301, "name": "ДнЕМ"}, {"id": 302, "name": "ЦЕК"}]},
]


def _api():
    api = AsyncMock()
    api.regions.return_value = REGIONS
    api.streets.return_value = [{"id": 11, "value": "вул. Хрещатик"}, {"id": 12, "value": "пров. Хрещатий"}]
    api.houses.return_value = [{"id": 21, "value": "22"}, {"id": 22, "value": "22/1"}, {"id": 23, "value": "122"}]
    api.group.return_value = "3.1"
    api.planned.return_value = {"3.1": DAY, "1.1": {}, "10.2": {}, "2.1": {}}
    api.probable.return_value = PROBABLE
    return api


async def test_address_flow_and_entities(hass, freezer):
    freezer.move_to(datetime(2026, 10, 27, 20, 30, tzinfo=KYIV))
    api = _api()
    with patch("custom_components.yasno.config_flow.YasnoApi", return_value=api), \
         patch("custom_components.yasno.coordinator.YasnoApi", return_value=api):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"region_id": "25"})
        assert result["type"] is FlowResultType.MENU  # single DSO is picked by itself
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "street"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"street": "хрещ"})
        assert result["step_id"] == "street_pick"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"street_id": "11"})
        assert result["step_id"] == "house"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"house": "22"})
        assert result["type"] is FlowResultType.CREATE_ENTRY  # exact number match, no picker
        assert result["title"] == "вул. Хрещатик, 22 (3.1)"
        assert result["data"]["group"] == "3.1"
        api.group.assert_awaited_with(25, 902, 11, 21)
        await hass.async_block_till_done()

        by_key = {s.entity_id: s for s in hass.states.async_all()}
        def state(key, platform="sensor"):
            return by_key[f"{platform}.yasno_vul_khreshchatik_22_{key}"]

        assert state("minutes_to_outage").state == "30"  # 21:00
        assert state("outage_duration").state == "300"  # 21:00 - 02:00, merged over midnight
        assert state("group").state == "3.1"
        assert state("minutes_to_power_on").state == "0"
        assert state("grid_status", "binary_sensor").state == "on"
        assert state("emergency_outages", "binary_sensor").state == "off"
        assert state("outage_hours_today").state == "7.0"  # 04-08 + 21-24
        assert state("outages_today").state == "2"
        assert state("outage_hours_tomorrow").state == "6.0"  # 00-02 + 10-14
        assert state("outages_tomorrow").state == "2"
        assert state("tomorrow_schedule_published", "binary_sensor").state == "on"
        assert state("schedule", "binary_sensor").state == "on"
        assert state("schedule", "binary_sensor").attributes["status"] == "ScheduleApplies"
        assert state("schedule_tomorrow", "binary_sensor").state == "on"
        assert state("schedule_updated").state == "2026-10-27T10:00:00+00:00"
        assert state("minutes_to_probable_outage").state == str(15 * 60 + 30)  # tomorrow 12:00
        assert state("probable_outage_now", "binary_sensor").state == "off"

        # During the outage: grid off, minutes count down to power on.
        freezer.move_to(datetime(2026, 10, 27, 22, 0, 20, tzinfo=KYIV))
        await entry_refresh(hass)
        by_key.update({s.entity_id: s for s in hass.states.async_all()})
        assert state("grid_status", "binary_sensor").state == "off"
        assert state("minutes_to_power_on").state == "240"  # to 02:00, rounded up
        assert state("power_back").state == "2026-10-28T00:00:00+00:00"

        # Calendar: planned outages, probable ones only on days without a schedule.
        events = await hass.services.async_call(
            "calendar", "get_events",
            {"entity_id": "calendar.yasno_vul_khreshchatik_22_outages",
             "start_date_time": "2026-10-27T00:00:00+02:00", "end_date_time": "2026-10-31T00:00:00+02:00"},
            blocking=True, return_response=True,
        )
        got = [(e["start"], e["summary"]) for e in events["calendar.yasno_vul_khreshchatik_22_outages"]["events"]]
        assert got == [
            ("2026-10-27T04:00:00+02:00", "Outage"),
            ("2026-10-27T21:00:00+02:00", "Outage"),
            ("2026-10-28T10:00:00+02:00", "Outage"),
            ("2026-10-29T12:00:00+02:00", "Probable outage"),
            ("2026-10-30T12:00:00+02:00", "Probable outage"),
        ]


async def entry_refresh(hass):
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_group_by_hand(hass):
    api = _api()
    with patch("custom_components.yasno.config_flow.YasnoApi", return_value=api), \
         patch("custom_components.yasno.coordinator.YasnoApi", return_value=api):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"region_id": "3"})
        assert result["step_id"] == "dso"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"dso_id": "301"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "group"})
        options = [o["value"] for o in result["data_schema"].schema["group"].config["options"]]
        assert options == ["1.1", "2.1", "3.1", "10.2"]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"group": "3.1"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Дніпро 3.1"
