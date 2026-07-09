"""Sensor platform for the Concept2 Logbook integration."""

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pyconcept2 import Workout, WorkoutSummary

from .const import CONF_PROFILE_ID, CONF_PROFILE_NAME, DOMAIN, SUMMARY_PERIODS, WORKOUT_TYPES
from .coordinator import Concept2LogbookCoordinator, Concept2LogbookData, SummaryFilter


@dataclass(frozen=True, kw_only=True)
class Concept2SensorEntityDescription(SensorEntityDescription):
    """Entity description for Concept2 sensors."""

    value_fn: Callable[[Concept2LogbookData], Any]
    available_fn: Callable[[Concept2LogbookData], bool] = lambda data: True
    attrs_fn: Callable[[Concept2LogbookData], dict[str, Any]] | None = None


LATEST_WORKOUT_SENSORS: tuple[Concept2SensorEntityDescription, ...] = (
    Concept2SensorEntityDescription(
        key="last_workout",
        translation_key="last_workout",
        icon="mdi:rowing",
        value_fn=lambda data: data.latest_workout.date
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None,
        attrs_fn=lambda data: _workout_attributes(data.latest_workout),
    ),
    Concept2SensorEntityDescription(
        key="last_workout_distance",
        translation_key="last_workout_distance",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.latest_workout.distance
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_time",
        translation_key="last_workout_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _tenths_to_seconds(data.latest_workout.time)
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_calories",
        translation_key="last_workout_calories",
        native_unit_of_measurement="kcal",
        icon="mdi:fire",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.latest_workout.calories
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None
        and data.latest_workout.calories is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_stroke_rate",
        translation_key="last_workout_stroke_rate",
        icon="mdi:speedometer",
        native_unit_of_measurement="spm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.latest_workout.stroke_rate
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None
        and data.latest_workout.stroke_rate is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_pace",
        translation_key="last_workout_pace",
        icon="mdi:timer-outline",
        value_fn=lambda data: _workout_pace_formatted(data.latest_workout),
        available_fn=lambda data: _workout_pace_formatted(data.latest_workout)
        is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_drag_factor",
        translation_key="last_workout_drag_factor",
        icon="mdi:tune-variant",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.latest_workout.drag_factor
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None
        and data.latest_workout.drag_factor is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_workout_type",
        translation_key="last_workout_workout_type",
        icon="mdi:format-list-bulleted-type",
        value_fn=lambda data: data.latest_workout.workout_type
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None
        and data.latest_workout.workout_type is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_source",
        translation_key="last_workout_source",
        icon="mdi:cloud-upload-outline",
        value_fn=lambda data: data.latest_workout.source
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None
        and data.latest_workout.source is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_verified",
        translation_key="last_workout_verified",
        icon="mdi:check-decagram",
        value_fn=lambda data: data.latest_workout.verified
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None
        and data.latest_workout.verified is not None,
    ),
    Concept2SensorEntityDescription(
        key="last_workout_ranked",
        translation_key="last_workout_ranked",
        icon="mdi:podium",
        value_fn=lambda data: data.latest_workout.ranked
        if data.latest_workout is not None
        else None,
        available_fn=lambda data: data.latest_workout is not None
        and data.latest_workout.ranked is not None,
    ),
)

