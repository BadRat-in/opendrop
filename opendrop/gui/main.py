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

OpenDrop GUI application entry point.

This module defines the main() function that starts the Qt application,
creates the system tray icon, and handles application lifecycle.

To run: python -m opendrop.gui.main
Or via console script: opendrop-gui
"""

import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from opendrop.gui.tray import OpenDropTray

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Entry point for the OpenDrop GUI application.

    Creates a QApplication, checks for system tray availability, initializes
    the system tray icon, and starts the Qt event loop.

    Exits with code 1 if system tray is not available.
    """
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    logger.info("=" * 60)
    logger.info("OpenDrop GUI Starting")
    logger.info("=" * 60)

    # Create Qt application
    app = QApplication(sys.argv)

    # Configure application metadata
    app.setApplicationName("OpenDrop")
    app.setApplicationVersion("0.14.0")
    app.setOrganizationName("OpenDrop")

    # Don't quit when last window closes (we have a tray icon)
    app.setQuitOnLastWindowClosed(False)

    # Check for system tray support
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.critical("System tray is not available on this desktop")
        QMessageBox.critical(
            None,
            "OpenDrop",
            "System tray is not available on this desktop.\n"
            "Please use a desktop environment with system tray support.",
        )
        sys.exit(1)

    logger.info("System tray is available")

    # Create and show tray icon
    try:
        tray = OpenDropTray(app)
        tray.show()
        logger.info("Tray icon created and displayed")
    except Exception as e:
        logger.critical(f"Failed to create tray icon: {e}")
        QMessageBox.critical(None, "OpenDrop", f"Failed to start GUI: {e}")
        sys.exit(1)

    # Start Qt event loop
    logger.info("Entering Qt event loop")
    exit_code = app.exec()

    logger.info("=" * 60)
    logger.info(f"OpenDrop GUI Exiting (code: {exit_code})")
    logger.info("=" * 60)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
