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

QThread workers for AirDrop operations.

Provides non-blocking Qt threads that wrap the existing AirDropBrowser,
AirDropClient, and AirDropServer for use in the GUI. All network operations
run in background threads to keep the UI responsive.
"""

import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from opendrop.client import AirDropBrowser, AirDropClient
from opendrop.config import AirDropConfig
from opendrop.server import AirDropServer

logger = logging.getLogger(__name__)


class BrowseWorker(QThread):
    """
    Background thread for discovering nearby AirDrop devices.

    Uses mDNS (via AirDropBrowser) to discover _airdrop._tcp.local. services
    and emits signals when devices are found or removed.

    Signals:
        device_found: Emitted with device info dict when a device is discovered
        device_removed: Emitted with device ID when a device goes offline
        error: Emitted with error message if discovery fails
    """

    device_found = pyqtSignal(dict)
    device_removed = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, config: AirDropConfig, parent=None):
        """
        Initialize the browse worker.

        Args:
            config: AirDropConfig instance with interface settings
            parent: Parent QObject
        """
        super().__init__(parent)
        self.config = config
        self.browser: Optional[AirDropBrowser] = None
        self._stop_event = threading.Event()

    def run(self) -> None:
        """
        Background thread main loop: discover and monitor AirDrop devices.

        Creates an AirDropBrowser and runs it until stop() is called.
        Emits device_found and device_removed signals as devices appear/disappear.
        """
        try:
            logger.info(
                f"Starting device discovery on interface {self.config.interface}"
            )
            self.browser = AirDropBrowser(self.config)

            def on_device_found(info):
                try:
                    device_data = self._parse_device_info(info)
                    logger.debug(f"Device found: {device_data.get('name')}")
                    self.device_found.emit(device_data)
                except Exception as e:
                    logger.warning(f"Error parsing device info: {e}")

            def on_device_removed(info):
                try:
                    if info is None:
                        logger.debug("Device removal called with None info")
                        return
                    name = info.name.split(".")[0]
                    logger.debug(f"Device removed: {name}")
                    self.device_removed.emit(name)
                except Exception as e:
                    logger.warning(f"Error processing device removal: {e}")

            self.browser.start(
                callback_add=on_device_found, callback_remove=on_device_removed
            )

            # Keep the thread alive until stop() is called
            while not self._stop_event.is_set():
                self._stop_event.wait(0.1)

            logger.info("Device discovery stopped")

        except Exception as e:
            error_msg = f"Discovery error: {e}"
            logger.error(error_msg)
            self.error.emit(error_msg)

        finally:
            if self.browser:
                try:
                    self.browser.stop()
                except Exception as e:
                    logger.error(f"Error stopping browser: {e}")

    def _parse_device_info(self, info) -> Dict:
        """
        Parse zeroconf ServiceInfo into a device dictionary.

        Args:
            info: zeroconf.ServiceInfo object

        Returns:
            Dict with keys: name, address, port, id, flags, model, flags
        """
        identifier = info.name.split(".")[0]
        try:
            address = info.parsed_addresses()[0]
        except (IndexError, AttributeError):
            address = "unknown"

        port = int(info.port) if info.port else 8771

        return {
            "name": info.server.rstrip(".") if info.server else identifier,
            "address": str(address),
            "port": port,
            "id": identifier,
            "properties": dict(info.properties) if info.properties else {},
        }

    def stop(self) -> None:
        """Stop the discovery thread gracefully."""
        logger.debug("Stopping BrowseWorker")
        self._stop_event.set()
        self.quit()
        self.wait()


class SendWorker(QThread):
    """
    Background thread for sending a file to a receiver device.

    Signals:
        progress: Emitted with percentage (0-100) during upload
        finished: Emitted with success bool when transfer completes
        error: Emitted with error message on failure
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(
        self,
        config: AirDropConfig,
        file_path: str,
        receiver_info: Dict,
        parent=None,
    ):
        """
        Initialize the send worker.

        Args:
            config: AirDropConfig instance
            file_path: Path to file to send (or URL if is_url=True)
            receiver_info: Dict with keys 'address', 'port', 'name'
            parent: Parent QObject
        """
        super().__init__(parent)
        self.config = config
        self.file_path = file_path
        self.receiver_info = receiver_info

    def run(self) -> None:
        """
        Background thread main loop: send file to receiver.

        Attempts to send file, emitting progress and finished signals.
        """
        try:
            file_path = Path(self.file_path).expanduser()

            if not file_path.exists() and not self.file_path.startswith("http"):
                raise FileNotFoundError(f"File not found: {self.file_path}")

            logger.info(f"Starting file send to {self.receiver_info.get('name')}")

            # Create client and connect to receiver
            receiver_addr = (
                self.receiver_info["address"],
                self.receiver_info["port"],
            )
            client = AirDropClient(self.config, receiver_addr)

            # Send /Discover request
            logger.debug("Sending /Discover request")
            self.progress.emit(10)
            if not client.send_discover():
                raise RuntimeError("Receiver rejected /Discover")

            # Send /Ask request
            logger.debug("Sending /Ask request")
            self.progress.emit(30)
            if not client.send_ask(self.file_path):
                raise RuntimeError("Receiver rejected file")

            # Send /Upload request
            logger.debug("Sending /Upload request")
            self.progress.emit(50)
            if not client.send_upload(self.file_path):
                raise RuntimeError("Upload failed")

            logger.info("File sent successfully")
            self.progress.emit(100)
            self.finished.emit(True)

        except Exception as e:
            error_msg = f"Send failed: {e}"
            logger.error(error_msg)
            self.error.emit(error_msg)
            self.finished.emit(False)

    def stop(self) -> None:
        """Stop the send operation."""
        logger.debug("Stopping SendWorker")
        self.quit()
        self.wait()


