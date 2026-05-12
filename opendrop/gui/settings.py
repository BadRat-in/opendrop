"""
OpenDrop: an open source AirDrop implementation
Copyright (C) 2024  Ravindra Singh Budgurjar (GUI extension)
Copyright (C) 2018  Milan Stute
Copyright (C) 2018  Alexander Heinrich

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Settings persistence module for the OpenDrop GUI.

Provides a dataclass-based settings system that persists to
~/.config/opendrop/settings.json. Handles default values, validation,
and JSON serialization/deserialization.
"""

import json
import logging
import socket
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OpenDropSettings:
    """
    Configuration for OpenDrop GUI application.

    Attributes:
        interface: AWDL interface name (default: "awdl0")
        computer_name: Computer name displayed in AirDrop (default: hostname)
        receive_directory: Directory to save received files (default: ~/Downloads)
        wifi_interface: WiFi interface that OWL operates on (default: "wlo1")
        auto_start_owl: Start OWL automatically on app launch (default: False)
        receiving_enabled: Accept incoming files by default (default: False)
        warn_wifi_disruption: Show warning about WiFi interruption (default: True)
    """

    interface: str = "awdl0"
    computer_name: str = field(default_factory=socket.gethostname)
    receive_directory: str = field(
        default_factory=lambda: str(Path.home() / "Downloads")
    )
    wifi_interface: str = "wlo1"
    auto_start_owl: bool = False
    receiving_enabled: bool = False
    warn_wifi_disruption: bool = True

    @staticmethod
    def _get_config_file() -> Path:
        """
        Determine the path to the settings JSON file.

        Creates ~/.config/opendrop/ directory if it doesn't exist.

        Returns:
            Path to the settings JSON file
        """
        config_dir = Path.home() / ".config" / "opendrop"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "settings.json"

    @classmethod
    def load(cls) -> "OpenDropSettings":
        """
        Load settings from ~/.config/opendrop/settings.json.

        If the file doesn't exist or is invalid, returns default settings.
        Logs a warning if the file exists but is malformed.

        Returns:
            Loaded settings or defaults if file not found/invalid
        """
        config_file = cls._get_config_file()

        if not config_file.exists():
            logger.debug(f"Settings file not found at {config_file}, using defaults")
            return cls()

        try:
            with open(config_file, "r") as f:
                data = json.load(f)
            logger.debug(f"Loaded settings from {config_file}")
            return cls(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to load settings from {config_file}: {e}")
            logger.warning("Using default settings")
            return cls()

    def save(self) -> None:
        """
        Save settings to ~/.config/opendrop/settings.json.

        Validates that receive_directory exists before saving.
        Raises ValueError if directory validation fails.
        """
        # Validate receive directory exists
        recv_path = Path(self.receive_directory).expanduser()
        if not recv_path.exists():
            logger.warning(
                f"Receive directory does not exist: {self.receive_directory}"
            )
            logger.info(f"Creating receive directory: {self.receive_directory}")
            try:
                recv_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise ValueError(
                    f"Cannot create receive directory {self.receive_directory}: {e}"
                )

        config_file = self._get_config_file()
        try:
            with open(config_file, "w") as f:
                json.dump(asdict(self), f, indent=2)
            logger.debug(f"Saved settings to {config_file}")
        except OSError as e:
            logger.error(f"Failed to save settings to {config_file}: {e}")
            raise
