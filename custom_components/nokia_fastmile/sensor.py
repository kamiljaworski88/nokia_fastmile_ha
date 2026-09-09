from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_HOST,
    DATA_5G_RSRP,
    DATA_5G_RSRP_STRENGTH_INDEX,
    DATA_5G_RSRQ,
    DATA_5G_SIGNAL_LEVEL,
    DATA_5G_SINR,
    DATA_CELLULAR_BYTES_RECEIVED,
    DATA_CELLULAR_BYTES_SENT,
    DATA_CONNECTION_STATE,
    DATA_CONNECTED_DEVICES,
    DATA_ETHERNET_BYTES_RECEIVED,
    DATA_ETHERNET_BYTES_SENT,
    DATA_ETHERNET_PACKETS_RECEIVED,
    DATA_ETHERNET_PACKETS_SENT,
    DATA_LTE_RSRP,
    DATA_LTE_RSRP_STRENGTH_INDEX,
    DATA_LTE_RSRQ,
    DATA_LTE_RSSI,
    DATA_LTE_SIGNAL_LEVEL,
    DATA_LTE_SINR,
    DATA_SERIAL_NUMBER,
    DATA_SW_VERSION,
    DATA_UNREAD_SMS,
    DATA_UPTIME,
    DATA_WAN_ACTIVE,
    DATA_WAN_MODE,
    DOMAIN,
    NAME,
)
from .coordinator import NokiaFastMileCoordinator


@dataclass(frozen=True, kw_only=True)
class NokiaSensorDescription(SensorEntityDescription):
    data_key: str = ""


SENSORS: tuple[NokiaSensorDescription, ...] = (
    # ── 5G signal ─────────────────────────────────────────────────────────────
    NokiaSensorDescription(
        key="5g_rsrp",
        data_key=DATA_5G_RSRP,
        name="5G RSRP",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal-5g",
    ),
    NokiaSensorDescription(
        key="5g_rsrq",
        data_key=DATA_5G_RSRQ,
        name="5G RSRQ",
        native_unit_of_measurement="dB",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal-5g",
    ),
    NokiaSensorDescription(
        key="5g_sinr",
        data_key=DATA_5G_SINR,
        name="5G SINR",
        native_unit_of_measurement="dB",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    NokiaSensorDescription(
        key="5g_signal_level",
        data_key=DATA_5G_SIGNAL_LEVEL,
        name="5G poziom sygnału",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal-5g",
    ),
    NokiaSensorDescription(
        key="5g_rsrp_strength_index",
        data_key=DATA_5G_RSRP_STRENGTH_INDEX,
        name="5G RSRP Strength Index",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal-5g",
    ),
    # ── LTE signal ────────────────────────────────────────────────────────────
    NokiaSensorDescription(
        key="lte_rsrp",
        data_key=DATA_LTE_RSRP,
        name="LTE RSRP",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
    ),
    NokiaSensorDescription(
        key="lte_rsrq",
        data_key=DATA_LTE_RSRQ,
        name="LTE RSRQ",
        native_unit_of_measurement="dB",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
    ),
    NokiaSensorDescription(
        key="lte_rssi",
        data_key=DATA_LTE_RSSI,
        name="LTE RSSI",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
    ),
    NokiaSensorDescription(
        key="lte_sinr",
        data_key=DATA_LTE_SINR,
        name="LTE SINR",
        native_unit_of_measurement="dB",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    NokiaSensorDescription(
        key="lte_signal_level",
        data_key=DATA_LTE_SIGNAL_LEVEL,
        name="LTE poziom sygnału",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
    ),
    NokiaSensorDescription(
        key="lte_rsrp_strength_index",
        data_key=DATA_LTE_RSRP_STRENGTH_INDEX,
        name="LTE RSRP Strength Index",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
    ),
    # ── Connection / WAN ──────────────────────────────────────────────────────
    NokiaSensorDescription(
        key="connection_state",
        data_key=DATA_CONNECTION_STATE,
        name="Stan połączenia",
        icon="mdi:connection",
    ),
    NokiaSensorDescription(
        key="wan_mode",
        data_key=DATA_WAN_MODE,
        name="Tryb WAN",
        icon="mdi:router-network",
    ),
    NokiaSensorDescription(
        key="wan_active",
        data_key=DATA_WAN_ACTIVE,
        name="Aktywny WAN",
        icon="mdi:antenna",
    ),
    # ── Transfer data ───────────────────────────────────────────────────────
    NokiaSensorDescription(
        key="cellular_bytes_received",
        data_key=DATA_CELLULAR_BYTES_RECEIVED,
        name="Cellular Bytes Received",
        native_unit_of_measurement="B",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:download-network",
        entity_registry_enabled_default=False,
    ),
    NokiaSensorDescription(
        key="cellular_bytes_sent",
        data_key=DATA_CELLULAR_BYTES_SENT,
        name="Cellular Bytes Sent",
        native_unit_of_measurement="B",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:upload-network",
        entity_registry_enabled_default=False,
    ),
    NokiaSensorDescription(
        key="ethernet_bytes_received",
        data_key=DATA_ETHERNET_BYTES_RECEIVED,
        name="Ethernet Bytes Received",
        native_unit_of_measurement="B",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:download-network",
        entity_registry_enabled_default=False,
    ),
    NokiaSensorDescription(
        key="ethernet_bytes_sent",
        data_key=DATA_ETHERNET_BYTES_SENT,
        name="Ethernet Bytes Sent",
        native_unit_of_measurement="B",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:upload-network",
        entity_registry_enabled_default=False,
    ),
    NokiaSensorDescription(
        key="ethernet_packets_received",
        data_key=DATA_ETHERNET_PACKETS_RECEIVED,
        name="Ethernet Packets Received",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:package-down",
        entity_registry_enabled_default=False,
    ),
    NokiaSensorDescription(
        key="ethernet_packets_sent",
        data_key=DATA_ETHERNET_PACKETS_SENT,
        name="Ethernet Packets Sent",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:package-up",
        entity_registry_enabled_default=False,
    ),
    # ── Device info ───────────────────────────────────────────────────────────
    NokiaSensorDescription(
        key="uptime",
        data_key=DATA_UPTIME,
        name="Uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:timer-outline",
    ),
    NokiaSensorDescription(
        key="connected_devices",
        data_key=DATA_CONNECTED_DEVICES,
        name="Podłączone urządzenia",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:devices",
    ),
    NokiaSensorDescription(
        key="unread_sms",
        data_key=DATA_UNREAD_SMS,
        name="Nieprzeczytane SMS",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:message-badge",
    ),
    NokiaSensorDescription(
        key="sw_version",
        data_key=DATA_SW_VERSION,
        name="Wersja oprogramowania",
        icon="mdi:package-up",
        entity_registry_enabled_default=False,
    ),
    NokiaSensorDescription(
        key="serial_number",
        data_key=DATA_SERIAL_NUMBER,
        name="Numer seryjny",
        icon="mdi:barcode",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NokiaFastMileCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NokiaFastMileSensor(coordinator, entry, desc) for desc in SENSORS
    )


class NokiaFastMileSensor(CoordinatorEntity[NokiaFastMileCoordinator], SensorEntity):
    """Single sensor entity backed by Nokia FastMile coordinator data."""

    entity_description: NokiaSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NokiaFastMileCoordinator,
        entry: ConfigEntry,
        description: NokiaSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{NAME} ({entry.data[CONF_HOST]})",
            manufacturer="Nokia",
            model="FastMile 5G14-B",
            sw_version=(
                coordinator.data.get(DATA_SW_VERSION) if coordinator.data else None
            ),
        )

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)
