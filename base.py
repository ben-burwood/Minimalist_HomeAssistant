"""Base Minimalist UI class."""
from __future__ import annotations

import logging
import os
import pathlib
import shutil
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable

from homeassistant.components.frontend import add_extra_js_url, async_remove_panel
from homeassistant.components.lovelace import _register_panel
from homeassistant.components.lovelace.dashboard import LovelaceYAML
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration

from .const import (
    DEFAULT_INCLUDE_OTHER_CARDS,
    DEFAULT_LANGUAGE,
    DEFAULT_SIDEPANEL_ENABLED,
    DEFAULT_SIDEPANEL_ICON,
    DEFAULT_SIDEPANEL_TITLE,
    DEFAULT_THEME,
    DEFAULT_THEME_PATH,
    DOMAIN,
    GITHUB_REPO,
    LANGUAGES,
    TV,
)
from .enums import ConfigurationType, muiDisabledReason
from .utils.decode import decode_content

_LOGGER: logging.Logger = logging.getLogger(__name__)


@dataclass
class MuiSystem:
    """MUI System info."""

    disabled_reason: muiDisabledReason | None = None
    running: bool = False

    @property
    def disabled(self) -> bool:
        """Return if MUI is disabled."""
        return self.disabled_reason is not None


@dataclass
class MuiConfiguration:
    """MuiConfiguration class."""

    config: dict[str, Any] = field(default_factory=dict)
    config_entry: ConfigEntry | None = None
    config_type: ConfigurationType | None = None
    sidepanel_enabled: bool = DEFAULT_SIDEPANEL_ENABLED
    sidepanel_icon: str = DEFAULT_SIDEPANEL_ICON
    sidepanel_title: str = DEFAULT_SIDEPANEL_TITLE
    adaptive_ui_enabled: bool = DEFAULT_SIDEPANEL_ENABLED
    adaptive_ui_icon: str = DEFAULT_SIDEPANEL_ICON
    adaptive_ui_title: str = DEFAULT_SIDEPANEL_TITLE
    theme_path: str = DEFAULT_THEME_PATH
    theme: str = DEFAULT_THEME
    plugin_path: str = "www/community/"
    include_other_cards: bool = DEFAULT_INCLUDE_OTHER_CARDS
    language: str = DEFAULT_LANGUAGE
    token: str = None

    def to_dict(self) -> dict:
        """Return Dict."""
        return self.__dict__

    def to_json(self) -> str:
        """Return a json string."""
        return asdict(self)

    def update_from_dict(self, data: dict) -> None:
        """Set attributes from dicts."""
        if not isinstance(data, dict):
            raise Exception("Configuration is not valid.")

        for key in data:
            self.__setattr__(key, data[key])


