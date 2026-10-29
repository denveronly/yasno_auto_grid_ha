"""Base entity: one device per configured address / group."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DSO, CONF_GROUP, CONF_HOUSE, CONF_SOURCE, CONF_STREET, DOMAIN, SOURCE_DTEK
from .coordinator import YasnoCoordinator


class YasnoEntity(CoordinatorEntity[YasnoCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: YasnoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        data = entry.data
        # Without the group, so entity ids stay the same when Yasno moves the house to another group.
        is_dtek = data.get(CONF_SOURCE) == SOURCE_DTEK
        place = f"{data[CONF_STREET]} {data[CONF_HOUSE]}" if data.get(CONF_HOUSE) else data[CONF_GROUP]
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"DTEK {entry.title}" if is_dtek else f"Yasno {place}",
            manufacturer="DTEK" if is_dtek else "Yasno",
            model=entry.data.get(CONF_DSO),
            entry_type=DeviceEntryType.SERVICE,
        )
