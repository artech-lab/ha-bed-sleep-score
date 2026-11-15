"""Tests for the config and options flows."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bed_sleep_score.const import DOMAIN

AXES = ["sensor.bed_accel_x", "sensor.bed_accel_y", "sensor.bed_accel_z"]
USER_INPUT = {
    "name": "Sleep tracker",
    "accelerometer_sensors": AXES,
    "window_start": "23:30:00",
    "window_end": "07:30:00",
}


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(USER_INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sleep tracker"
    assert result["data"]["accelerometer_sensors"] == AXES
    await hass.async_block_till_done()
    assert hass.states.get("sensor.sleep_tracker_score") is not None


async def test_user_flow_errors(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    bad = {**USER_INPUT, "accelerometer_sensors": [*AXES, "sensor.extra"], "window_end": "23:30:00"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"accelerometer_sensors": "sensor_count", "window_end": "window_empty"}


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Sleep tracker", data={"accelerometer_sensors": AXES})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"accelerometer_sensors": AXES[:1], "movement_threshold": 0.2}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    tracker = entry.runtime_data
    assert tracker.sensors == AXES[:1]
    assert tracker.threshold_on == 0.2
    assert round(tracker.scale, 3) == 1.961
