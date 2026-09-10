from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

try:
    from homeassistant.components.http import StaticPathConfig
except ImportError:  # Home Assistant < 2024.7
    StaticPathConfig = None  # type: ignore[misc, assignment]

from .const import DOMAIN
from .coordinator import NokiaFastMileCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button"]
FRONTEND_URL = f"/{DOMAIN}/nokia-fastmile-card.js"
FRONTEND_PATH = Path(__file__).with_name("nokia-fastmile-card.js")


async def _async_register_frontend(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("frontend_registered"):
        return

    if StaticPathConfig is not None and hasattr(
        hass.http, "async_register_static_paths"
    ):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL, str(FRONTEND_PATH), False)]
        )
    else:
        # Compatibility with Home Assistant 2024.1-2024.6.
        hass.http.register_static_path(FRONTEND_URL, str(FRONTEND_PATH), False)

    domain_data["frontend_registered"] = True


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register frontend assets independently of router availability."""
    await _async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Keep this call as a safeguard for config-entry-only loading paths.
    await _async_register_frontend(hass)

    coordinator = NokiaFastMileCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: NokiaFastMileCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unloaded
