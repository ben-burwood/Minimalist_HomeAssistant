"""Custom Integration to setup Minimalist UI"""
from __future__ import annotations

import logging
from typing import Any

#from aiogithubapi import AIOGitHubAPIException, GitHubAPI
from homeassistant.components import frontend
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .base import MuiBase
from .const import DOMAIN, NAME
from .enums import ConfigurationType, muiDisabledReason

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_initialize_integration(hass: HomeAssistant, *, 
    config_entry: ConfigEntry | None = None, 
    config: dict[str, Any] | None = None
) -> bool:
    """Initialize the integration."""
    hass.data[DOMAIN] = mui = MuiBase()
    mui.enable_mui()

    if config is not None:
        if DOMAIN not in config:
            return True
        if mui.configuration.config_type == ConfigurationType.CONFIG_ENTRY:
            return True
        mui.configuration.update_from_dict(
            {
                "config_type": ConfigurationType.YAML,
                **config[DOMAIN],
                "config": config[DOMAIN],
            }
        )

    if config_entry is not None:
        if config_entry.source == SOURCE_IMPORT:
            # not sure about this one
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id)
            )
            return False

        mui.configuration.update_from_dict(
            {
                "config_entry": config_entry,
                "config_type": ConfigurationType.CONFIG_ENTRY,
                **config_entry.data,
                **config_entry.options,
            }
        )

    integration = await async_get_integration(hass, DOMAIN)

    clientsession = async_get_clientsession(hass)

    mui.integration = integration
    mui.version = integration.version
    mui.session = clientsession
    mui.hass = hass
    mui.system.running = True

    async def async_startup():
        """MUI Startup tasks."""

        if (
            not await mui.configure_mui()
            or not await mui.configure_plugins()
            or not await mui.configure_dashboard()
        ):
            return False

        mui.enable_mui()

        return not mui.system.disabled

    startup_result = await async_startup()
    if not startup_result:
        return False

    mui.enable_mui()

    return True


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using UI."""
    return await async_initialize_integration(hass=hass, config=config)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""

    config_entry.add_update_listener(async_reload_entry)
    return await async_initialize_integration(hass=hass, config_entry=config_entry)


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Remove Integration."""
    _LOGGER.debug(f"{NAME} is now uninstalled")

    # TODO cleanup:
    #  - themes
    #  - blueprints
    frontend.async_remove_panel(hass, "minimalist-ui")


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload Integration."""
    _LOGGER.debug("Reload the config entry")

    await async_setup_entry(hass, config_entry)
