# File: binary_sensor.py

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, LOGGER
from .utils import create_device_info


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MG SAIC binary sensors."""
    coordinator = hass.data[DOMAIN][f"{entry.entry_id}_coordinator"]

    try:
        if not coordinator.data.get("info"):
            LOGGER.error("Failed to retrieve vehicle info.")
            return

        vin_info = coordinator.vin_info

        # Determine if vehicle is RHD
        lrd_value = None
        for config_item in vin_info.vehicleModelConfiguration:
            if config_item.itemCode == "LRD":
                lrd_value = config_item.itemValue
                break

        is_rhd = lrd_value == "1"

        # Set door names based on LHD/RHD
        if is_rhd:
            driver_door_name = "Door Front Right"
            passenger_door_name = "Door Front Left"
        else:
            driver_door_name = "Door Front Left"
            passenger_door_name = "Door Front Right"

        binary_sensors = [
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Bonnet Status",
                "bonnetStatus",
                BinarySensorDeviceClass.DOOR,
                "mdi:car",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Boot Status",
                "bootStatus",
                BinarySensorDeviceClass.DOOR,
                "mdi:car-back",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Dipped Beam Status",
                "dippedBeamStatus",
                BinarySensorDeviceClass.LIGHT,
                "mdi:car-light-dimmed",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                driver_door_name,
                "driverDoor",
                BinarySensorDeviceClass.DOOR,
                "mdi:car-door",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                passenger_door_name,
                "passengerDoor",
                BinarySensorDeviceClass.DOOR,
                "mdi:car-door",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Door Rear Left",
                "rearLeftDoor",
                BinarySensorDeviceClass.DOOR,
                "mdi:car-door",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Door Rear Right",
                "rearRightDoor",
                BinarySensorDeviceClass.DOOR,
                "mdi:car-door",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Engine Status",
                "engineStatus",
                BinarySensorDeviceClass.POWER,
                "mdi:engine",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "HVAC Status",
                "remoteClimateStatus",
                BinarySensorDeviceClass.RUNNING,
                "mdi:air-conditioner",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Lock Status",
                "lockStatus",
                BinarySensorDeviceClass.LOCK,
                "mdi:car-key",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Main Beam Status",
                "mainBeamStatus",
                BinarySensorDeviceClass.LIGHT,
                "mdi:car-light-high",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Side Light Status",
                "sideLightStatus",
                BinarySensorDeviceClass.LIGHT,
                "mdi:car-parking-lights",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Wheel Tyre Monitor Status",
                "wheelTyreMonitorStatus",
                BinarySensorDeviceClass.PROBLEM,
                "mdi:car-tire-alert",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Window Front Left",
                "driverWindow",
                BinarySensorDeviceClass.WINDOW,
                "mdi:car-door",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Window Front Right",
                "passengerWindow",
                BinarySensorDeviceClass.WINDOW,
                "mdi:car-door",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Window Rear Left",
                "rearLeftWindow",
                BinarySensorDeviceClass.WINDOW,
                "mdi:car-door",
                "status",
            ),
            SAICMGBinarySensor(
                coordinator,
                entry,
                "Window Rear Right",
                "rearRightWindow",
                BinarySensorDeviceClass.WINDOW,
                "mdi:car-door",
                "status",
            ),
        ]

        # Add charging-related binary sensors
        if coordinator.vehicle_type in ["BEV", "PHEV"]:
            charging_binary_sensors = [
                SAICMGChargingBinarySensor(
                    coordinator,
                    entry,
                    "Charging Gun State",
                    "chargingGunState",
                    BinarySensorDeviceClass.PLUG,
                    "mdi:ev-plug-type2",
                    "rvsChargeStatus",
                    "charging",
                ),
            ]

            binary_sensors.extend(charging_binary_sensors)

        if coordinator.has_sunroof:
            binary_sensors.append(
                SAICMGBinarySensor(
                    coordinator,
                    entry,
                    "Sunroof Status",
                    "sunroofStatus",
                    BinarySensorDeviceClass.WINDOW,
                    "mdi:car-door",
                    "status",
                ),
            )

        async_add_entities(binary_sensors, update_before_add=True)

    except Exception as e:
        LOGGER.error("Error setting up MG SAIC binary sensors: %s", e)


# GENERAL VEHICLE BINARY SENSORS
class SAICMGBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a MG SAIC binary sensor."""

    def __init__(self, coordinator, entry, name, field, device_class, icon, data_type):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._name = name
        self._field = field
        self._device_class = device_class
        self._icon = icon
        self._data_type = data_type
        vin_info = self.coordinator.vin_info
        self._unique_id = f"{entry.entry_id}_{vin_info.vin}_{field}_binary_sensor"

        self._device_info = create_device_info(coordinator, entry.entry_id)

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return self._unique_id

    @property
    def name(self):
        vin_info = self.coordinator.vin_info
        return f"{vin_info.brandName} {vin_info.modelName} {self._name}"

    @property
    def available(self):
        """Return True if the entity is available."""
        required_data = self.coordinator.data.get(self._data_type)
        return self.coordinator.last_update_success and required_data is not None

    @property
    def is_on(self):
        data = self.coordinator.data.get(self._data_type)
        if data:
            if self._data_type == "status":
                status_data = getattr(data, "basicVehicleStatus", None)
                if status_data:
                    value = getattr(status_data, self._field, None)
                    if value is not None:
                        if self._field == "lockStatus":
                            return value == 0
                        return bool(value)
            elif self._data_type == "charging":
                charging_status_data = getattr(data, "rvsChargeStatus", None)
                if charging_status_data:
                    value = getattr(charging_status_data, self._field, None)
                    if value is not None:
                        return bool(value)
        return False

    @property
    def device_class(self):
        """Return the device class of this binary sensor."""
        return self._device_class

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def device_info(self):
        """Return device info"""
        return self._device_info


# CHARGING SENSORS
class SAICMGChargingBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a MG SAIC charging binary sensor."""

    def __init__(
        self,
        coordinator,
        entry,
        name,
        field,
        device_class,
        icon,
        data_source,
        data_type,
    ):
        """Initialize the charging binary sensor."""
        super().__init__(coordinator)
        self._name = name
        self._field = field
        self._device_class = device_class
        self._icon = icon
        self._data_source = data_source
        self._data_type = data_type
        vin_info = self.coordinator.vin_info
        self._unique_id = f"{entry.entry_id}_{vin_info.vin}_{field}_binary_sensor"

        self._device_info = create_device_info(coordinator, entry.entry_id)

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the binary sensor."""
        vin_info = self.coordinator.vin_info
        return f"{vin_info.brandName} {vin_info.modelName} {self._name}"

    @property
    def available(self):
        """Return True if the entity is available."""
        required_data = self.coordinator.data.get(self._data_type)
        return self.coordinator.last_update_success and required_data is not None

    @property
    def is_on(self):
        """Return true if the charging gun is connected."""
        charging_data = self.coordinator.data.get(self._data_type)
        if charging_data:
            data_source = getattr(charging_data, self._data_source, None)
            if data_source:
                value = getattr(data_source, self._field, None)
                if value is not None:
                    return bool(value)
        return None

    @property
    def device_class(self):
        """Return the device class of this binary sensor."""
        return self._device_class

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def device_info(self):
        """Return device info"""
        return self._device_info
