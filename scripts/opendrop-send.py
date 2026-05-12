#!/usr/bin/env python3

"""
OpenDrop Context Menu Send Helper

Integrates OpenDrop into file manager context menus.
Used by Nautilus (GNOME), Dolphin (KDE), and other file managers.

Usage:
    opendrop-send file1.txt file2.pdf ...

This script:
1. Takes files as arguments
2. Launches a device selection dialog
3. Sends the file(s) to the selected device
4. Shows progress and completion status
"""

import sys
import os
import logging
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QMessageBox,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from opendrop.config import AirDropConfig
from opendrop.client import AirDropBrowser
from opendrop.gui.worker import SendWorker
from opendrop.gui.settings import OpenDropSettings

logger = logging.getLogger(__name__)


class DeviceSelectionDialog(QDialog):
    """
    Dialog to select a device from discovered AirDrop devices.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Device - OpenDrop")
        self.setGeometry(200, 200, 500, 400)
        self.selected_device = None
        self.devices = {}
        self._build_ui()
        self._discover_devices()

    def _build_ui(self) -> None:
        """Build the device selection UI."""
        layout = QVBoxLayout()

        # Instruction
        layout.addWidget(QLabel("Select a device to send files to:"))

        # Device list
        self.device_list = QListWidget()
        self.device_list.itemClicked.connect(self._on_device_selected)
        layout.addWidget(self.device_list)

        # Status
        self.status_label = QLabel("Discovering devices...")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.send_btn = QPushButton("Send")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.send_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _discover_devices(self) -> None:
        """Discover nearby AirDrop devices."""
        try:
            settings = OpenDropSettings.load()
            config = AirDropConfig(
                computer_name=settings.computer_name,
                interface=settings.interface,
            )

            self.browser = AirDropBrowser(config)
            self.browser.start(
                callback_add=self._on_device_found,
                callback_remove=self._on_device_removed,
            )

            # Auto-stop after 10 seconds
            QThread.msleep(10000)
            self.browser.stop()

        except Exception as e:
            logger.error(f"Device discovery failed: {e}")
            self.status_label.setText(f"Error: {e}")

    def _on_device_found(self, device_info) -> None:
        """Add discovered device to list."""
        name = device_info.name
        device_id = device_info.name

        if device_id not in self.devices:
            self.devices[device_id] = device_info
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, device_id)
            self.device_list.addItem(item)

        if self.device_list.count() > 0:
            self.status_label.setText(f"Found {self.device_list.count()} device(s)")

    def _on_device_removed(self, device_id: str) -> None:
        """Remove device from list."""
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == device_id:
                self.device_list.takeItem(i)
                if device_id in self.devices:
                    del self.devices[device_id]
                break

    def _on_device_selected(self) -> None:
        """Enable send button when device is selected."""
        if self.device_list.currentItem():
            self.send_btn.setEnabled(True)

    def get_selected_device(self):
        """Return the selected device info."""
        if self.device_list.currentItem():
            device_id = self.device_list.currentItem().data(Qt.ItemDataRole.UserRole)
            return self.devices.get(device_id)
        return None


class SendProgressDialog(QDialog):
    """Show progress while sending files."""

    def __init__(self, files: List[str], device_info, parent=None):
        super().__init__(parent)
        self.files = files
        self.device_info = device_info
        self.setWindowTitle("Sending Files - OpenDrop")
        self.setGeometry(200, 200, 500, 150)
        self._build_ui()
        self._send_files()

    def _build_ui(self) -> None:
        """Build the progress UI."""
        layout = QVBoxLayout()

        self.status_label = QLabel(f"Sending {len(self.files)} file(s)...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def _send_files(self) -> None:
        """Send files to the selected device."""
        try:
            settings = OpenDropSettings.load()
            config = AirDropConfig(
                computer_name=settings.computer_name,
                interface=settings.interface,
            )

            total_files = len(self.files)
            for idx, file_path in enumerate(self.files):
                # Update progress
                progress = int((idx / total_files) * 100)
                self.progress_bar.setValue(progress)
                self.status_label.setText(f"Sending {Path(file_path).name}...")

                # Create and run send worker
                worker = SendWorker(config, file_path, self.device_info)
                worker.finished.connect(lambda: self._on_send_complete())
                worker.start()
                worker.wait()  # Wait for completion

            # All done
            self.progress_bar.setValue(100)
            self.status_label.setText(f"✓ Sent {total_files} file(s) successfully!")
            QMessageBox.information(self, "Success", f"Sent {total_files} file(s) successfully!")
            self.accept()

        except Exception as e:
            logger.error(f"Send failed: {e}")
            QMessageBox.critical(self, "Error", f"Send failed: {e}")
            self.reject()

    def _on_send_complete(self) -> None:
        """Handle send completion."""
        pass


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: opendrop-send file1 [file2 ...]")
        sys.exit(1)

    files = sys.argv[1:]

    # Verify files exist
    for file_path in files:
        if not Path(file_path).exists():
            print(f"Error: File not found: {file_path}")
            sys.exit(1)

    # Create Qt application
    app = QApplication(sys.argv)

    # Select device
    device_dialog = DeviceSelectionDialog()
    if device_dialog.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    selected_device = device_dialog.get_selected_device()
    if not selected_device:
        QMessageBox.warning(None, "Error", "No device selected")
        sys.exit(1)

    # Send files
    send_dialog = SendProgressDialog(files, selected_device)
    send_dialog.exec()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