class MuiBase:
    """Base Minimalist UI"""

    integration: Integration | None = None
    configuration = MuiConfiguration()
    hass: HomeAssistant | None = None
    log: logging.Logger = _LOGGER
    githubapi: GitHubAPI | None = None
    system = MuiSystem()
    version: str | None = None

    @property
    def integration_dir(self) -> pathlib.Path:
        """Return the MUI integration dir."""
        return self.integration.file_path

    @property
    def templates_dir(self) -> pathlib.Path:
        """Return the Button Cards Template dir."""
        return pathlib.Path(f"{self.integration_dir}/__ui_minimalist__/mui_templates")

    def disable_mui(self, reason: muiDisabledReason) -> None:
        """Disable Mui."""

        if self.system.disabled_reason == reason:
            return

        self.system.disabled_reason = reason
        if reason == muiDisabledReason.INVALID_TOKEN:
            self.configuration.config_entry.state = ConfigEntryState.SETUP_ERROR
            self.configuration.config_entry.reason = "Authentiation Failed"
            self.hass.add_job(
                self.configuration.config_entry.async_start_reauth, self.hass
            )

    def enable_mui(self) -> None:
        """Enable Mui"""
        if self.system.disabled_reason is not None:
            self.system.disabled_reason = None
            self.log.info("MUI is enabled")

    async def async_save_file(self, file_path: str, content: Any) -> bool:
        """Save a file"""

        self.log.debug("Saving file: %s" % file_path)

        def _write_file():
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(
                file_path,
                mode="w" if isinstance(content, str) else "wb",
                encoding="utf-8" if isinstance(content, str) else None,
                errors="ignore" if isinstance(content, str) else None,
            ) as file_handler:
                file_handler.write(content)

        try:
            await self.hass.async_add_executor_job(_write_file)
        except (
            BaseException
        ) as error:  # lgtm [py/catch-base-exception] pylint: disable=broad-except
            self.log.error(f"Could not write data to {file_path} - {error}")
            return False

        return os.path.exists(file_path)

    async def configure_plugins(self) -> bool:
        """Configure the Plugins MUI depends on."""
        self.log.debug("Checking Dependencies.")

        try:
            if not os.path.exists(
                self.hass.config.path("custom_components/browser_mod")
            ):
                self.log.error('HACS Integration repo "browser mod" is not installed!')

            dependency_resource_paths = [
                "button-card",
                "light-entity-card",
                "lovelace-card-mod",
                "lovelace-auto-entities",
                "mini-graph-card",
                "mini-media-player",
                "my-cards",
                "simple-weather-card",
                "lovelace-layout-card",
                "lovelace-state-switch",
                "weather-radar-card",
            ]
            for p in dependency_resource_paths:
                if not self.configuration.include_other_cards:
                    if not os.path.exists(self.hass.config.path(f"www/community/{p}")):
                        self.log.error(
                            f'HACS Frontend repo "{p}" is not installed, See Integration Configuration.'
                        )
                else:
                    if os.path.exists(self.hass.config.path(f"www/community/{p}")):
                        _LOGGER.error(
                            f'HACS Frontend repo "{p}" is already installed, Remove it or disable include custom cards'
                        )

            if self.configuration.include_other_cards:
                for c in dependency_resource_paths:
                    add_extra_js_url(
                        self.hass, f"/minimalist_ui/ext_dependencies/{c}/{c}.js"
                    )

            # Register
            self.hass.http.register_static_path(
                "/minimalist_ui/ext_dependencies",
                self.hass.config.path(f"{self.integration_dir}/ext_dependencies"),
                True,
            )

        except Exception as exception:
            self.log.error(exception)
            self.disable_mui(muiDisabledReason.LOAD_MUI)
            return False

        return True

    async def configure_dashboard(self) -> bool:
        """Configure the MUI Dashboards."""

        dashboard_url = "minimalist-ui"
        dashboard_config = {
            "mode": "yaml",
            "icon": self.configuration.sidepanel_icon,
            "title": self.configuration.sidepanel_title,
            "filename": "minimalist_ui/dashboard/ui.yaml",
            "show_in_sidebar": True,
            "require_admin": False,
        }

        # adv_dashboard_url = "adaptive-dash"
        # adv_dashboard_config = {
        #    "mode": "yaml",
        #    "icon": self.configuration.adaptive_ui_icon,
        #    "title": self.configuration.adaptive_ui_title,
        #    "filename": "minimalist_ui/dashboard/adaptive-dash/adaptive-ui.yaml",
        #    "show_in_sidebar": True,
        #    "require_admin": False,
        # }

        # Optional override can be done with config_flow?
        # if not dashboard_url in hass.data["lovelace"]["dashboards"]:
        try:
            if self.configuration.sidepanel_enabled:
                self.hass.data["lovelace"]["dashboards"][dashboard_url] = LovelaceYAML(
                    self.hass, dashboard_url, dashboard_config
                )

                _register_panel(
                    self.hass, dashboard_url, "yaml", dashboard_config, True
                )
            else:
                if dashboard_url in self.hass.data["lovelace"]["dashboards"]:
                    async_remove_panel(self.hass, "minimalist-ui")

            # if self.configuration.adaptive_ui_enabled:
            #    self.hass.data["lovelace"]["dashboards"][
            #        adv_dashboard_url
            #    ] = LovelaceYAML(self.hass, adv_dashboard_url, adv_dashboard_config)

            #    _register_panel(
            #        self.hass, adv_dashboard_url, "yaml", adv_dashboard_config, True
            #    )
            # else:
            #    if adv_dashboard_url in self.hass.data["lovelace"]["dashboards"]:
            #        async_remove_panel(self.hass, "adaptive-dash")

        except Exception as exception:
            self.log.error(exception)
            self.disable_mui(muiDisabledReason.LOAD_MUI)
            return False

        return True

    async def configure_mui(self) -> bool:
        """Configure initial dashboard & cards directory."""
        self.log.info("Setup MUI Configuration")

        try:
            # Cleanup
            shutil.rmtree(
                self.hass.config.path(f"{DOMAIN}/configs"), ignore_errors=True
            )
            shutil.rmtree(self.hass.config.path(f"{DOMAIN}/addons"), ignore_errors=True)
            # Create config dir
            os.makedirs(self.hass.config.path(f"{DOMAIN}/dashboard"), exist_ok=True)
            os.makedirs(
                self.hass.config.path(f"{DOMAIN}/custom_actions"), exist_ok=True
            )

            if os.path.exists(self.hass.config.path(f"{DOMAIN}/dashboard")):
                os.makedirs(self.templates_dir, exist_ok=True)

                # Translations
                language = LANGUAGES[self.configuration.language]

                # Copy default language file over to config dir
                shutil.copy2(
                    f"{self.integration_dir}/dashboard/translations/default.yaml",
                    f"{self.templates_dir}/default.yaml",
                )
                # Copy example dashboard file over to user config dir if not exists
                if self.configuration.sidepanel_enabled:
                    if not os.path.exists(
                        self.hass.config.path(f"{DOMAIN}/dashboard/ui.yaml")
                    ):
                        shutil.copy2(
                            f"{self.integration_dir}/dashboard/ui.yaml",
                            self.hass.config.path(f"{DOMAIN}/dashboard/ui.yaml"),
                        )
                # Copy adaptive dashboard if not exists and is selected as option
                # if self.configuration.adaptive_ui_enabled:
                #    if not os.path.exists(
                #        self.hass.config.path(f"{DOMAIN}/dashboard/adaptive-dash")
                #    ):
                #        shutil.copytree(
                #            f"{self.integration_dir}/dashboard/adaptive-dash",
                #            self.hass.config.path(f"{DOMAIN}/dashboard/adaptive-dash"),
                #        )
                # Copy example custom actions file over to user config dir if not exists
                if not os.path.exists(
                    self.hass.config.path(
                        f"{DOMAIN}/custom_actions/custom_actions.yaml"
                    )
                ):
                    shutil.copy2(
                        f"{self.integration_dir}/dashboard/custom_actions.yaml",
                        self.hass.config.path(
                            f"{DOMAIN}/custom_actions/custom_actions.yaml"
                        ),
                    )
                # Copy chosen language file over to config dir
                shutil.copy2(
                    f"{self.integration_dir}/dashboard/translations/{language}.yaml",
                    f"{self.templates_dir}/language.yaml",
                )
                # Copy over cards from integration
                shutil.copytree(
                    f"{self.integration_dir}/dashboard/mui_templates",
                    f"{self.templates_dir}",
                    dirs_exist_ok=True,
                )
                # Copy over manually installed custom_actions from user
                shutil.copytree(
                    self.hass.config.path(f"{DOMAIN}/custom_actions"),
                    f"{self.templates_dir}/custom_actions",
                    dirs_exist_ok=True,
                )
                # Copy over themes to defined themes folder
                shutil.copytree(
                    f"{self.integration_dir}/dashboard/themefiles",
                    self.hass.config.path(f"{self.configuration.theme_path}/"),
                    dirs_exist_ok=True,
                )

            self.hass.bus.async_fire("minimalist_ui_reload")

            async def handle_reload(call):
                _LOGGER.debug("Reload Minimalist UI Configuration")

                self.reload_configuration()

            # Register servcie minimalist_ui.reload
            self.hass.services.async_register(DOMAIN, "reload", handle_reload)

        except Exception as exception:
            self.log.error(exception)
            self.disable_mui(muiDisabledReason.LOAD_MUI)
            return False

        return True

    def reload_configuration(self):
        """Reload Configuration."""
        if os.path.exists(self.hass.config.path(f"{DOMAIN}/custom_actions")):
            # Copy over manually installed custom_actions from user
            shutil.copytree(
                self.hass.config.path(f"{DOMAIN}/custom_actions"),
                f"{self.templates_dir}/custom_actions",
                dirs_exist_ok=True,
            )
        self.hass.bus.async_fire("minimalist_ui_reload")
