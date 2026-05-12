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

Settings dialog for the OpenDrop GUI.

Allows users to configure interface names, computer name, receive directory,
and other preferences through a user-friendly dialog.
"""

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from opendrop.gui.settings import OpenDropSettings

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Settings configuration dialog for OpenDrop.

    Provides editable fields for:
    - Computer name (displayed in AirDrop)
    - Receive directory (where files are saved)
    - AWDL interface name
    - WiFi interface name
    - Auto-start OWL toggle
    - WiFi disruption warning toggle

    On OK, validates settings and saves to ~/.config/opendrop/settings.json.
    """

    def __init__(self, settings: OpenDropSettings, parent=None):
        """
        Initialize the settings dialog.

        Args:
            settings: Current OpenDropSettings instance
            parent: Parent QWidget
        """
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("OpenDrop Settings")
        self.setGeometry(100, 100, 500, 400)
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        """Build the dialog UI with input fields and buttons."""
        layout = QVBoxLayout()

        # Computer Name
        layout.addWidget(QLabel("Computer Name:"))
        self.computer_name_input = QLineEdit()
        self.computer_name_input.setPlaceholderText("Name shown in AirDrop")
        layout.addWidget(self.computer_name_input)

        # Receive Directory
        layout.addWidget(QLabel("Receive Directory:"))
        recv_layout = QHBoxLayout()
        self.receive_dir_input = QLineEdit()
        self.receive_dir_input.setPlaceholderText("Directory for received files")
        recv_layout.addWidget(self.receive_dir_input)
        recv_browse_btn = QPushButton("Browse...")
        recv_browse_btn.clicked.connect(self._on_browse_receive_dir)
        recv_layout.addWidget(recv_browse_btn)
        layout.addLayout(recv_layout)

        # AWDL Interface
        layout.addWidget(QLabel("AWDL Interface:"))
        self.interface_input = QLineEdit()
        self.interface_input.setPlaceholderText("e.g., awdl0")
        layout.addWidget(self.interface_input)

        # WiFi Interface
        layout.addWidget(QLabel("WiFi Interface:"))
        self.wifi_interface_input = QLineEdit()
        self.wifi_interface_input.setPlaceholderText("e.g., wlo1")
        layout.addWidget(self.wifi_interface_input)

        # Checkboxes
        self.auto_start_owl_checkbox = QCheckBox("Start OWL automatically on launch")
        layout.addWidget(self.auto_start_owl_checkbox)

        self.warn_wifi_disruption_checkbox = QCheckBox(
            "Warn about WiFi interruption before starting OWL"
        )
        layout.addWidget(self.warn_wifi_disruption_checkbox)

        # Spacer
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _load_settings(self) -> None:
        """Load current settings into the input fields."""
        self.computer_name_input.setText(self.settings.computer_name)
        self.receive_dir_input.setText(self.settings.receive_directory)
        self.interface_input.setText(self.settings.interface)
        self.wifi_interface_input.setText(self.settings.wifi_interface)
        self.auto_start_owl_checkbox.setChecked(self.settings.auto_start_owl)
        self.warn_wifi_disruption_checkbox.setChecked(
            self.settings.warn_wifi_disruption
        )

    def _on_browse_receive_dir(self) -> None:
        """Open file browser to select receive directory."""
        current_path = Path(self.receive_dir_input.text()).expanduser()
        if not current_path.exists():
            current_path = Path.home() / "Downloads"

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Receive Directory",
            str(current_path),
        )

        if directory:
            self.receive_dir_input.setText(directory)

    def accept(self) -> None:
        """Validate and save settings, then close the dialog."""
        try:
            # Update settings object from dialog fields
            self.settings.computer_name = self.computer_name_input.text().strip()
            recv_dir = self.receive_dir_input.text().strip()

            if not recv_dir:
                QMessageBox.warning(self, "Validation Error", "Receive directory cannot be empty")
                return

            recv_path = Path(recv_dir).expanduser()
            if not recv_path.exists():
                result = QMessageBox.question(
                    self,
                    "Directory Does Not Exist",
                    f"Create directory?\n{recv_dir}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if result == QMessageBox.StandardButton.Yes:
                    try:
                        recv_path.mkdir(parents=True, exist_ok=True)
                    except OSError as e:
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"Failed to create directory: {e}",
                        )
                        return
                else:
                    return

            self.settings.receive_directory = recv_dir
            self.settings.interface = self.interface_input.text().strip() or "awdl0"
            self.settings.wifi_interface = (
                self.wifi_interface_input.text().strip() or "wlo1"
            )
            self.settings.auto_start_owl = self.auto_start_owl_checkbox.isChecked()
            self.settings.warn_wifi_disruption = (
                self.warn_wifi_disruption_checkbox.isChecked()
            )

            # Save to disk
            self.settings.save()
            logger.info("Settings saved successfully")
            super().accept()

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {e}",
            )
