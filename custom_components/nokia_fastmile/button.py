"""Button entities for Nokia FastMile 5G."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, DATA_SW_VERSION, DOMAIN, NAME
from .coordinator import NokiaFastMileCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nokia FastMile button entities."""
    coordinator: NokiaFastMileCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NokiaFastMileRestartButton(coordinator, entry)])


class NokiaFastMileRestartButton(
    CoordinatorEntity[NokiaFastMileCoordinator], ButtonEntity
):
    """Restart the Nokia FastMile router."""

    _attr_has_entity_name = True
    _attr_name = "Restart router"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: NokiaFastMileCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the restart button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_restart"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{NAME} ({entry.data[CONF_HOST]})",
            manufacturer="Nokia",
            model="FastMile 5G14-B",
            sw_version=(
                coordinator.data.get(DATA_SW_VERSION) if coordinator.data else None
            ),
        )

    async def async_press(self) -> None:
        """Restart the router."""
        await self.coordinator.async_reboot()
