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

OWL AWDL daemon lifecycle management for the GUI.

Manages starting/stopping the OWL systemd service, monitoring awdl0 interface
status, and emitting signals for GUI state updates. Handles privilege escalation
via password dialog (GUI) instead of relying on pre-configured sudoers.
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
from opendrop.gui.privilege import SudoExecutor

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
        self._sudo_executor = SudoExecutor(parent=parent)

    def check_hardware_capability(self) -> bool:
        """
        Check if the Wi-Fi hardware supports concurrent monitor+managed mode.

        Delegates to opendrop.hardware which parses iw phy output for every
        Wi-Fi adapter on the system and consults known-bad/good chipset
        tables. Returns True only if the *best* adapter advertises a
        concurrent interface combination — meaning OWL can run without
        kicking the user off Wi-Fi.

        Returns:
            True if concurrent mode is supported (no Wi-Fi disruption),
            False otherwise (OWL may not start or will tear down Wi-Fi).
        """
        from opendrop.hardware import detect

        report = detect()
        best = report.best_adapter
        if best is None:
            logger.warning("No Wi-Fi adapter detected")
            self._supports_concurrent_mode = False
            return False

        if best.supports_concurrent_monitor:
            logger.info(
                f"Adapter {best.interface} ({best.chipset!r}) supports concurrent "
                f"monitor+managed mode — OWL should run without disrupting Wi-Fi"
            )
            self._supports_concurrent_mode = True
            return True

        logger.warning(
            f"Adapter {best.interface} ({best.chipset!r}) does NOT advertise "
            "concurrent monitor+managed interface combinations. "
            "OWL is unlikely to start successfully here. "
            "See `opendrop-doctor` for hardware recommendations."
        )
        self._supports_concurrent_mode = False
        return False

    def _systemctl_call(self, command: str) -> bool:
        """
        Execute a systemctl command for the owl-awdl service.

        Uses SudoExecutor which prompts for password via GUI dialog if needed.
        No pre-configured sudoers required.

        Args:
            command: One of "start", "stop", or "status"

        Returns:
            True if command succeeded, False otherwise
        """
        description = f"{'Start' if command == 'start' else 'Stop' if command == 'stop' else 'Check'} OWL AWDL service"
        success, output, error = self._sudo_executor.execute(
            ["systemctl", command, "owl-awdl.service"], description=description
        )

        if success:
            logger.info(f"systemctl {command} succeeded")
            return True
        else:
            logger.error(f"systemctl {command} failed: {error}")
            self.owl_error.emit(f"Failed to {command} OWL: {error}")
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

        Refuses up-front if the host's Wi-Fi chipset is on the known-bad
        list (Intel CNVi etc.) — otherwise we'd watch the systemd unit
        crash-loop with "Operation not supported" every 5 seconds.

        If the chipset is *unknown* but the driver doesn't advertise
        concurrent monitor+managed and warn_on_disruption is True, emits
        wifi_disruption_warning so the caller can confirm.

        Args:
            warn_on_disruption: If True, emit warning signal on WiFi
                                disruption risk for unknown chipsets.
        """
        # Hard refuse on chipsets we already know fail this kernel API.
        from opendrop.hardware import AWDLCompatibility, detect

        report = detect()
        if report.awdl_compatibility in (
            AWDLCompatibility.UNLIKELY,
            AWDLCompatibility.NOT_SUPPORTED,
        ):
            best = report.best_adapter
            chipset = best.chipset if best else "unknown"
            msg = (
                f"This Wi-Fi adapter ({chipset!r}) cannot run AWDL. "
                "OWL will fail every time on it because the driver does not "
                "support the nl80211 operations OWL needs.\n\n"
                "Run `opendrop-doctor` for hardware recommendations. "
                "A USB Wi-Fi adapter with an Atheros AR9271 or Realtek "
                "RTL8812 chipset is the standard workaround."
            )
            logger.error(msg)
            self.owl_error.emit(msg)
            return

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
