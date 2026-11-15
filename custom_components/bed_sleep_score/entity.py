# SPDX-License-Identifier: GPL-3.0-or-later
"""Base entity for Bed Sleep Score."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.util import slugify

from .const import DEFAULT_NAME, DOMAIN
from .tracker import SleepTracker


class SleepTrackerEntity(Entity):
    """Common behaviour: device grouping, English entity IDs, push updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, tracker: SleepTracker, description: EntityDescription, platform: str) -> None:
        """Initialise the entity."""
        self.tracker = tracker
        self.entity_description = description
        entry = tracker.entry
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        # Explicit English object IDs, independent of the UI language.
        self.entity_id = f"{platform}.{slugify(entry.title) or slugify(DEFAULT_NAME)}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Bed Sleep Score",
            sw_version=tracker.version,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._written: Any = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to tracker updates."""
        self.async_on_remove(async_dispatcher_connect(self.hass, self.tracker.signal, self._on_update))

    @callback
    def _on_update(self) -> None:
        """Write the state only when it actually changed (the tracker notifies often)."""
        current = (self.state, self.extra_state_attributes)
        if current != self._written:
            self._written = current
            self.async_write_ha_state()
