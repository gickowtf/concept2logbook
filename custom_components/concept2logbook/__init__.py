"""Home Assistant integration for Concept2 Logbook."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import Concept2LogbookCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Concept2 Logbook from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    coordinator = Concept2LogbookCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Concept2 Logbook config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    if unload_ok:
        coordinator: Concept2LogbookCoordinator | None = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if coordinator is not None:
            await hass.async_add_executor_job(coordinator.close)

    return unload_ok


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""

    await hass.config_entries.async_reload(entry.entry_id)
