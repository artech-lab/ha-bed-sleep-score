# SPDX-License-Identifier: GPL-3.0-or-later
"""Config and options flow for Bed Sleep Score."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_PRESENCE_ENTITY,
    CONF_SENSORS,
    CONF_THRESHOLD,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    DEFAULT_NAME,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DOMAIN,
)

MAX_AXES = 3


def _sources(current: dict[str, Any]) -> dict[Any, Any]:
    """Fields shared by the setup and the options form."""
    return {
        vol.Required(CONF_SENSORS, default=current.get(CONF_SENSORS, [])): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=True)
        ),
        vol.Optional(
            CONF_PRESENCE_ENTITY, description={"suggested_value": current.get(CONF_PRESENCE_ENTITY)}
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["person", "device_tracker", "binary_sensor", "input_boolean"])
        ),
    }


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    errors = {}
    if not 1 <= len(user_input[CONF_SENSORS]) <= MAX_AXES:
        errors[CONF_SENSORS] = "sensor_count"
    if CONF_WINDOW_START in user_input and user_input[CONF_WINDOW_START] == user_input[CONF_WINDOW_END]:
        errors[CONF_WINDOW_END] = "window_empty"
    return errors


class BedSleepScoreConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup: accelerometer sensors and sleep window."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Single setup form."""
        errors: dict[str, str] = {}
        if user_input is not None and not (errors := _validate(user_input)):
            return self.async_create_entry(title=user_input.pop(CONF_NAME), data=user_input)

        current = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=current.get(CONF_NAME, DEFAULT_NAME)): selector.TextSelector(),
                **_sources(current),
                vol.Required(
                    CONF_WINDOW_START, default=current.get(CONF_WINDOW_START, DEFAULT_WINDOW_START.isoformat())
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_WINDOW_END, default=current.get(CONF_WINDOW_END, DEFAULT_WINDOW_END.isoformat())
                ): selector.TimeSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BedSleepScoreOptionsFlow:
        """Return the options flow."""
        return BedSleepScoreOptionsFlow()


class BedSleepScoreOptionsFlow(OptionsFlow):
    """Change the sensors and the sensitivity."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Single options form."""
        errors: dict[str, str] = {}
        if user_input is not None and not (errors := _validate(user_input)):
            # An optional entity removed in the form must be cleared explicitly.
            user_input.setdefault(CONF_PRESENCE_ENTITY, None)
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        schema = vol.Schema(
            {
                **_sources(current),
                vol.Required(
                    CONF_THRESHOLD, default=current.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.001, max=100, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
