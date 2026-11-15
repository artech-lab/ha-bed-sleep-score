# SPDX-License-Identifier: GPL-3.0-or-later
"""Bed Sleep Score: nightly sleep quality score from a bed accelerometer."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
import voluptuous as vol

from .const import (
    ATTR_AVERAGE,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_NIGHT_OF,
    ATTR_SCORE,
    CARD_FILENAME,
    CARD_URL,
    DOMAIN,
    SERVICE_SET_SCORE,
)
from .tracker import SleepTracker

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.TIME]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type SleepScoreConfigEntry = ConfigEntry[SleepTracker]

_PERCENT = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
SET_SCORE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_SCORE): _PERCENT,
        vol.Optional(ATTR_AVERAGE): _PERCENT,
        vol.Optional(ATTR_NIGHT_OF): cv.date,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the bundled dashboard card and load it in every dashboard.

    The version in ``manifest.json`` is the single source of truth: it is
    appended to the card URL, which busts the browser cache after an update
    and tells the card its own version.
    """
    version = str((await async_get_integration(hass, DOMAIN)).version)
    hass.data[DOMAIN] = version
    card = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(card), cache_headers=False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")
    hass.services.async_register(DOMAIN, SERVICE_SET_SCORE, _async_set_score, schema=SET_SCORE_SCHEMA)
    return True


@callback
def _async_set_score(call: ServiceCall) -> None:
    """Set the last score and, optionally, the 7-day average of one tracker."""
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = call.hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"name": entry.title},
        )
    tracker: SleepTracker = entry.runtime_data
    tracker.async_set_score(call.data[ATTR_SCORE], call.data.get(ATTR_AVERAGE), call.data.get(ATTR_NIGHT_OF))


async def async_setup_entry(hass: HomeAssistant, entry: SleepScoreConfigEntry) -> bool:
    """Set up a sleep tracker from a config entry."""
    tracker = SleepTracker(hass, entry, hass.data[DOMAIN])
    await tracker.async_load()
    entry.runtime_data = tracker

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    tracker.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SleepScoreConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: SleepScoreConfigEntry) -> None:
    """Reload when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
