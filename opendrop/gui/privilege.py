"""
Privilege escalation helper for OpenDrop GUI.

Provides secure password prompts for operations requiring root access,
without relying on pre-configured sudoers entries.
"""

import subprocess
import logging
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class PasswordDialog(QDialog):
    """
    Secure password input dialog for privilege escalation.

    Prompts user for their password to execute commands with sudo.
    Uses PyQt6 for GUI integration instead of terminal-based askpass.
    """

    def __init__(self, parent=None, command_description=""):
        """
        Initialize password dialog.

        Args:
            parent: Parent widget
            command_description: Description of what requires password
                Example: "Start OWL AWDL service"
        """
        super().__init__(parent)
        self.password = None
        self.command_description = command_description
        self.setup_ui()

    def setup_ui(self):
        """Create password input UI."""
        self.setWindowTitle("Authentication Required")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Description
        if self.command_description:
            desc_label = QLabel(f"Action: {self.command_description}")
            layout.addWidget(desc_label)

        # Password prompt
        prompt_label = QLabel("Enter your password:")
        layout.addWidget(prompt_label)

        # Password field
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.accept)
        layout.addWidget(self.password_input)

        # Buttons
        button_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Authenticate")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def get_password(self):
        """Return the entered password."""
        return self.password_input.text()


class SudoExecutor:
    """
    Execute commands with sudo, prompting for password via GUI.

    Handles privilege escalation securely without requiring pre-configured
    passwordless sudoers entries.
    """

    def __init__(self, parent=None):
        """
        Initialize executor.

        Args:
            parent: Parent widget for password dialogs
        """
        self.parent = parent

    def execute(self, command, description=""):
        """
        Execute a command with sudo, prompting for password if needed.

        Args:
            command: Command to execute (str or list)
            description: Human-readable description of the action

        Returns:
            tuple: (success: bool, output: str, error: str)

        Example:
            success, output, error = executor.execute(
                ["systemctl", "start", "owl-awdl.service"],
                description="Start OWL AWDL service"
            )
        """
        if isinstance(command, str):
            command = command.split()

        try:
            # Try without password first (in case sudoers is already configured)
            logger.info(f"Attempting to execute: {' '.join(command)}")
            result = subprocess.run(
                ["sudo"] + command,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Command succeeded: {' '.join(command)}")
                return True, result.stdout, ""

            # If it failed due to password, prompt user
            if "password is required" in result.stderr.lower():
                return self._execute_with_password(command, description)
            else:
                logger.error(f"Command failed: {result.stderr}")
                return False, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            error = f"Command timeout (30s): {' '.join(command)}"
            logger.error(error)
            return False, "", error
        except Exception as e:
            error = f"Failed to execute command: {str(e)}"
            logger.error(error)
            return False, "", error

    def _execute_with_password(self, command, description):
        """
        Execute command by prompting user for password.

        Args:
            command: List of command parts
            description: Human-readable description

        Returns:
            tuple: (success: bool, output: str, error: str)
        """
        # Create password dialog
        dialog = PasswordDialog(self.parent, description)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False, "", "Cancelled by user"

        password = dialog.get_password()
        if not password:
            return False, "", "No password provided"

        try:
            # Use echo to pipe password to sudo
            # This is more secure than command-line argument
            process = subprocess.Popen(
                ["sudo", "-S"] + command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(
                input=password + "\n",
                timeout=30
            )

            # Clear password from memory
            del password

            if process.returncode == 0:
                logger.info(f"Command succeeded with authentication: {' '.join(command)}")
                return True, stdout, ""
            else:
                logger.error(f"Command failed: {stderr}")
                return False, stdout, stderr

        except subprocess.TimeoutExpired:
            process.kill()
            error = f"Command timeout (30s): {' '.join(command)}"
            logger.error(error)
            return False, "", error
        except Exception as e:
            error = f"Failed to execute command with password: {str(e)}"
            logger.error(error)
            return False, "", error

    def execute_and_show_dialog(self, command, description="", show_output=True):
        """
        Execute command and show result in dialog.

        Args:
            command: Command to execute
            description: Human-readable description
            show_output: Whether to show command output/errors in dialog

        Returns:
            bool: Success status
        """
        success, output, error = self.execute(command, description)

        if show_output:
            if success:
                QMessageBox.information(
                    self.parent,
                    "Success",
                    f"✓ {description}\n\n{output if output else 'Command completed.'}"
                )
            else:
                QMessageBox.critical(
                    self.parent,
                    "Error",
                    f"✗ {description} failed\n\n{error if error else 'Unknown error'}"
                )

        return success
