"""
OpenDrop: an open source AirDrop implementation
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
"""

import io
import json
import logging
import os
import platform
import plistlib
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

import libarchive
import libarchive.extract
import libarchive.read
from zeroconf import IPVersion, ServiceInfo, Zeroconf

from .util import AirDropUtil

logger = logging.getLogger(__name__)

# Serializes concurrent uploads so they don't fight over process-wide cwd.
# Uploads are expected to be infrequent, so serialization is acceptable.
_UPLOAD_LOCK = threading.Lock()


@contextmanager
def _chdir(path: str):
    """Temporarily chdir into `path`; restore cwd on exit."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        try:
            os.chdir(prev)
        except OSError:
            # If the previous cwd was removed (rare), fall back to home
            os.chdir(os.path.expanduser("~"))


class AirDropServer:
    """
    Announces an HTTPS AirDrop server in the local network via mDNS.
    """

    def __init__(self, config):
        self.config = config

        # Track our own bound port locally rather than mutating config.port —
        # other components hold a reference to the same AirDropConfig.
        self.port = self.config.port

        # Use IPv6
        self.serveraddress = ("::", self.port)
        self.ServerClass = HTTPServerV6
        self.ServerClass.allow_reuse_address = False

        self.ip_addr = AirDropUtil.get_ip_for_interface(
            self.config.interface, ipv6=True
        )
        if self.ip_addr is None:
            if self.config.interface == "awdl0":
                raise RuntimeError(
                    f"Interface {self.config.interface} does not have an IPv6 address. Make sure that `owl` is running."
                )
            else:
                raise RuntimeError(
                    f"Interface {self.config.interface} does not have an IPv6 address"
                )

        self.Handler = AirDropServerHandler
        self.Handler.config = self.config

        # Try dual-stack (IPv4+IPv6) for better compatibility
        ip_version = IPVersion.All
        ipv4_addr = AirDropUtil.get_ip_for_interface(self.config.interface, ipv6=False)
        if ipv4_addr is None:
            # Fall back to IPv6-only if no IPv4 available
            ip_version = IPVersion.V6Only
            logger.debug(f"No IPv4 found on {self.config.interface}, using IPv6-only")
        else:
            logger.debug(
                f"Server using dual-stack: IPv4={ipv4_addr}, IPv6={self.ip_addr}"
            )

        # Zeroconf expects IP address strings for interfaces, not interface
        # names. For link-local IPv6, the address carries a "%iface" zone id.
        self.zeroconf = Zeroconf(
            interfaces=[str(self.ip_addr)],
            ip_version=ip_version,
            apple_p2p=platform.system() == "Darwin",
        )

        self.http_server = self._init_server()
        self.service_info = self._init_service()

    def _init_service(self):
        properties = self.get_properties()
        server = self.config.host_name + ".local."
        # AirDrop uses the service_id (random hex) as the mDNS service name,
        # with the friendly computer name carried in the TXT properties.
        service_name = self.config.service_id + "._airdrop._tcp.local."
        info = ServiceInfo(
            "_airdrop._tcp.local.",
            service_name,
            port=self.port,
            properties=properties,
            server=server,
            addresses=[self.ip_addr.packed],
        )
        return info

    def start_service(self):
        logger.info(
            f"Announcing service: host {self.config.host_name}, "
            f"address {self.ip_addr}, port {self.port}"
        )
        self.zeroconf.register_service(self.service_info)

    def _init_server(self):
        # Try ports in a range starting at the configured port. Don't mutate
        # config.port — store the bound port on self instead.
        max_attempts = 10
        last_error = None
        for attempt in range(max_attempts):
            try:
                httpd = self.ServerClass(self.serveraddress, self.Handler)
                break
            except OSError as e:
                last_error = e
                self.port += 1
                self.serveraddress = (self.serveraddress[0], self.port)
        else:
            raise RuntimeError(
                f"Could not bind any port in range "
                f"{self.config.port}-{self.config.port + max_attempts}: {last_error}"
            )

        # Adapt socket for awdl0
        if self.config.interface == "awdl0" and platform.system() == "Darwin":
            httpd.socket.setsockopt(socket.SOL_SOCKET, 0x1104, 1)

        httpd.socket = self.config.get_ssl_context().wrap_socket(
            sock=httpd.socket, server_side=True
        )

        return httpd

    def start_server(self):
        logger.info("Starting HTTPS server")
        self.http_server.serve_forever()

    def stop(self):
        self.zeroconf.unregister_all_services()
        self.http_server.shutdown()

    def get_properties(self):
        properties = {b"flags": str(self.config.flags).encode("utf-8")}
        return properties


class HTTPServerV6(HTTPServer):
    address_family = socket.AF_INET6


class AirDropServerHandler(BaseHTTPRequestHandler):
    """
    Server which responds to AirDrop HTTP POST requests.

    Class attributes (set by AirDropServer before the server starts):
        config: AirDropConfig instance with cert/identity info.
        receive_dir: Absolute path where uploaded files should land. If None,
                     falls back to the process cwd at request time (legacy).
    """

    protocol_version = "HTTP/1.1"
    config = None
    receive_dir = None

    def _set_response(self, content_length):
        """
        Setting the default values for a successful response
        """
        self.send_response(200)
        self.send_header("Content-Length", content_length)
        self.end_headers()

    def do_HEAD(self):
        """
        Answer head requests
        """
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        """
        Answer get requests
        """
        logger.debug(f"GET request at {self.path}")
        body = "\n".encode("utf-8")
        self._set_response(len(body))
        self.wfile.write(body)

    def handle_discover(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)

        AirDropUtil.write_debug(
            self.config, post_data, "receive_discover_request.plist"
        )

        # sample media capabilities as recorded from macOS 10.13.3
        media_capabilities = {
            "Version": 1,
            # don't advertise any codec/container support so we receive legacy file formats (JPEG instead of HEIF, etc.)
            # 'Codecs': {
            #     'hvc1': {
            #         'Profiles': {
            #             'VTPerProfileSupport': {
            #                 '1': {'VTMaxPlaybackLevel': 120},
            #                 '2': {'VTMaxPlaybackLevel': 120},
            #                 '3': {}
            #             },
            #             'VTSupportedProfiles': [1, 2, 3]
            #         }
            #     }
            # },
            # 'ContainerFormats': {
            #     'public.heif-standard': {
            #         'HeifSubtypes': ['public.avci', 'public.heic', 'public.heif']
            #     }
            # },
            # 'Vendor': {
            #     'com.apple': {
            #         'OSVersion': [10, 13, 3],
            #         'OSBuildVersion': '17D102',
            #         'LivePhotoFormatVersion': '1'
            #     }
            # }
        }
        media_capabilities_json = json.JSONEncoder().encode(media_capabilities)
        media_capabilities_binary = media_capabilities_json.encode("utf-8")
        discover_answer = {
            "ReceiverMediaCapabilities": media_capabilities_binary,
            "ReceiverComputerName": self.config.computer_name,
            "ReceiverModelName": self.config.computer_model,
        }
        if self.config.record_data:
            discover_answer["ReceiverRecordData"] = self.config.record_data

        discover_answer_binary = plistlib.dumps(
            discover_answer, fmt=plistlib.FMT_BINARY  # pylint: disable=no-member
        )

        AirDropUtil.write_debug(
            self.config, discover_answer_binary, "receive_discover_response.plist"
        )

        # Change to actual length
        self._set_response(len(discover_answer_binary))
        self.wfile.write(discover_answer_binary)

    def handle_ask(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)

        AirDropUtil.write_debug(self.config, post_data, "receive_ask_request.plist")

        ask_response = {
            "ReceiverModelName": self.config.computer_model,
            "ReceiverComputerName": self.config.computer_name,
        }
        ask_resp_binary = plistlib.dumps(
            ask_response, fmt=plistlib.FMT_BINARY  # pylint: disable=no-member
        )

        AirDropUtil.write_debug(
            self.config, ask_resp_binary, "receive_ask_response.plist"
        )

        self._set_response(len(ask_resp_binary))
        self.wfile.write(ask_resp_binary)

    def handle_upload(self):
        if self.headers.get("content-type", "").lower() != "application/x-cpio":
            logger.warning(
                f"Unsupported content-type: {self.headers.get('content-type')}"
            )
            self.send_response(406)  # Unprocessable Entity
            self.send_header("Content-Type", "application/x-cpio")
            self.send_header("Content-Length", 0)
            self.send_header("Connection", "close")
            self.end_headers()
            return

        # If pipelining is not support, 'Expect: 100-continue' is sent to which we need to respond
        if self.headers.get("expect", "").lower() == "100-continue":
            self.send_response(100)
            self.send_header("Content-Length", 0)
            self.end_headers()

        if self.headers.get("transfer-encoding", "").lower() != "chunked":
            logger.warning("Expect chunked transfer encoding")
            self.send_response(400)  # Bad Request
            self.send_header("Transfer-Encoding", "Chunked")
            self.send_header("Content-Length", 0)
            self.send_header("Connection", "close")
            self.end_headers()
            return

        class HTTPChunkedReader(io.RawIOBase):
            def __init__(self, rfile, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.rfile = rfile
                self.chunk = None
                self.total = 0

            def _next_chunk(self):
                if self.chunk is None or len(self.chunk) == 0:
                    length = int(self.rfile.readline().rstrip(), 16)
                    self.chunk = self.rfile.read(length)
                    self.rfile.readline()  # strip trailing \n\r

            def readinto(self, buf):
                self._next_chunk()
                length = min(len(self.chunk), len(buf))
                buf[:length] = self.chunk[:length]
                self.chunk = self.chunk[length:]
                self.total += length
                return length

        def extract_stream(stream, flags=0):
            """
            Extracts an archive from memory into the current directory.

            libarchive's extract_entries always writes to cwd, so the caller
            is responsible for chdir-ing first (under the upload lock).
            """

            with libarchive.read.stream_reader(stream) as archive:
                libarchive.extract.extract_entries(archive, flags)

        logger.info("Receiving file(s) ...")
        start = time.time()
        reader = HTTPChunkedReader(self.rfile)

        # libarchive extracts to cwd; serialize uploads and chdir into the
        # configured receive directory rather than mutating cwd globally.
        target_dir = self.receive_dir or os.getcwd()
        os.makedirs(target_dir, exist_ok=True)
        with _UPLOAD_LOCK:
            with _chdir(target_dir):
                extract_stream(reader)

        transferred = reader.total / 1024.0 / 1024.0
        elapsed = max(time.time() - start, 1e-6)
        speed = transferred / elapsed
        logger.info(
            f"File(s) received into {target_dir} "
            f"(size {transferred:.02f} MB, speed {speed:.02f} MB/s)"
        )

        self.send_response(200)
        self.send_header("Content-Length", 0)
        self.send_header("Connection", "close")
        self.end_headers()

    def do_POST(self):
        """
        Handle post requests
        """

        logger.debug(f"POST request at {self.path}")
        logger.debug(f"Headers\n{self.headers}")

        if self.path == "/Discover":
            self.handle_discover()
        elif self.path == "/Ask":
            self.handle_ask()
        elif self.path == "/Upload":
            self.handle_upload()
        else:
            logger.debug(f"POST request at {self.path}")
            self.send_response(400)
            self.send_header("Content-Length", 0)
            self.end_headers()

    def log_message(self, format, *args):
        # pylint: disable=redefined-builtin
        logger.debug(
            f"{self.client_address[0]} - - [{self.log_date_time_string()}] {format % args}"
        )
