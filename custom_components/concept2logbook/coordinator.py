"""Data coordinator for the Concept2 Logbook integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import NamedTuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pyconcept2 import (
    AthleteProfile,
    Concept2APIError,
    Concept2AuthenticationError,
    Concept2Client,
    Concept2RequestError,
    Workout,
    WorkoutSummary,
)

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_SUMMARY_PERIODS,
    CONF_WORKOUT_TYPES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SUMMARY_PERIODS,
    DEFAULT_WORKOUT_TYPES,
    DOMAIN,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Concept2LogbookData:
    """Fetched Concept2 Logbook data."""

    profile: AthleteProfile
    latest_workout: Workout | None
    summaries: dict[str, WorkoutSummary]
    fetched_at: datetime


class SummaryFilter(NamedTuple):
    """Resolved Concept2 summary filter."""

    period: str
    workout_type: str
    from_date: str | None
    to_date: str | None
    api_workout_type: str | None


class Concept2LogbookCoordinator(DataUpdateCoordinator[Concept2LogbookData]):
    """Coordinator that fetches Concept2 Logbook data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self.config_entry = entry
        self.client = Concept2Client(access_token=entry.data[CONF_ACCESS_TOKEN])

        super().__init__(
            hass,
            _LOGGER,
            name=f"{NAME} {entry.title}",
            update_interval=_scan_interval(entry),
        )

    async def _async_update_data(self) -> Concept2LogbookData:
        """Fetch data from Concept2."""

        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except Concept2AuthenticationError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except (Concept2APIError, Concept2RequestError, ValueError) as exc:
            raise UpdateFailed(str(exc)) from exc

    def _fetch_data(self) -> Concept2LogbookData:
        """Fetch all data using the synchronous pyconcept2 client."""

        profile = self.client.get_profile()
        workouts = self.client.get_workouts(number=250, all_pages=True)
        latest_workout = workouts[0] if workouts else None
        summaries = {
            _summary_key(summary_filter.period, summary_filter.workout_type):
            _summarize_workouts(
                workouts,
                from_date=summary_filter.from_date,
                to_date=summary_filter.to_date,
                workout_type=summary_filter.api_workout_type,
            )
            for summary_filter in self.summary_filters
        }

        return Concept2LogbookData(
            profile=profile,
            latest_workout=latest_workout,
            summaries=summaries,
            fetched_at=datetime.now().astimezone(),
        )

    def close(self) -> None:
        """Close the underlying API client."""

        self.client.close()

    @property
    def summary_filters(self) -> list[SummaryFilter]:
        """Return enabled summary filters from entry options."""

        periods = _option_list(
            self.config_entry.options.get(CONF_SUMMARY_PERIODS),
            DEFAULT_SUMMARY_PERIODS,
        )
        workout_types = _option_list(
            self.config_entry.options.get(CONF_WORKOUT_TYPES),
            DEFAULT_WORKOUT_TYPES,
        )

        filters: list[SummaryFilter] = []
        for period in periods:
            from_date, to_date = _period_dates(period)
            for workout_type in workout_types:
                filters.append(
                    SummaryFilter(
                        period=period,
                        workout_type=workout_type,
                        from_date=from_date,
                        to_date=to_date,
                        api_workout_type=None
                        if workout_type == "all"
                        else workout_type,
                    )
                )

        return filters


def _scan_interval(entry: ConfigEntry) -> timedelta:
    raw_value = entry.options.get(CONF_SCAN_INTERVAL)
    if raw_value is None:
        return DEFAULT_SCAN_INTERVAL

    try:
        return timedelta(seconds=int(raw_value))
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL


def _option_list(value: object, fallback: list[str]) -> list[str]:
    if not value:
        return fallback

    if isinstance(value, list):
        return [str(item) for item in value]

    return [str(value)]


def _period_dates(period: str) -> tuple[str | None, str | None]:
    today = date.today()

    if period == "current_year":
        return date(today.year, 1, 1).isoformat(), today.isoformat()

    if period == "current_month":
        return date(today.year, today.month, 1).isoformat(), today.isoformat()

    if period == "last_30_days":
        return (today - timedelta(days=29)).isoformat(), today.isoformat()

    if period == "last_7_days":
        return (today - timedelta(days=6)).isoformat(), today.isoformat()

    if period == "concept2_season":
        start_year = today.year if today.month >= 5 else today.year - 1
        return date(start_year, 5, 1).isoformat(), today.isoformat()

    return None, None


def _summary_key(period: str, workout_type: str) -> str:
    return f"{period}_{workout_type}"


def _summarize_workouts(
    workouts: list[Workout],
    *,
    from_date: str | None,
    to_date: str | None,
    workout_type: str | None,
) -> WorkoutSummary:
    filtered = [
        workout
        for workout in workouts
        if _workout_matches(workout, from_date, to_date, workout_type)
    ]
    calories = [
        workout.calories for workout in filtered if workout.calories is not None
    ]

    return WorkoutSummary(
        count=len(filtered),
        distance=sum(workout.distance for workout in filtered),
        time=sum(workout.time for workout in filtered),
        calories=sum(calories) if calories else None,
    )


def _workout_matches(
    workout: Workout,
    from_date: str | None,
    to_date: str | None,
    workout_type: str | None,
) -> bool:
    workout_day = workout.date[:10]

    if from_date is not None and workout_day < from_date:
        return False

    if to_date is not None and workout_day > to_date:
        return False

    if workout_type is not None and workout.type != workout_type:
        return False

    return True
