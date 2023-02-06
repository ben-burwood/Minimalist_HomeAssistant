"""Config Flow for Minimalist UI Integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.loader import async_get_integration
import voluptuous as vol

from .base import MuiBase
from .const import (
    CLIENT_ID,
    CONF_INCLUDE_OTHER_CARDS,
    CONF_LANGUAGE,
    CONF_LANGUAGES,
    CONF_SIDEPANEL_ENABLED,
    CONF_SIDEPANEL_ICON,
    CONF_SIDEPANEL_TITLE,
    CONF_SIDEPANEL_ADV_ENABLED,
    CONF_SIDEPANEL_ADV_ICON,
    CONF_SIDEPANEL_ADV_TITLE,
    CONF_THEME,
    CONF_THEME_OPTIONS,
    CONF_THEME_PATH,
    DEFAULT_INCLUDE_OTHER_CARDS,
    DEFAULT_LANGUAGE,
    DEFAULT_SIDEPANEL_ENABLED,
    DEFAULT_SIDEPANEL_ICON,
    DEFAULT_SIDEPANEL_TITLE,
    DEFAULT_SIDEPANEL_ADV_ENABLED,
    DEFAULT_SIDEPANEL_ADV_ICON,
    DEFAULT_SIDEPANEL_ADV_TITLE,
    DEFAULT_THEME,
    DEFAULT_THEME_PATH,
    DOMAIN,
    NAME,
)
from .enums import ConfigurationType

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def mui_config_option_schema(options: dict = {}) -> dict:
    """Return a schema for MUI configuration options."""

    # Also update base.py MuiConfiguration
    return {
        vol.Optional(
            CONF_SIDEPANEL_ENABLED,
            default=options.get(CONF_SIDEPANEL_ENABLED, DEFAULT_SIDEPANEL_ENABLED),
        ): bool,
        vol.Optional(
            CONF_SIDEPANEL_TITLE,
            default=options.get(CONF_SIDEPANEL_TITLE, DEFAULT_SIDEPANEL_TITLE),
        ): str,
        vol.Optional(
            CONF_SIDEPANEL_ICON,
            default=options.get(CONF_SIDEPANEL_ICON, DEFAULT_SIDEPANEL_ICON),
        ): str,
        #vol.Optional(
        #    CONF_SIDEPANEL_ADV_ENABLED,
        #    default=options.get(
        #        CONF_SIDEPANEL_ADV_ENABLED, DEFAULT_SIDEPANEL_ADV_ENABLED
        #    ),
        #): bool,
        #vol.Optional(
        #    CONF_SIDEPANEL_ADV_TITLE,
        #    default=options.get(CONF_SIDEPANEL_ADV_TITLE, DEFAULT_SIDEPANEL_ADV_TITLE),
        #): str,
        #vol.Optional(
        #    CONF_SIDEPANEL_ADV_ICON,
        #    default=options.get(CONF_SIDEPANEL_ADV_ICON, DEFAULT_SIDEPANEL_ADV_ICON),
        #): str,
        vol.Optional(
            CONF_THEME, default=options.get(CONF_THEME, DEFAULT_THEME)
        ): vol.In(CONF_THEME_OPTIONS),
        vol.Optional(
            CONF_THEME_PATH,
            default=options.get(CONF_THEME_PATH, DEFAULT_THEME_PATH),
        ): str,
        #vol.Optional(
        #    CONF_INCLUDE_OTHER_CARDS,
        #    default=options.get(CONF_INCLUDE_OTHER_CARDS, DEFAULT_INCLUDE_OTHER_CARDS),
        #): bool
    }


class MuiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Minimalist UI"""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._errors = {}
        self.device = None
        self.activation = None
        self.log = _LOGGER
        self._progress_task = None
        self._login_device = None
        self._reauth = False

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle a flow initialized by the user."""

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if self.hass.data.get(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)


class MuiOptionFlowHandler(config_entries.OptionsFlow):
    """MUI config flow option handler (Edit Flow)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, _user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initilized by the user."""
        mui: MuiBase = self.hass.data.get(DOMAIN)
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title=NAME, data=user_input)

        if mui is None or mui.configuration is None:
            return self.async_abort(reason="not_setup")

        if mui.configuration.config_type == ConfigurationType.YAML:
            schema = {vol.Optional("not_in_use", default=""): str}
        else:
            schema = await mui_config_option_schema(mui.configuration.to_dict())

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(schema), errors=errors
        )
