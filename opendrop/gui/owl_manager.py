"""
OpenDrop: an open source AirDrop implementation
Copyright (C) 2024  Ravindra K. (GUI extension)
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

OWL AWDL daemon lifecycle management for the GUI.

Manages starting/stopping the OWL systemd service, monitoring awdl0 interface
status, and emitting signals for GUI state updates. Uses subprocess to call
systemctl (which is authorized via sudoers for no-password operation).
"""

import logging
import subprocess
import threading
from typing import Optional

try:
    from PyQt6.QtCore import QObject, QTimer, pyqtSignal
except ImportError:
    # Fallback for environments without PyQt6
    QObject = object
    pyqtSignal = lambda *args, **kwargs: None
    QTimer = None

from opendrop.util import AirDropUtil

logger = logging.getLogger(__name__)


class OWLManager(QObject):
    """
    Manages the OWL AWDL daemon lifecycle via systemd service.

    Provides signals for GUI updates on OWL status changes. Uses systemctl
    commands (via sudoers) to start/stop the owl-awdl.service. Monitors
    awdl0 interface for IPv6 address availability.

    Signals:
        owl_started: Emitted when awdl0 is up with IPv6 address
        owl_stopped: Emitted when awdl0 becomes unavailable
        owl_error: Emitted with error message on subprocess failure
        wifi_disruption_warning: Emitted if WiFi will be interrupted
    """

    owl_started = pyqtSignal()
    owl_stopped = pyqtSignal()
    owl_error = pyqtSignal(str)
    wifi_disruption_warning = pyqtSignal()

    def __init__(self, parent=None):
        """
        Initialize the OWL manager.

        Args:
            parent: Parent QObject for signal/slot hierarchy
        """
        super().__init__(parent)
        self._poll_timer: Optional[QTimer] = None
        self._awdl0_present = False
        self._wifi_disruption_checked = False
        self._supports_concurrent_mode = False

    def check_hardware_capability(self) -> bool:
        """
        Check if the WiFi hardware supports concurrent monitor+managed mode.

        This prevents WiFi disruption when OWL starts. If the hardware doesn't
        support concurrent mode, WiFi will be briefly interrupted.

        Returns:
            True if concurrent mode is supported (no WiFi disruption),
            False if WiFi will be interrupted during OWL operation
        """
        try:
            # Parse iw phy output to check for simultaneous mode capability
            result = subprocess.run(
                ["iw", "phy", "phy0", "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                output = result.stdout
                # Check if "managed" and "monitor" appear in the same
                # valid interface combinations section
                if "managed" in output and "monitor" in output:
                    # Simple heuristic: if both are mentioned, might support it
                    # A proper check would parse the interface combinations more carefully
                    logger.debug("Hardware may support concurrent monitor+managed mode")
                    self._supports_concurrent_mode = True
                    return True
            else:
                logger.warning(f"iw phy command failed: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Could not check hardware capability: {e}")

        logger.warning("Hardware does not support concurrent monitor+managed mode")
        logger.warning("WiFi will be interrupted when OWL starts")
        self._supports_concurrent_mode = False
        return False

    def _systemctl_call(self, command: str) -> bool:
        """
        Execute a systemctl command for the owl-awdl service.

        Uses sudo (authorized via /etc/sudoers.d/opendrop for no password).

        Args:
            command: One of "start", "stop", or "status"

        Returns:
            True if command succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["sudo", "systemctl", command, "owl-awdl.service"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                logger.info(f"systemctl {command} succeeded")
                return True
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"systemctl {command} failed: {error_msg}")
                self.owl_error.emit(f"Failed to {command} OWL: {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            msg = f"systemctl {command} timed out"
            logger.error(msg)
            self.owl_error.emit(msg)
            return False
        except FileNotFoundError:
            msg = "sudo or systemctl not found"
            logger.error(msg)
            self.owl_error.emit(msg)
            return False

    def _poll_for_awdl0(self) -> None:
        """
        Poll for awdl0 interface presence and status.

        Called by a QTimer while OWL is starting/stopping. Checks if awdl0
        has an IPv6 address (indicates OWL is ready) and emits appropriate
        signals.
        """
        if not QTimer:
            logger.warning("QTimer not available, skipping polling")
            return

        awdl0_ip = AirDropUtil.get_ip_for_interface("awdl0", ipv6=True)

        if awdl0_ip is not None and not self._awdl0_present:
            logger.info(f"awdl0 is up with IPv6: {awdl0_ip}")
            self._awdl0_present = True
            self.owl_started.emit()
            if self._poll_timer:
                self._poll_timer.stop()

        elif awdl0_ip is None and self._awdl0_present:
            logger.info("awdl0 is no longer available")
            self._awdl0_present = False
            self.owl_stopped.emit()
            if self._poll_timer:
                self._poll_timer.stop()

    def start(self, warn_on_disruption: bool = True) -> None:
        """
        Start the OWL AWDL daemon via systemd.

        If hardware does not support concurrent monitor+managed mode and
        warn_on_disruption is True, emits wifi_disruption_warning signal.
        The caller should handle this and confirm before proceeding.

        Starts a polling timer to detect when awdl0 is ready.

        Args:
            warn_on_disruption: If True, emit warning signal on WiFi disruption risk
        """
        if not self._wifi_disruption_checked:
            capability = self.check_hardware_capability()
            self._wifi_disruption_checked = True

            if not capability and warn_on_disruption:
                logger.warning("Emitting WiFi disruption warning")
                self.wifi_disruption_warning.emit()
                return

        logger.info("Starting OWL AWDL daemon...")
        if not self._systemctl_call("start"):
            return

        # Start polling for awdl0 to appear
        if QTimer:
            self._poll_timer = QTimer()
            self._poll_timer.timeout.connect(self._poll_for_awdl0)
            self._poll_timer.start(500)  # Poll every 500ms
            logger.debug("Started polling for awdl0 interface")
        else:
            # Fallback: do a single check if no Qt available
            self._poll_for_awdl0()

    def stop(self) -> None:
        """
        Stop the OWL AWDL daemon via systemd.

        Stops the polling timer and calls systemctl stop.
        The systemd service will clean up mon0 and restore WiFi.
        """
        logger.info("Stopping OWL AWDL daemon...")

        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None

        if not self._systemctl_call("stop"):
            return

        # Start polling for awdl0 to disappear
        if QTimer:
            self._poll_timer = QTimer()
            self._poll_timer.timeout.connect(self._poll_for_awdl0)
            self._poll_timer.start(500)
            logger.debug("Started polling for awdl0 removal")
        else:
            self._poll_for_awdl0()

    def is_running(self) -> bool:
        """
        Check if OWL AWDL is currently running (awdl0 has IPv6).

        Returns:
            True if awdl0 interface exists with IPv6 address
        """
        awdl0_ip = AirDropUtil.get_ip_for_interface("awdl0", ipv6=True)
        return awdl0_ip is not None
