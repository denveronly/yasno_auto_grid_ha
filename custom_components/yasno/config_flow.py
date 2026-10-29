"""Set up: Yasno (region -> DSO -> street -> house, Yasno finds the group, or the group by
hand) or DTEK (region -> group)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from . import dtek
from .api import YasnoApi, YasnoError
from .const import (
    CONF_DSO,
    CONF_DSO_ID,
    CONF_GROUP,
    CONF_HOUSE,
    CONF_HOUSE_ID,
    CONF_REGION,
    CONF_REGION_ID,
    CONF_SOURCE,
    CONF_STREET,
    CONF_STREET_ID,
    DOMAIN,
    SOURCE_DTEK,
    SOURCE_YASNO,
)

MAX_CHOICES = 100


def _select(options: dict[str, str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[{"value": k, "label": v} for k, v in options.items()],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _choices(items: list[dict[str, Any]]) -> dict[str, str]:
    return {str(i["id"]): str(i.get("value") or i.get("name") or i["id"]) for i in items[:MAX_CHOICES] if "id" in i}


def _group_key(group: str) -> tuple[float, ...]:
    try:
        return tuple(float(p) for p in group.split("."))
    except ValueError:
        return (999.0,)


class YasnoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._api: YasnoApi | None = None
        self._regions: list[dict[str, Any]] = []
        self._dsos: dict[str, str] = {}
        self._streets: dict[str, str] = {}
        self._houses: dict[str, str] = {}
        self.data: dict[str, Any] = {}

    @property
    def api(self) -> YasnoApi:
        if self._api is None:
            self._api = YasnoApi(async_get_clientsession(self.hass))
        return self._api

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=[SOURCE_YASNO, SOURCE_DTEK])

    async def async_step_dtek(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """DTEK region; the group is chosen from the groups in its schedule."""
        if user_input is None and len(dtek.REGIONS) == 1:
            user_input = {CONF_REGION: next(iter(dtek.REGIONS))}
        if user_input is not None:
            self.data = {CONF_SOURCE: SOURCE_DTEK, CONF_REGION: user_input[CONF_REGION]}
            return await self.async_step_dtek_group()
        return self.async_show_form(
            step_id="dtek", data_schema=vol.Schema({vol.Required(CONF_REGION): _select(dtek.REGIONS)})
        )

    async def async_step_dtek_group(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create(user_input[CONF_GROUP])
        try:
            data = await dtek.fetch(async_get_clientsession(self.hass), self.data[CONF_REGION])
        except YasnoError:
            return self.async_abort(reason="cannot_connect")
        groups = sorted(dtek.groups(data), key=_group_key)
        if not groups:
            return self.async_abort(reason="no_groups")
        return self.async_show_form(
            step_id="dtek_group",
            data_schema=vol.Schema({vol.Required(CONF_GROUP): _select({g: g for g in groups})}),
            description_placeholders={CONF_REGION: dtek.REGIONS[self.data[CONF_REGION]]},
        )

    async def async_step_yasno(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if not self._regions:
            try:
                self._regions = await self.api.regions()
            except YasnoError:
                return self.async_abort(reason="cannot_connect")
        regions = {str(r["id"]): str(r.get("value") or r["id"]) for r in self._regions if "id" in r}
        if user_input is not None:
            region = next(r for r in self._regions if str(r["id"]) == user_input[CONF_REGION_ID])
            self.data[CONF_SOURCE] = SOURCE_YASNO
            self.data[CONF_REGION_ID] = int(region["id"])
            self.data[CONF_REGION] = regions[user_input[CONF_REGION_ID]]
            self._dsos = _choices(region.get("dsos") or [])
            if not self._dsos:
                errors["base"] = "no_dso"
            elif len(self._dsos) == 1:
                return await self.async_step_dso({CONF_DSO_ID: next(iter(self._dsos))})
            else:
                return await self.async_step_dso()
        return self.async_show_form(
            step_id="yasno",
            data_schema=vol.Schema({vol.Required(CONF_REGION_ID): _select(regions)}),
            errors=errors,
        )

    async def async_step_dso(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self.data[CONF_DSO_ID] = int(user_input[CONF_DSO_ID])
            self.data[CONF_DSO] = self._dsos[user_input[CONF_DSO_ID]]
            return await self.async_step_method()
        return self.async_show_form(
            step_id="dso", data_schema=vol.Schema({vol.Required(CONF_DSO_ID): _select(self._dsos)})
        )

    async def async_step_method(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="method", menu_options=["street", "group"])

    async def async_step_street(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Search the street by part of its name."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                found = await self.api.streets(self.data[CONF_REGION_ID], self.data[CONF_DSO_ID], user_input[CONF_STREET].strip())
            except YasnoError:
                errors["base"] = "cannot_connect"
            else:
                self._streets = _choices(found)
                if not self._streets:
                    errors[CONF_STREET] = "street_not_found"
                elif len(self._streets) == 1:
                    return await self.async_step_street_pick({CONF_STREET_ID: next(iter(self._streets))})
                else:
                    return await self.async_step_street_pick()
        return self.async_show_form(
            step_id="street", data_schema=vol.Schema({vol.Required(CONF_STREET): str}), errors=errors
        )

    async def async_step_street_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self.data[CONF_STREET_ID] = int(user_input[CONF_STREET_ID])
            self.data[CONF_STREET] = self._streets[user_input[CONF_STREET_ID]]
            return await self.async_step_house()
        return self.async_show_form(
            step_id="street_pick", data_schema=vol.Schema({vol.Required(CONF_STREET_ID): _select(self._streets)})
        )

    async def async_step_house(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Search the house number on the street."""
        errors: dict[str, str] = {}
        if user_input is not None:
            query = user_input[CONF_HOUSE].strip()
            try:
                found = await self.api.houses(self.data[CONF_REGION_ID], self.data[CONF_DSO_ID], self.data[CONF_STREET_ID], query)
            except YasnoError:
                errors["base"] = "cannot_connect"
            else:
                self._houses = _choices(found)
                exact = [k for k, v in self._houses.items() if v.strip().lower() == query.lower()]
                if not self._houses:
                    errors[CONF_HOUSE] = "house_not_found"
                elif len(self._houses) == 1 or len(exact) == 1:
                    return await self.async_step_house_pick({CONF_HOUSE_ID: exact[0] if exact else next(iter(self._houses))})
                else:
                    return await self.async_step_house_pick()
        return self.async_show_form(
            step_id="house",
            data_schema=vol.Schema({vol.Required(CONF_HOUSE): str}),
            description_placeholders={CONF_STREET: self.data[CONF_STREET]},
            errors=errors,
        )

    async def async_step_house_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            house_id = int(user_input[CONF_HOUSE_ID])
            try:
                group = await self.api.group(self.data[CONF_REGION_ID], self.data[CONF_DSO_ID], self.data[CONF_STREET_ID], house_id)
            except YasnoError:
                errors["base"] = "cannot_connect"
            else:
                if group:
                    self.data[CONF_HOUSE_ID] = house_id
                    self.data[CONF_HOUSE] = self._houses[user_input[CONF_HOUSE_ID]]
                    return await self._create(group)
                errors["base"] = "group_not_found"
        return self.async_show_form(
            step_id="house_pick",
            data_schema=vol.Schema({vol.Required(CONF_HOUSE_ID): _select(self._houses)}),
            errors=errors,
        )

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The group by hand (e.g. 3.1), from the groups Yasno has a schedule for."""
        if user_input is not None:
            return await self._create(user_input[CONF_GROUP])
        try:
            planned = await self.api.planned(self.data[CONF_REGION_ID], self.data[CONF_DSO_ID])
        except YasnoError:
            return self.async_abort(reason="cannot_connect")
        groups = sorted(planned, key=_group_key)
        if not groups:
            return self.async_abort(reason="no_groups")
        return self.async_show_form(
            step_id="group",
            data_schema=vol.Schema({vol.Required(CONF_GROUP): _select({g: g for g in groups})}),
        )

    async def _create(self, group: str) -> ConfigFlowResult:
        self.data[CONF_GROUP] = group
        if self.data[CONF_SOURCE] == SOURCE_DTEK:
            await self.async_set_unique_id(f"dtek_{self.data[CONF_REGION]}_{group}")
            title = f"{dtek.REGIONS[self.data[CONF_REGION]]} {group}"
        elif self.data.get(CONF_HOUSE_ID):
            await self.async_set_unique_id(f"{self.data[CONF_REGION_ID]}_{self.data[CONF_STREET_ID]}_{self.data[CONF_HOUSE_ID]}")
            title = f"{self.data[CONF_STREET]}, {self.data[CONF_HOUSE]} ({group})"
        else:
            await self.async_set_unique_id(f"{self.data[CONF_REGION_ID]}_{self.data[CONF_DSO_ID]}_group_{group}")
            title = f"{self.data[CONF_REGION]} {group}"
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=self.data)
