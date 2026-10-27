from datetime import datetime
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from custom_components.yasno.api import KYIV
from custom_components.yasno.const import DOMAIN

from .test_api import DAY

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
        assert "sensor.yasno_vul_khreshchatik_22_minutes_to_outage" in by_key
        minutes = next(s for e, s in by_key.items() if e.endswith("minutes_to_outage"))
        assert minutes.state == "30"  # 21:00
        duration = next(s for e, s in by_key.items() if e.endswith("outage_duration"))
        assert duration.state == "300"  # 21:00 - 02:00, merged over midnight
        group = next(s for e, s in by_key.items() if e.endswith("_group"))
        assert group.state == "3.1"
        now = next(s for e, s in by_key.items() if e.endswith("outage_now"))
        assert now.state == "off"


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
