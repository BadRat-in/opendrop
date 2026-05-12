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

Main window for the OpenDrop GUI application.

Displays OWL/AWDL status, nearby devices, send/receive controls, and settings.
Coordinates between OWL manager, worker threads, and user interactions.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QMessageBox,
    QFileDialog,
    QDialog,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from opendrop.config import AirDropConfig
from opendrop.gui.owl_manager import OWLManager
from opendrop.gui.settings import OpenDropSettings
from opendrop.gui.settings_dialog import SettingsDialog
from opendrop.gui.worker import BrowseWorker, SendWorker, ReceiveWorker
from opendrop.util import AirDropUtil

logger = logging.getLogger(__name__)


class MainWindow(QWidget):
    """
    Main application window for OpenDrop.

    Manages the interface between the user and OpenDrop/OWL:
    - Shows OWL/AWDL status with indicator light
    - Lists nearby AirDrop devices (from BrowseWorker)
    - Allows sending files (SendWorker) and receiving (ReceiveWorker)
    - Provides settings dialog
    - Manages OWL lifecycle via OWLManager

    This window is shown/hidden from the system tray by the parent application.
    """

    def __init__(self, parent=None):
        """
        Initialize the main window.

        Args:
            parent: Parent QWidget
        """
        super().__init__(parent)
        self.setWindowTitle("OpenDrop — AirDrop for Linux")
        self.setGeometry(100, 100, 600, 600)

        # Load settings
        self.settings = OpenDropSettings.load()

        # Create OWL manager for systemd integration
        self.owl_manager = OWLManager()
        self.owl_manager.owl_started.connect(self._on_owl_started)
        self.owl_manager.owl_stopped.connect(self._on_owl_stopped)
        self.owl_manager.owl_error.connect(self._on_owl_error)
        self.owl_manager.wifi_disruption_warning.connect(
            self._on_wifi_disruption_warning
        )

        # Worker threads
        self.browse_worker: Optional[BrowseWorker] = None
        self.send_worker: Optional[SendWorker] = None
        self.receive_worker: Optional[ReceiveWorker] = None

        # Build UI
        self._build_ui()

        # Auto-start OWL if configured
        if self.settings.auto_start_owl:
            QTimer.singleShot(500, self._on_start_owl_clicked)

    def _build_ui(self) -> None:
        """Build the main window UI layout."""
        layout = QVBoxLayout()

        # ===== Status Panel =====
        status_label = QLabel("AWDL Status:")
        layout.addWidget(status_label)

        status_layout = QHBoxLayout()
        self.status_indicator = QLabel("⚫")
        self.status_indicator.setStyleSheet("color: gray; font-size: 16px;")
        status_layout.addWidget(self.status_indicator)

        self.status_text = QLabel("OWL not running")
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()

        layout.addLayout(status_layout)

        # ===== OWL Control Buttons =====
        owl_button_layout = QHBoxLayout()
        self.start_owl_btn = QPushButton("Start OWL")
        self.start_owl_btn.clicked.connect(self._on_start_owl_clicked)
        owl_button_layout.addWidget(self.start_owl_btn)

        self.stop_owl_btn = QPushButton("Stop OWL")
        self.stop_owl_btn.clicked.connect(self._on_stop_owl_clicked)
        self.stop_owl_btn.setEnabled(False)
        owl_button_layout.addWidget(self.stop_owl_btn)

        owl_button_layout.addStretch()
        layout.addLayout(owl_button_layout)

        layout.addWidget(QLabel(""))  # Spacer

        # ===== Devices Panel =====
        layout.addWidget(QLabel("Nearby Devices:"))

        self.device_list = QListWidget()
        self.device_list.itemClicked.connect(self._on_device_selected)
        layout.addWidget(self.device_list)

        # Device control buttons
        device_btn_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh Devices")
        self.refresh_btn.clicked.connect(self._on_refresh_devices)
        device_btn_layout.addWidget(self.refresh_btn)

        self.send_btn = QPushButton("Send File to Device")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_send_file)
        device_btn_layout.addWidget(self.send_btn)

        layout.addLayout(device_btn_layout)

        layout.addWidget(QLabel(""))  # Spacer

        # ===== Receive Panel =====
        recv_layout = QHBoxLayout()
        self.receive_checkbox = QCheckBox("Accept incoming files")
        self.receive_checkbox.stateChanged.connect(self._on_receive_toggled)
        recv_layout.addWidget(self.receive_checkbox)
        recv_layout.addStretch()

        layout.addLayout(recv_layout)

        layout.addWidget(QLabel(""))  # Spacer

        # ===== Info & Settings =====
        info_layout = QHBoxLayout()

        interface_text = (
            f"Interface: {self.settings.interface} | "
            f"WiFi: {self.settings.wifi_interface}"
        )
        self.info_label = QLabel(interface_text)
        info_layout.addWidget(self.info_label)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._on_settings)
        info_layout.addWidget(settings_btn)

        layout.addLayout(info_layout)

        self.setLayout(layout)

    def _update_status_indicator(self) -> None:
        """Update the AWDL status indicator based on awdl0 presence."""
        if self.owl_manager.is_running():
            self.status_indicator.setText("🟢")
            self.status_indicator.setStyleSheet("color: green; font-size: 16px;")
            awdl0_ip = AirDropUtil.get_ip_for_interface("awdl0", ipv6=True)
            self.status_text.setText(f"AWDL Active: {awdl0_ip}")
            self.start_owl_btn.setEnabled(False)
            self.stop_owl_btn.setEnabled(True)
            self.refresh_btn.setEnabled(True)
        else:
            self.status_indicator.setText("⚫")
            self.status_indicator.setStyleSheet("color: gray; font-size: 16px;")
            self.status_text.setText("OWL not running")
            self.start_owl_btn.setEnabled(True)
            self.stop_owl_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)

    def _on_start_owl_clicked(self) -> None:
        """Handle Start OWL button click."""
        logger.info("User clicked Start OWL")
        self.owl_manager.start(warn_on_disruption=self.settings.warn_wifi_disruption)

    def _on_stop_owl_clicked(self) -> None:
        """Handle Stop OWL button click."""
        logger.info("User clicked Stop OWL")
        if self.receive_worker:
            self.receive_worker.stop()
            self.receive_worker = None
        if self.browse_worker:
            self.browse_worker.stop()
            self.browse_worker = None
        self.owl_manager.stop()

    def _on_owl_started(self) -> None:
        """OWL has started successfully."""
        logger.info("OWL started successfully")
        self._update_status_indicator()
        QMessageBox.information(self, "OWL Started", "AWDL interface is up!")

    def _on_owl_stopped(self) -> None:
        """OWL has stopped."""
        logger.info("OWL stopped")
        self._update_status_indicator()

    def _on_owl_error(self, error: str) -> None:
        """OWL encountered an error."""
        logger.error(f"OWL error: {error}")
        QMessageBox.critical(self, "OWL Error", error)
        self._update_status_indicator()

    def _on_wifi_disruption_warning(self) -> None:
        """WiFi disruption warning emitted; ask user for confirmation."""
        result = QMessageBox.warning(
            self,
            "WiFi Interruption Warning",
            "Starting OWL will briefly interrupt your WiFi connection.\n\n"
            "Your WiFi will be automatically restored when OWL stops.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            # User confirmed; start OWL without warning
            self.owl_manager.start(warn_on_disruption=False)

    def _on_refresh_devices(self) -> None:
        """Refresh the device list.

        Works with or without OWL:
        - With OWL (AWDL): Uses awdl0 interface for AWDL discovery
        - Without OWL (Option A): Uses WiFi interface for Bonjour/mDNS discovery
        """
        logger.info("User clicked Refresh Devices")

        # Verify we have a valid interface with IPv6
        interface = self.settings.interface
        ip_addr = AirDropUtil.get_ip_for_interface(interface, ipv6=True)

        if ip_addr is None:
            QMessageBox.warning(
                self,
                "No IPv6 Address",
                f"Interface {interface!r} does not have an IPv6 address.\n\n"
                "Make sure:\n"
                "1. WiFi is connected\n"
                "2. IPv6 is enabled\n"
                "3. Interface name is correct in Settings",
            )
            return

        self.device_list.clear()
        if self.browse_worker:
            self.browse_worker.stop()

        # Create new AirDropConfig
        try:
            config = AirDropConfig(
                computer_name=self.settings.computer_name,
                interface=self.settings.interface,
            )

            self.browse_worker = BrowseWorker(config)
            self.browse_worker.device_found.connect(self._on_device_found)
            self.browse_worker.device_removed.connect(self._on_device_removed)
            self.browse_worker.error.connect(self._on_browse_error)
            self.browse_worker.start()

            logger.info(f"Device browsing started on interface {interface}")
        except Exception as e:
            logger.error(f"Failed to start device browsing: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start browsing: {e}")

    def _on_device_found(self, device_info: Dict) -> None:
        """Add or update a discovered device in the list.

        If the device already exists, update its info instead of creating a duplicate.
        """
        device_id = device_info.get("id")
        name = device_info.get("name", "Unknown")

        # Check if device already exists
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            existing_info = item.data(Qt.ItemDataRole.UserRole)
            if existing_info.get("id") == device_id:
                # Update existing device info
                item.setData(Qt.ItemDataRole.UserRole, device_info)
                logger.debug(f"Device info updated: {name}")
                return

        # Device not found, add new entry
        item_text = f"{name}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, device_info)
        self.device_list.addItem(item)
        logger.debug(f"Device added to list: {name}")

    def _on_device_removed(self, device_id: str) -> None:
        """Remove a device from the list."""
        if not device_id:
            logger.debug("Device removal called with empty device_id")
            return

        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_data and item_data.get("id") == device_id:
                self.device_list.takeItem(i)
                logger.debug(f"Device removed from list: {device_id}")
                break

    def _on_browse_error(self, error: str) -> None:
        """Handle browsing error."""
        logger.error(f"Browse error: {error}")
        QMessageBox.warning(self, "Discovery Error", error)

    def _on_device_selected(self) -> None:
        """Enable send button when device is selected."""
        if self.device_list.currentItem():
            self.send_btn.setEnabled(True)
        else:
            self.send_btn.setEnabled(False)

    def _on_send_file(self) -> None:
        """Handle send file button click."""
        current_item = self.device_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Device Selected", "Select a device first")
            return

        device_info = current_item.data(Qt.ItemDataRole.UserRole)

        # Open file picker
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Send",
            str(Path.home()),
        )

        if not file_path:
            return

        logger.info(f"Sending {file_path} to {device_info.get('name')}")

        try:
            config = AirDropConfig(
                computer_name=self.settings.computer_name,
                interface=self.settings.interface,
            )

            self.send_worker = SendWorker(config, file_path, device_info)
            self.send_worker.progress.connect(self._on_send_progress)
            self.send_worker.finished.connect(self._on_send_finished)
            self.send_worker.error.connect(self._on_send_error)
            self.send_worker.start()

            self.send_btn.setEnabled(False)

        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            QMessageBox.critical(self, "Send Failed", str(e))

    def _on_send_progress(self, percent: int) -> None:
        """Update progress during file send."""
        self.send_btn.setText(f"Sending... {percent}%")

    def _on_send_finished(self, success: bool) -> None:
        """File send completed."""
        if success:
            QMessageBox.information(self, "Success", "File sent successfully!")
        self.send_btn.setText("Send File to Device")
        self.send_btn.setEnabled(True)

    def _on_send_error(self, error: str) -> None:
        """Send error occurred."""
        logger.error(f"Send error: {error}")
        QMessageBox.critical(self, "Send Error", error)
        self.send_btn.setText("Send File to Device")
        self.send_btn.setEnabled(True)

    def _on_receive_toggled(self, state: int) -> None:
        """Handle receive checkbox state change."""
        if state == Qt.CheckState.Checked.value:
            logger.info("User enabled receiving")

            # Verify interface has IPv6 for Bonjour/mDNS discovery
            interface = self.settings.interface
            ip_addr = AirDropUtil.get_ip_for_interface(interface, ipv6=True)

            if ip_addr is None:
                QMessageBox.warning(
                    self,
                    "No IPv6 Address",
                    f"Interface {interface!r} does not have an IPv6 address.\n\n"
                    "Make sure:\n"
                    "1. WiFi is connected\n"
                    "2. IPv6 is enabled\n"
                    "3. Interface name is correct in Settings",
                )
                self.receive_checkbox.setChecked(False)
                return

            try:
                config = AirDropConfig(
                    computer_name=self.settings.computer_name,
                    interface=self.settings.interface,
                )

                self.receive_worker = ReceiveWorker(config)
                self.receive_worker.file_request.connect(self._on_file_request)
                self.receive_worker.file_received.connect(self._on_file_received)
                self.receive_worker.error.connect(self._on_receive_error)
                self.receive_worker.start()

                self.settings.receiving_enabled = True
                self.settings.save()

            except Exception as e:
                logger.error(f"Failed to start receiver: {e}")
                QMessageBox.critical(self, "Error", f"Failed to start receiver: {e}")
                self.receive_checkbox.setChecked(False)
        else:
            logger.info("User disabled receiving")
            if self.receive_worker:
                self.receive_worker.stop()
                self.receive_worker = None
            self.settings.receiving_enabled = False
            self.settings.save()

    def _on_file_request(self, request_info: Dict) -> None:
        """Handle incoming AirDrop file request."""
        sender = request_info.get("sender", "Unknown Device")
        files = request_info.get("files", [])
        file_count = request_info.get("file_count", 0)

        # Create a readable file list
        if len(files) == 1:
            file_text = files[0]
        elif len(files) <= 3:
            file_text = ", ".join(files)
        else:
            file_text = ", ".join(files[:3]) + f"... (+{len(files) - 3} more)"

        # Show confirmation dialog
        result = QMessageBox.question(
            self,
            "Incoming AirDrop",
            f"Accept {file_count} file(s) from {sender}?\n\n{file_text}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        approved = result == QMessageBox.StandardButton.Yes
        logger.info(f"File request {'approved' if approved else 'rejected'}: {sender}")

        if self.receive_worker:
            self.receive_worker.approve_file_request(approved)

    def _on_file_received(self, file_path: str) -> None:
        """File has been received."""
        logger.info(f"File received: {file_path}")
        QMessageBox.information(
            self,
            "File Received",
            f"File received and saved to:\n{file_path}",
        )

    def _on_receive_error(self, error: str) -> None:
        """Receive error occurred."""
        logger.error(f"Receive error: {error}")
        QMessageBox.critical(self, "Receive Error", error)
        self.receive_checkbox.setChecked(False)

    def _on_settings(self) -> None:
        """Open settings dialog."""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("Settings updated")
            # Reload settings for display
            interface_text = (
                f"Interface: {self.settings.interface} | "
                f"WiFi: {self.settings.wifi_interface}"
            )
            self.info_label.setText(interface_text)

    def closeEvent(self, event) -> None:
        """Clean up worker threads on window close."""
        if self.browse_worker:
            self.browse_worker.stop()
        if self.receive_worker:
            self.receive_worker.stop()
        super().closeEvent(event)