class ReceiveWorker(QThread):
    """
    Background thread for receiving files from AirDrop senders.

    Registers an mDNS service and accepts incoming file transfers with user confirmation.

    Signals:
        file_request: Emitted with file details dict when an /Ask request arrives
        file_received: Emitted with file path when a file is received
        error: Emitted with error message on failure
    """

    file_request = pyqtSignal(dict)
    file_received = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, config: AirDropConfig, parent=None):
        """
        Initialize the receive worker.

        Args:
            config: AirDropConfig instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self.config = config
        self.server: Optional[AirDropServer] = None
        self._stop_event = threading.Event()
        self._pending_request = None
        self._request_approved = threading.Event()
        self._request_lock = threading.Lock()

    def run(self) -> None:
        """
        Background thread main loop: listen for and accept file transfers.

        Creates an AirDropServer and runs serve_forever() until stop() is called.
        """
        try:
            logger.info(
                f"Starting AirDrop receiver on interface {self.config.interface}"
            )

            recv_dir = Path(self.config.airdrop_dir) / "incoming"
            recv_dir.mkdir(parents=True, exist_ok=True)

            self.server = AirDropServer(self.config)
            # Tell the request handler where to deposit uploaded files.
            # The handler uses a process-wide lock to serialize chdir-based
            # extraction, so this stays thread-safe.
            self.server.Handler.receive_dir = str(recv_dir)

            # Monkey-patch to handle /Ask requests with user confirmation
            original_handle_ask = self.server.Handler.handle_ask

            def handle_ask_wrapper(handler_self):
                try:
                    import plistlib

                    content_length = int(handler_self.headers["Content-Length"])
                    post_data = handler_self.rfile.read(content_length)

                    # Parse the request to get file information
                    try:
                        ask_request = plistlib.loads(post_data)
                    except Exception:
                        ask_request = {}

                    # Extract file details from the request
                    files = ask_request.get("Files", [])
                    sender_name = ask_request.get("SenderComputerName", "Unknown")
                    file_names = [f.get("FileName", "Unknown") for f in files]

                    # Create request info to send to GUI
                    request_info = {
                        "sender": sender_name,
                        "files": file_names,
                        "file_count": len(files),
                    }

                    # Emit signal and wait for user response
                    with self._request_lock:
                        self._pending_request = request_info
                        self._request_approved.clear()

                    logger.info(
                        f"File request from {sender_name}: {', '.join(file_names)}"
                    )
                    self.file_request.emit(request_info)

                    # Wait for user response (with timeout)
                    approved = self._request_approved.wait(
                        timeout=60
                    )  # 60 second timeout
                    if not approved:
                        logger.warning("File request timed out")
                        approved = False

                    with self._request_lock:
                        if self._pending_request:
                            approved = self._pending_request.get("approved", False)
                        self._pending_request = None

                    # Send response to sender
                    ask_response = {
                        "ReceiverModelName": handler_self.config.computer_model,
                        "ReceiverComputerName": handler_self.config.computer_name,
                    }

                    if not approved:
                        # Send rejection response
                        logger.info(f"File request rejected: {sender_name}")
                        handler_self.send_response(400)
                        handler_self.send_header("Content-Length", 0)
                        handler_self.end_headers()
                        return

                    # Send approval response
                    ask_resp_binary = plistlib.dumps(
                        ask_response, fmt=plistlib.FMT_BINARY
                    )
                    handler_self.send_response(200)
                    handler_self.send_header("Content-Length", len(ask_resp_binary))
                    handler_self.end_headers()
                    handler_self.wfile.write(ask_resp_binary)
                    logger.info(f"File request approved: {sender_name}")

                except Exception as e:
                    logger.error(f"Ask handler error: {e}")
                    try:
                        handler_self.send_response(500)
                        handler_self.send_header("Content-Length", 0)
                        handler_self.end_headers()
                    except Exception:
                        pass

            # Monkey-patch the server to emit signals on file receive
            original_handle_upload = self.server.Handler.handle_upload

            def handle_upload_wrapper(handler_self):
                try:
                    result = original_handle_upload(handler_self)
                    # Extract the filename from the request if possible
                    if hasattr(handler_self, "file_path"):
                        self.file_received.emit(str(handler_self.file_path))
                    logger.info("File received successfully")
                    return result
                except Exception as e:
                    logger.error(f"Upload handler error: {e}")
                    raise

            self.server.Handler.handle_ask = handle_ask_wrapper
            self.server.Handler.handle_upload = handle_upload_wrapper

            # Register mDNS service and start server
            self.server.start_service()
            logger.info("Starting server, waiting for incoming files...")
            self.server.start_server()

        except Exception as e:
            error_msg = f"Receive error: {e}"
            logger.error(error_msg)
            self.error.emit(error_msg)

        finally:
            if self.server:
                try:
                    self.server.stop()
                except Exception as e:
                    logger.error(f"Error stopping server: {e}")

    def approve_file_request(self, approved: bool) -> None:
        """
        Called by GUI to approve or reject a file request.

        Args:
            approved: True to accept, False to reject
        """
        with self._request_lock:
            if self._pending_request:
                self._pending_request["approved"] = approved
                self._request_approved.set()

    def stop(self) -> None:
        """Stop receiving and shut down the server."""
        logger.debug("Stopping ReceiveWorker")
        if self.server:
            try:
                self.server.stop()
            except Exception:
                pass
        self._stop_event.set()
        self.quit()
        self.wait()
