"""Config flow for the Concept2 Logbook integration."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from pyconcept2 import Concept2AuthenticationError, Concept2Client, Concept2Error

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SUMMARY_PERIODS,
    CONF_WORKOUT_TYPES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SUMMARY_PERIODS,
    DEFAULT_WORKOUT_TYPES,
    DOMAIN,
    MIN_SCAN_INTERVAL_SECONDS,
    SUMMARY_PERIODS,
    WORKOUT_TYPES,
)


class Concept2LogbookConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Concept2 Logbook."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            client = Concept2Client(access_token=user_input[CONF_ACCESS_TOKEN])
            try:
                profile = await self.hass.async_add_executor_job(client.get_profile)
            except Concept2AuthenticationError:
                errors[CONF_ACCESS_TOKEN] = "invalid_auth"
            except Concept2Error:
                errors["base"] = "cannot_connect"
            finally:
                await self.hass.async_add_executor_job(client.close)

            if not errors:
                profile_id = _profile_id(profile, user_input[CONF_ACCESS_TOKEN])

                await self.async_set_unique_id(profile_id)
                self._abort_if_unique_id_configured()

                profile_name = _profile_name(profile)
                title = user_input.get(CONF_NAME) or profile_name

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                        CONF_PROFILE_ID: profile_id,
                        CONF_PROFILE_NAME: profile_name,
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                        CONF_SUMMARY_PERIODS: DEFAULT_SUMMARY_PERIODS,
                        CONF_WORKOUT_TYPES: DEFAULT_WORKOUT_TYPES,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_config_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> Concept2LogbookOptionsFlow:
        """Create the options flow."""

        return Concept2LogbookOptionsFlow(config_entry)


class Concept2LogbookOptionsFlow(config_entries.OptionsFlow):
    """Handle Concept2 Logbook options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""

        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""

        errors: dict[str, str] = {}

        if user_input is not None:
            new_token = user_input.get(CONF_ACCESS_TOKEN)
            if new_token:
                client = Concept2Client(access_token=new_token)
                try:
                    profile = await self.hass.async_add_executor_job(
                        client.get_profile
                    )
                except Concept2AuthenticationError:
                    errors[CONF_ACCESS_TOKEN] = "invalid_auth"
                except Concept2Error:
                    errors["base"] = "cannot_connect"
                finally:
                    await self.hass.async_add_executor_job(client.close)

                if not errors:
                    profile_id = _profile_id(profile, new_token)
                    if profile_id != str(self._config_entry.data[CONF_PROFILE_ID]):
                        errors[CONF_ACCESS_TOKEN] = "wrong_account"

                    if not errors:
                        self.hass.config_entries.async_update_entry(
                            self._config_entry,
                            data={
                                **self._config_entry.data,
                                CONF_ACCESS_TOKEN: new_token,
                                CONF_PROFILE_NAME: _profile_name(profile),
                            },
                        )

            if not errors:
                options = {
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_SUMMARY_PERIODS: _non_empty_list(
                        user_input.get(CONF_SUMMARY_PERIODS),
                        DEFAULT_SUMMARY_PERIODS,
                    ),
                    CONF_WORKOUT_TYPES: _non_empty_list(
                        user_input.get(CONF_WORKOUT_TYPES),
                        DEFAULT_WORKOUT_TYPES,
                    ),
                }
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._config_entry, user_input),
            errors=errors,
        )


def _config_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    user_input = user_input or {}

    return vol.Schema(
        {
            vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, "")): str,
            vol.Required(
                CONF_ACCESS_TOKEN, default=user_input.get(CONF_ACCESS_TOKEN, "")
            ): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD, multiline=False)
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=user_input.get(
                    CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds())
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL_SECONDS,
                    max=86400,
                    step=60,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="seconds",
                )
            ),
        }
    )


def _options_schema(
    config_entry: ConfigEntry, user_input: dict[str, Any] | None
) -> vol.Schema:
    user_input = user_input or {}
    options = config_entry.options

    return vol.Schema(
        {
            vol.Optional(CONF_ACCESS_TOKEN, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD, multiline=False)
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=user_input.get(
                    CONF_SCAN_INTERVAL,
                    options.get(
                        CONF_SCAN_INTERVAL,
                        int(DEFAULT_SCAN_INTERVAL.total_seconds()),
                    ),
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL_SECONDS,
                    max=86400,
                    step=60,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="seconds",
                )
            ),
            vol.Required(
                CONF_SUMMARY_PERIODS,
                default=user_input.get(
                    CONF_SUMMARY_PERIODS,
                    options.get(CONF_SUMMARY_PERIODS, DEFAULT_SUMMARY_PERIODS),
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(SUMMARY_PERIODS),
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                    translation_key=CONF_SUMMARY_PERIODS,
                )
            ),
            vol.Required(
                CONF_WORKOUT_TYPES,
                default=user_input.get(
                    CONF_WORKOUT_TYPES,
                    options.get(CONF_WORKOUT_TYPES, DEFAULT_WORKOUT_TYPES),
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(WORKOUT_TYPES),
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                    translation_key=CONF_WORKOUT_TYPES,
                )
            ),
        }
    )


def _profile_id(profile: Any, access_token: str) -> str:
    profile_id = str(profile.id or profile.username)
    if profile_id == "None":
        return access_token[-8:]

    return profile_id


def _profile_name(profile: Any) -> str:
    names = [profile.first_name, profile.last_name]
    full_name = " ".join(name for name in names if name)
    return full_name or profile.username or f"Concept2 {profile.id}"


def _non_empty_list(value: Any, fallback: list[str]) -> list[str]:
    if not value:
        return fallback

    if isinstance(value, list):
        return value

    return [str(value)]
