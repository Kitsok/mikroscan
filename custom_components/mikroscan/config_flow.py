"""Config flow for the Mikroscan integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .client import MikroscanApiClient, MikroscanApiError
from .const import (
    CONF_SCAN_RANGE,
    CONF_WEB_PORT,
    DEFAULT_HOST,
    DEFAULT_SCAN_RANGE,
    DEFAULT_WEB_PORT,
    DOMAIN,
)


class MikroscanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mikroscan."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._async_validate_input(user_input)
            except MikroscanApiError:
                errors["base"] = "cannot_connect"
            else:
                unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_WEB_PORT]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Mikroscan {unique_id}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_WEB_PORT, default=DEFAULT_WEB_PORT): int,
                    vol.Optional(CONF_SCAN_RANGE, default=DEFAULT_SCAN_RANGE): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await self._async_validate_input(user_input)
            except MikroscanApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, DEFAULT_HOST)): str,
                    vol.Required(
                        CONF_WEB_PORT,
                        default=entry.data.get(CONF_WEB_PORT, DEFAULT_WEB_PORT),
                    ): int,
                    vol.Optional(
                        CONF_SCAN_RANGE,
                        default=entry.data.get(CONF_SCAN_RANGE, DEFAULT_SCAN_RANGE),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_validate_input(self, user_input: dict[str, Any]) -> None:
        """Validate connectivity to the local Mikroscan API."""
        session = async_create_clientsession(self.hass)
        client = MikroscanApiClient(
            session=session,
            host=user_input[CONF_HOST],
            port=user_input[CONF_WEB_PORT],
        )
        await client.async_get_status()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return MikroscanOptionsFlow(config_entry)


class MikroscanOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Mikroscan."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_scan_range = self.config_entry.options.get(
            CONF_SCAN_RANGE,
            self.config_entry.data.get(CONF_SCAN_RANGE, DEFAULT_SCAN_RANGE),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_RANGE, default=current_scan_range): str,
                }
            ),
        )
