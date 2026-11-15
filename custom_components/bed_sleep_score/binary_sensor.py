# SPDX-License-Identifier: GPL-3.0-or-later
"""Binary sensors for Bed Sleep Score."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SleepScoreConfigEntry
from .entity import SleepTrackerEntity

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(key="window_active"),
    BinarySensorEntityDescription(key="movement", device_class=BinarySensorDeviceClass.MOTION),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SleepScoreConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    async_add_entities(
        SleepBinarySensor(entry.runtime_data, description, "binary_sensor") for description in BINARY_SENSORS
    )


class SleepBinarySensor(SleepTrackerEntity, BinarySensorEntity):
    """Sleep window state or bed movement."""

    @property
    def is_on(self) -> bool:
        """Current state."""
        if self.entity_description.key == "window_active":
            return self.tracker.in_window()
        return self.tracker.moving
