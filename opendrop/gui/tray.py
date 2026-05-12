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

System tray integration for the OpenDrop GUI.

Provides a system tray icon that can be clicked to show/hide the main window
and a context menu for quick access to OWL controls and settings.
"""

import logging

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtCore import QTimer
from pathlib import Path

from opendrop.gui.window import MainWindow

logger = logging.getLogger(__name__)


def _get_icon(active: bool = False) -> QIcon:
    """
    Get the system tray icon.

    Creates a simple colored circle icon (green for active, gray for inactive).
    If icon files are available in the resources directory, uses those instead.

    Args:
        active: If True, return active (green) icon, else inactive (gray)

    Returns:
        QIcon instance
    """
    try:
        # Try to load from resources first
        resources_dir = Path(__file__).parent / "resources"
        if active:
            icon_path = resources_dir / "icon_active.png"
        else:
            icon_path = resources_dir / "icon_inactive.png"

        if icon_path.exists():
            return QIcon(str(icon_path))
    except Exception as e:
        logger.debug(f"Could not load icon from resources: {e}")

    # Fallback: create a simple colored circle icon programmatically
    from PyQt6.QtGui import QPixmap, QPainter
    from PyQt6.QtCore import QSize

    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    color = QColor(0, 200, 0) if active else QColor(128, 128, 128)
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()

    return QIcon(pixmap)


class OpenDropTray(QSystemTrayIcon):
    """
    System tray icon for OpenDrop.

    Allows the user to:
    - Click to show/hide the main window
    - Right-click for a context menu with OWL control and settings
    - See at a glance whether OWL is running (green/gray icon)

    The tray icon automatically updates its appearance based on OWL status.
    """

    def __init__(self, app: QApplication, parent=None):
        """
        Initialize the system tray icon.

        Args:
            app: QApplication instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self.app = app
        self._window = MainWindow()
        self._status_timer: QTimer = None
        self._owl_running = False

        # Set initial icon
        self.setIcon(_get_icon(active=False))

        # Build context menu
        self._build_menu()

        # Connect signals
        self.activated.connect(self._on_activated)

        # Wire main window OWL status to tray icon updates
        self._window.owl_manager.owl_started.connect(self._on_owl_status_changed)
        self._window.owl_manager.owl_stopped.connect(self._on_owl_status_changed)

        # Start periodic status check
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_icon)
        self._status_timer.start(2000)  # Update every 2 seconds

        logger.info("System tray icon initialized")

    def _build_menu(self) -> None:
        """Build the context menu."""
        menu = QMenu()

        show_action = menu.addAction("Show OpenDrop")
        show_action.triggered.connect(self._show_window)

        menu.addSeparator()

        self.start_owl_action = menu.addAction("Start OWL")
        self.start_owl_action.triggered.connect(self._on_start_owl)

        self.stop_owl_action = menu.addAction("Stop OWL")
        self.stop_owl_action.triggered.connect(self._on_stop_owl)
        self.stop_owl_action.setEnabled(False)

        menu.addSeparator()

        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self._on_settings)

        menu.addSeparator()

        quit_action = menu.addAction("Quit OpenDrop")
        quit_action.triggered.connect(self.app.quit)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """
        Handle tray icon activation (click).

        Left-click toggles window visibility.

        Args:
            reason: Activation reason (click, double-click, etc.)
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left click: toggle window
            if self._window.isVisible():
                self._window.hide()
            else:
                self._window.show()
                self._window.raise_()
                self._window.activateWindow()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            # Middle click: toggle OWL
            if self._owl_running:
                self._on_stop_owl()
            else:
                self._on_start_owl()

    def _show_window(self) -> None:
        """Show and raise the main window."""
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _on_start_owl(self) -> None:
        """Start OWL via the main window."""
        self._show_window()
        self._window._on_start_owl_clicked()

    def _on_stop_owl(self) -> None:
        """Stop OWL via the main window."""
        self._window._on_stop_owl_clicked()

    def _on_settings(self) -> None:
        """Show settings dialog."""
        self._show_window()
        self._window._on_settings()

    def _on_owl_status_changed(self) -> None:
        """OWL status has changed; update menu and icon."""
        self._update_menu()
        self._update_icon()

    def _update_menu(self) -> None:
        """Update menu items based on OWL status."""
        self._owl_running = self._window.owl_manager.is_running()

        self.start_owl_action.setEnabled(not self._owl_running)
        self.stop_owl_action.setEnabled(self._owl_running)

    def _update_icon(self) -> None:
        """Update the tray icon based on OWL status."""
        is_running = self._window.owl_manager.is_running()

        if is_running != self._owl_running:
            self._owl_running = is_running
            self._update_menu()

        # Update icon appearance
        icon = _get_icon(active=self._owl_running)
        self.setIcon(icon)

        # Update tooltip
        if self._owl_running:
            self.setToolTip("OpenDrop — AWDL Active")
        else:
            self.setToolTip("OpenDrop — OWL Stopped")