DIAGNOSTIC_SENSORS: tuple[Concept2SensorEntityDescription, ...] = (
    Concept2SensorEntityDescription(
        key="profile",
        translation_key="profile",
        icon="mdi:account",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _profile_state(data),
        attrs_fn=lambda data: {
            "id": data.profile.id,
            "username": data.profile.username,
            "country": data.profile.country,
            "logbook_privacy": data.profile.logbook_privacy,
        },
    ),
    Concept2SensorEntityDescription(
        key="last_successful_update",
        translation_key="last_successful_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.fetched_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Concept2 Logbook sensors."""

    coordinator: Concept2LogbookCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        Concept2LogbookSensor(coordinator, config_entry, description)
        for description in (
            *LATEST_WORKOUT_SENSORS,
            *DIAGNOSTIC_SENSORS,
            *_summary_sensor_descriptions(coordinator.summary_filters),
        )
    )


class Concept2LogbookSensor(
    CoordinatorEntity[Concept2LogbookCoordinator], SensorEntity
):
    """Concept2 Logbook sensor."""

    entity_description: Concept2SensorEntityDescription

    def __init__(
        self,
        coordinator: Concept2LogbookCoordinator,
        config_entry: ConfigEntry,
        description: Concept2SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)
        self.config_entry = config_entry
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_unique_id = (
            f"{config_entry.data[CONF_PROFILE_ID]}_{description.key}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""

        return DeviceInfo(
            identifiers={(DOMAIN, str(self.config_entry.data[CONF_PROFILE_ID]))},
            manufacturer="Concept2",
            name=self.config_entry.data.get(CONF_PROFILE_NAME, self.config_entry.title),
            configuration_url="https://log.concept2.com/log",
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""

        if self.coordinator.data is None:
            return None

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""

        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.available_fn(self.coordinator.data)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes."""

        if self.entity_description.attrs_fn is None or self.coordinator.data is None:
            return None

        return self.entity_description.attrs_fn(self.coordinator.data)


def _tenths_to_seconds(value: int | float | None) -> float | None:
    if value is None:
        return None

    return round(float(value) / 10, 1)


def _format_tenths(value: int | float | None) -> str | None:
    if value is None:
        return None

    tenths = round(float(value))
    total_seconds, decimal = divmod(tenths, 10)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}.{decimal}"


def _workout_pace_formatted(workout: Workout | None) -> str | None:
    if workout is None or not workout.distance:
        return None

    pace = round(workout.time * 500 / workout.distance)
    return _format_tenths(pace)


def _profile_state(data: Concept2LogbookData) -> str:
    names = [data.profile.first_name, data.profile.last_name]
    full_name = " ".join(name for name in names if name)
    return full_name or data.profile.username or str(data.profile.id)


def _workout_attributes(workout: Workout | None) -> dict[str, Any]:
    if workout is None:
        return {}

    return {
        "id": workout.id,
        "date": workout.date,
        "date_utc": workout.date_utc,
        "timezone": workout.timezone,
        "type": workout.type,
        "workout_type": workout.workout_type,
        "machine_type": workout.machine_type,
        "distance": workout.distance,
        "time": _tenths_to_seconds(workout.time),
        "time_formatted": workout.time_formatted,
        "calories": workout.calories,
        "stroke_rate": workout.stroke_rate,
        "stroke_count": workout.stroke_count,
        "drag_factor": workout.drag_factor,
        "source": workout.source,
        "verified": workout.verified,
        "ranked": workout.ranked,
        "comments": workout.comments,
        "pace": _workout_pace_formatted(workout),
    }


def _summary_sensor_descriptions(
    summary_filters: list[SummaryFilter],
) -> list[Concept2SensorEntityDescription]:
    descriptions: list[Concept2SensorEntityDescription] = []

    for summary_filter in summary_filters:
        descriptions.extend(
            [
                _summary_description(
                    summary_filter,
                    "count",
                    icon="mdi:counter",
                    value_fn=lambda summary: summary.count,
                ),
                _summary_description(
                    summary_filter,
                    "distance",
                    native_unit_of_measurement=UnitOfLength.METERS,
                    device_class=SensorDeviceClass.DISTANCE,
                    value_fn=lambda summary: summary.distance,
                ),
                _summary_description(
                    summary_filter,
                    "time",
                    native_unit_of_measurement=UnitOfTime.SECONDS,
                    device_class=SensorDeviceClass.DURATION,
                    value_fn=lambda summary: _tenths_to_seconds(summary.time),
                ),
                _summary_description(
                    summary_filter,
                    "calories",
                    native_unit_of_measurement="kcal",
                    icon="mdi:fire",
                    value_fn=lambda summary: summary.calories,
                    available_fn=lambda summary: summary.calories is not None,
                ),
            ]
        )

    return descriptions


def _summary_description(
    summary_filter: SummaryFilter,
    metric: str,
    *,
    value_fn: Callable[[WorkoutSummary], Any],
    available_fn: Callable[[WorkoutSummary], bool] = lambda summary: True,
    native_unit_of_measurement: str | None = None,
    device_class: SensorDeviceClass | None = None,
    icon: str | None = None,
) -> Concept2SensorEntityDescription:
    summary_key = _summary_key(summary_filter.period, summary_filter.workout_type)
    entity_key = _summary_entity_key(summary_filter, metric)
    translation_key = _summary_entity_key(summary_filter, metric)

    return Concept2SensorEntityDescription(
        key=entity_key,
        translation_key=translation_key,
        native_unit_of_measurement=native_unit_of_measurement,
        device_class=device_class,
        icon=icon,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: value_fn(data.summaries[summary_key]),
        available_fn=lambda data: summary_key in data.summaries
        and available_fn(data.summaries[summary_key]),
        attrs_fn=lambda data: {
            "period": summary_filter.period,
            "period_name": SUMMARY_PERIODS.get(
                summary_filter.period, summary_filter.period
            ),
            "workout_type": summary_filter.workout_type,
            "workout_type_name": WORKOUT_TYPES.get(
                summary_filter.workout_type, summary_filter.workout_type
            ),
        },
    )


def _summary_key(period: str, workout_type: str) -> str:
    return f"{period}_{workout_type}"


def _summary_entity_key(summary_filter: SummaryFilter, metric: str) -> str:
    if summary_filter.period == "all_time" and summary_filter.workout_type == "all":
        return f"summary_{metric}"

    return f"summary_{summary_filter.period}_{summary_filter.workout_type}_{metric}"

