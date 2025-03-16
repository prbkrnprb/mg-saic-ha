# File: config_flow.py

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    AFTER_ACTION_UPDATE_INTERVAL_DELAY,
    CONF_HAS_BATTERY_HEATING,
    CONF_HAS_HEATED_SEATS,
    CONF_HAS_SUNROOF,
    COUNTRY_CODES,
    DEFAULT_AC_LONG_INTERVAL,
    DEFAULT_ALARM_LONG_INTERVAL,
    DEFAULT_BATTERY_HEATING_LONG_INTERVAL,
    DEFAULT_CHARGING_CURRENT_LONG_INTERVAL,
    DEFAULT_CHARGING_LONG_INTERVAL,
    DEFAULT_CHARGING_PORT_LOCK_LONG_INTERVAL,
    DEFAULT_FRONT_DEFROST_LONG_INTERVAL,
    DEFAULT_HEATED_SEATS_LONG_INTERVAL,
    DEFAULT_LOCK_UNLOCK_LONG_INTERVAL,
    DEFAULT_REAR_WINDOW_HEAT_LONG_INTERVAL,
    DEFAULT_SUNROOF_LONG_INTERVAL,
    DEFAULT_TAILGATE_LONG_INTERVAL,
    DEFAULT_TARGET_SOC_LONG_INTERVAL,
    DOMAIN,
    LOGGER,
    REGION_BASE_URIS,
    REGION_CHOICES,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_AFTER_SHUTDOWN,
    UPDATE_INTERVAL_CHARGING,
    UPDATE_INTERVAL_GRACE_PERIOD,
    UPDATE_INTERVAL_POWERED,
)
from saic_ismart_client_ng import SaicApi
from saic_ismart_client_ng.model import SaicApiConfiguration


@callback
def configured_vins(hass):
    """Return a set of configured MG SAIC VINs."""
    return set(
        entry.data.get("vin") for entry in hass.config_entries.async_entries(DOMAIN)
    )


class SAICMGConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MG SAIC integration."""

    VERSION = 1

    def __init__(self):
        self.login_type = None
        self.username = None
        self.password = None
        self.country_code = None
        self.region = None
        self.vin = None
        self.vehicles = []
        self.vehicle_type = None

        self.has_sunroof = False
        self.has_heated_seats = False
        self.has_battery_heating = False

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self.login_type = user_input["login_type"]
            return await self.async_step_login_data()

        data_schema = vol.Schema(
            {
                vol.Required("login_type"): vol.In(["email", "phone"]),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_login_data(self, user_input=None):
        errors = {}
        if user_input is not None:
            self.username = user_input["username"]
            self.password = user_input["password"]
            username_is_email = self.login_type == "email"

            self.region = user_input["region"]

            if not username_is_email:
                self.country_code = user_input["country_code"].replace("+", "")
                self.username = self.username.replace(" ", "").replace("+", "")

            try:
                await self.fetch_vehicle_data(username_is_email)
                return await self.async_step_select_vehicle()
            except Exception as e:
                errors["base"] = "auth"
                LOGGER.error(f"Failed to authenticate or fetch vehicle data: {e}")

        if self.login_type == "email":
            data_schema = vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("region"): vol.In(REGION_CHOICES),
                }
            )
        else:  # phone login
            country_options = {code["code"]: code["code"] for code in COUNTRY_CODES}
            data_schema = vol.Schema(
                {
                    vol.Required("country_code"): vol.In(country_options),
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("region"): vol.In(REGION_CHOICES),
                }
            )

        return self.async_show_form(
            step_id="login_data", data_schema=data_schema, errors=errors
        )

    async def async_step_select_vehicle(self, user_input=None):
        errors = {}
        if user_input is not None:
            selected_vin = user_input["vin"]
            self.vehicle_type = user_input["vehicle_type"]  # Store vehicle type

            self.vin = selected_vin
            return await self.async_step_vehicle_capabilities()

        # Add vehicle_type selection with fallback for user confirmation
        data_schema = vol.Schema(
            {
                vol.Required("vin"): vol.In(self.vehicles),
                vol.Required("vehicle_type"): vol.In(["BEV", "PHEV", "HEV", "ICE"]),
            }
        )

        return self.async_show_form(
            step_id="select_vehicle", data_schema=data_schema, errors=errors
        )

    async def async_step_vehicle_capabilities(self, user_input=None):
        """Step for configuring vehicle capabilities."""
        errors = {}
        if user_input is not None:
            self.has_sunroof = user_input["has_sunroof"]
            self.has_heated_seats = user_input["has_heated_seats"]
            self.has_battery_heating = user_input["has_battery_heating"]

            return self.async_create_entry(
                title=f"MG SAIC - {self.vin}",
                data={
                    "username": self.username,
                    "password": self.password,
                    "country_code": self.country_code,
                    "region": self.region,
                    "vin": self.vin,
                    "login_type": self.login_type,
                    "vehicle_type": self.vehicle_type,
                    "has_sunroof": self.has_sunroof,
                    "has_heated_seats": self.has_heated_seats,
                    "has_battery_heating": self.has_battery_heating,
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required("has_sunroof", default=self.has_sunroof): bool,
                vol.Required("has_heated_seats", default=self.has_heated_seats): bool,
                vol.Required(
                    "has_battery_heating", default=self.has_battery_heating
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="vehicle_capabilities", data_schema=data_schema, errors=errors
        )

    async def fetch_vehicle_data(self, username_is_email):
        """Authenticate and fetch vehicle data."""

        # Get the base_url for the selected region
        base_uri = REGION_BASE_URIS.get(self.region)
        if not base_uri:
            raise ValueError(f"Base URL not defined for region: {self.region}")

        config = SaicApiConfiguration(
            username=self.username,
            password=self.password,
            base_uri=base_uri,
            phone_country_code=self.country_code if not username_is_email else None,
            username_is_email=username_is_email,
        )

        LOGGER.debug(
            "Logging in with Username: %s, Country Code: %s, Email: %s, Region: %s, Base URL: %s",
            self.username,
            self.country_code,
            username_is_email,
            self.region,
            base_uri,
        )

        # Initialize SaicApi in the executor to avoid blocking the event loop
        saic_api = await self.hass.async_add_executor_job(SaicApi, config)

        try:
            await saic_api.login()
            vehicle_list_resp = await saic_api.vehicle_list()
            LOGGER.debug("Vehicle list response: %s", vehicle_list_resp)

            if (
                not hasattr(vehicle_list_resp, "vinList")
                or not vehicle_list_resp.vinList
            ):
                raise Exception("Vehicle list API returned no vehicles")

            # Now safely iterate over vinList
            self.vehicles = [car.vin for car in vehicle_list_resp.vinList]
            LOGGER.info("Fetched vehicle data successfully.")
        except Exception as e:
            LOGGER.error("Error fetching vehicle data: %s", e)
            raise

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SAICMGOptionsFlowHandler(config_entry)


class SAICMGOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for MG SAIC integration."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.entry_id = config_entry.entry_id

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        self.options = self.config_entry.options

        # Access options directly using self.options
        data_schema = vol.Schema(
            {
                # Vehicle Capabilities
                vol.Optional(
                    "has_sunroof",
                    default=self.options.get(
                        "has_sunroof",
                        self.config_entry.data.get("has_sunroof", False),
                    ),
                ): bool,
                vol.Optional(
                    "has_heated_seats",
                    default=self.options.get(
                        "has_heated_seats",
                        self.config_entry.data.get("has_heated_seats", False),
                    ),
                ): bool,
                vol.Optional(
                    "has_battery_heating",
                    default=self.options.get(
                        "has_battery_heating",
                        self.config_entry.data.get("has_battery_heating", False),
                    ),
                ): bool,
                # Update Intervals in minutes
                vol.Optional(
                    "update_interval",
                    default=self.options.get(
                        "update_interval", self.get_minutes(UPDATE_INTERVAL)
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "charging_update_interval",
                    default=self.options.get(
                        "charging_update_interval",
                        self.get_minutes(UPDATE_INTERVAL_CHARGING),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "powered_update_interval",
                    default=self.options.get(
                        "powered_update_interval",
                        self.get_minutes(UPDATE_INTERVAL_POWERED),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "after_shutdown_update_interval",
                    default=self.options.get(
                        "after_shutdown_update_interval",
                        self.get_minutes(UPDATE_INTERVAL_AFTER_SHUTDOWN),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "grace_period_update_interval",
                    default=self.options.get(
                        "grace_period_update_interval",
                        self.get_minutes(UPDATE_INTERVAL_GRACE_PERIOD),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                # After action delay in seconds
                vol.Optional(
                    "after_action_delay",
                    default=self.options.get(
                        "after_action_delay",
                        self.get_seconds(AFTER_ACTION_UPDATE_INTERVAL_DELAY),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                # Long-interval updates after actions in minutes
                vol.Optional(
                    "alarm_long_interval",
                    default=self.options.get(
                        "alarm_long_interval",
                        self.get_minutes(DEFAULT_ALARM_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "ac_long_interval",
                    default=self.options.get(
                        "ac_long_interval", self.get_minutes(DEFAULT_AC_LONG_INTERVAL)
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "front_defrost_long_interval",
                    default=self.options.get(
                        "front_defrost_long_interval",
                        self.get_minutes(DEFAULT_FRONT_DEFROST_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "rear_window_heat_long_interval",
                    default=self.options.get(
                        "rear_window_heat_long_interval",
                        self.get_minutes(DEFAULT_REAR_WINDOW_HEAT_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "lock_unlock_long_interval",
                    default=self.options.get(
                        "lock_unlock_long_interval",
                        self.get_minutes(DEFAULT_LOCK_UNLOCK_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "charging_port_lock_long_interval",
                    default=self.options.get(
                        "charging_port_lock_long_interval",
                        self.get_minutes(DEFAULT_CHARGING_PORT_LOCK_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "heated_seats_long_interval",
                    default=self.options.get(
                        "heated_seats_long_interval",
                        self.get_minutes(DEFAULT_HEATED_SEATS_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "battery_heating_long_interval",
                    default=self.options.get(
                        "battery_heating_long_interval",
                        self.get_minutes(DEFAULT_BATTERY_HEATING_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "charging_long_interval",
                    default=self.options.get(
                        "charging_long_interval",
                        self.get_minutes(DEFAULT_CHARGING_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "sunroof_long_interval",
                    default=self.options.get(
                        "sunroof_long_interval",
                        self.get_minutes(DEFAULT_SUNROOF_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "tailgate_long_interval",
                    default=self.options.get(
                        "tailgate_long_interval",
                        self.get_minutes(DEFAULT_TAILGATE_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "target_soc_long_interval",
                    default=self.options.get(
                        "target_soc_long_interval",
                        self.get_minutes(DEFAULT_TARGET_SOC_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "charging_current_long_interval",
                    default=self.options.get(
                        "charging_current_long_interval",
                        self.get_minutes(DEFAULT_CHARGING_CURRENT_LONG_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)

    def get_minutes(self, interval):
        """Convert timedelta to minutes."""
        return int(interval.total_seconds() // 60)

    def get_seconds(self, interval):
        """Convert timedelta to seconds."""
        return int(interval.total_seconds())
