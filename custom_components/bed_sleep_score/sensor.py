# SPDX-License-Identifier: GPL-3.0-or-later
"""Sensors for Bed Sleep Score."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SleepScoreConfigEntry
from .entity import SleepTrackerEntity
from .tracker import SleepTracker


@dataclass(frozen=True, kw_only=True)
class SleepSensorDescription(SensorEntityDescription):
    """Describes a Bed Sleep Score sensor."""

    value_fn: Callable[[SleepTracker], Any]
    state_class: SensorStateClass = SensorStateClass.MEASUREMENT


SENSORS: tuple[SleepSensorDescription, ...] = (
    SleepSensorDescription(key="score", suggested_display_precision=0, value_fn=lambda t: t.score),
    SleepSensorDescription(key="score_7_day_average", suggested_display_precision=1, value_fn=lambda t: t.average),
    SleepSensorDescription(key="movements", value_fn=lambda t: t.night.movements if t.night.started else None),
    SleepSensorDescription(key="clustered_movements", value_fn=lambda t: t.night.clusters if t.night.started else None),
    SleepSensorDescription(
        key="longest_undisturbed_sleep",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=lambda t: round(t.night.longest_min) if t.night.started else None,
    ),
    SleepSensorDescription(
        key="agitation",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=4,
        value_fn=lambda t: round(t.agitation, 4) if t.agitation is not None else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SleepScoreConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    async_add_entities(SleepSensor(entry.runtime_data, description, "sensor") for description in SENSORS)


class SleepSensor(SleepTrackerEntity, SensorEntity):
    """A Bed Sleep Score sensor."""

    entity_description: SleepSensorDescription

    @property
    def native_value(self) -> Any:
        """Current value."""
        return self.entity_description.value_fn(self.tracker)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The score sensor carries the breakdown of the night."""
        return self.tracker.score_attributes if self.entity_description.key == "score" else None
