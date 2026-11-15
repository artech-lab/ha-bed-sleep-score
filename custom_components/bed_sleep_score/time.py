# SPDX-License-Identifier: GPL-3.0-or-later
"""Editable sleep window start/end (time entities)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SleepScoreConfigEntry
from .entity import SleepTrackerEntity

TIMES: tuple[TimeEntityDescription, ...] = (
    TimeEntityDescription(key="window_start", entity_category=EntityCategory.CONFIG),
    TimeEntityDescription(key="window_end", entity_category=EntityCategory.CONFIG),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SleepScoreConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the window time entities."""
    async_add_entities(SleepWindowTime(entry.runtime_data, description, "time") for description in TIMES)


class SleepWindowTime(SleepTrackerEntity, TimeEntity):
    """Start or end of the sleep window."""

    @property
    def native_value(self) -> time:
        """Configured time."""
        return getattr(self.tracker, self.entity_description.key)

    async def async_set_value(self, value: time) -> None:
        """Change the window."""
        if self.entity_description.key == "window_start":
            await self.tracker.async_set_window(start=value)
        else:
            await self.tracker.async_set_window(end=value)
