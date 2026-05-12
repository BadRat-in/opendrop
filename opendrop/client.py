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
import ipaddress
import logging
import os
import platform
import plistlib
import socket
from http.client import HTTPSConnection

import fleep
import libarchive
from zeroconf import IPVersion, ServiceBrowser, Zeroconf

from .util import AbsArchiveWrite, AirDropUtil

logger = logging.getLogger(__name__)


class AirDropBrowser:
    def __init__(self, config):
        self.config = config
        self.ip_addr = AirDropUtil.get_ip_for_interface(config.interface, ipv6=True)
        if self.ip_addr is None:
            if config.interface == "awdl0":
                raise RuntimeError(
                    f"Interface {config.interface} does not have an IPv6 address. Make sure that `owl` is running."
                )
            else:
                raise RuntimeError(
                    f"Interface {config.interface} does not have an IPv6 address"
                )

        # Try dual-stack (IPv4+IPv6) for better compatibility
        # Some systems need both IPv4 and IPv6 for proper mDNS discovery
        ip_version = IPVersion.All
        ipv4_addr = AirDropUtil.get_ip_for_interface(config.interface, ipv6=False)
        if ipv4_addr is None:
            # Fall back to IPv6-only if no IPv4 available
            ip_version = IPVersion.V6Only
            logger.debug(f"No IPv4 found on {config.interface}, using IPv6-only")
        else:
            logger.debug(f"Using dual-stack: IPv4={ipv4_addr}, IPv6={self.ip_addr}")

        # Zeroconf expects IP address strings for interfaces, not interface
        # names. For link-local IPv6, the address carries a "%iface" zone id.
        self.zeroconf = Zeroconf(
            interfaces=[str(self.ip_addr)],
            ip_version=ip_version,
            apple_p2p=platform.system() == "Darwin",
        )

        self.callback_add = None
        self.callback_remove = None
        self.browser = None

    def start(self, callback_add=None, callback_remove=None):
        """
        Start the AirDropBrowser to discover other AirDrop devices
        """
        if self.browser is not None:
            return  # already started
        self.callback_add = callback_add
        self.callback_remove = callback_remove
        self.browser = ServiceBrowser(self.zeroconf, "_airdrop._tcp.local.", self)

    def stop(self):
        self.browser.cancel()
        self.browser = None
        self.zeroconf.close()

    def add_service(self, zeroconf, service_type, name):
        info = zeroconf.get_service_info(service_type, name)
        if info is None:
            logger.debug(f"Add service {name}: no info available")
            return

        if self._is_self(info):
            logger.debug(f"Add service {name}: skipping self-announcement")
            return

        logger.debug(f"Add service {name}")
        if self.callback_add is not None:
            self.callback_add(info)

    def remove_service(self, zeroconf, service_type, name):
        """
        Handle service removal. The service may already be gone from the registry,
        so info could be None.
        """
        try:
            info = zeroconf.get_service_info(service_type, name)
        except Exception as e:
            logger.debug(f"Error getting service info during removal: {e}")
            info = None

        logger.debug(f"Remove service {name}")
        if self.callback_remove is not None:
            self.callback_remove(info)

    def update_service(self, zeroconf, service_type, name):
        """
        Called when a service updates its TXT record / address.

        We re-emit as `add` so the GUI can refresh its cached device info.
        The GUI is expected to deduplicate by service id.
        """
        try:
            info = zeroconf.get_service_info(service_type, name)
        except Exception as e:
            logger.debug(f"Error updating service {name}: {e}")
            return

        if info is None:
            return

        if self._is_self(info):
            logger.debug(f"Update service {name}: skipping self-announcement")
            return

        logger.debug(f"Update service {name}")
        if self.callback_add is not None:
            self.callback_add(info)

    def _is_self(self, info) -> bool:
        """
        Return True if a discovered service belongs to this host.

        Compares the service's advertised addresses against our local interface
        addresses. Filters out self-announcements that come back through mDNS.
        """
        from .network import is_local_address

        try:
            addresses = info.parsed_addresses() if info else []
        except Exception:
            addresses = []
        for addr in addresses:
            if is_local_address(addr):
                return True
        return False


class AirDropClient:
    def __init__(self, config, receiver):
        self.config = config
        self.receiver_host = receiver[0]
        self.receiver_port = receiver[1]
        self.http_conn = None

    def send_POST(self, url, body, headers=None):
        logger.debug(f"Send {url} request")

        AirDropUtil.write_debug(
            self.config, body, f"send_{url.lower().strip('/')}_request.plist"
        )

        _headers = self._get_headers()
        if headers is not None:
            for key, val in headers.items():
                _headers[key] = val
        if self.http_conn is None:
            # Use single connection
            self.http_conn = HTTPSConnectionAWDL(
                self.receiver_host,
                self.receiver_port,
                interface_name=self.config.interface,
                context=self.config.get_ssl_context(),
            )
        self.http_conn.request("POST", url, body=body, headers=_headers)
        http_resp = self.http_conn.getresponse()

        response_bytes = http_resp.read()
        AirDropUtil.write_debug(
            self.config,
            response_bytes,
            f"send_{url.lower().strip('/')}_response.plist",
        )

        if http_resp.status != 200:
            status = False
            logger.debug(f"{url} request failed: {http_resp.status}")
        else:
            status = True
            logger.debug(f"{url} request successful")
        return status, response_bytes

    def send_discover(self):
        discover_body = {}
        if self.config.record_data:
            discover_body["SenderRecordData"] = self.config.record_data

        discover_plist_binary = plistlib.dumps(
            discover_body, fmt=plistlib.FMT_BINARY  # pylint: disable=no-member
        )
        _, response_bytes = self.send_POST("/Discover", discover_plist_binary)
        response = plistlib.loads(response_bytes)

        # if name is returned, then receiver is discoverable
        return response.get("ReceiverComputerName")

    def send_ask(self, file_path, is_url=False, icon=None):
        ask_body = {
            "SenderComputerName": self.config.computer_name,
            "BundleID": "com.apple.finder",
            "SenderModelName": self.config.computer_model,
            "SenderID": self.config.service_id,
            "ConvertMediaFormats": False,
        }
        if self.config.record_data:
            ask_body["SenderRecordData"] = self.config.record_data

        def file_entries(files):
            for file in files:
                file_name = os.path.basename(file)
                file_entry = {
                    "FileName": file_name,
                    "FileType": AirDropUtil.get_uti_type(flp),
                    "FileBomPath": os.path.join(".", file_name),
                    "FileIsDirectory": os.path.isdir(file_name),
                    "ConvertMediaFormats": 0,
                }
                yield file_entry

        if isinstance(file_path, str):
            file_path = [file_path]
        if is_url:
            ask_body["Items"] = file_path
        else:
            # generate icon for first file
            with open(file_path[0], "rb") as f:
                file_header = f.read(128)
                flp = fleep.get(file_header)
                if not icon and len(flp.mime) > 0 and "image" in flp.mime[0]:
                    icon = AirDropUtil.generate_file_icon(f.name)
            ask_body["Files"] = [e for e in file_entries(file_path)]
        if icon:
            ask_body["FileIcon"] = icon

        ask_binary = plistlib.dumps(
            ask_body, fmt=plistlib.FMT_BINARY  # pylint: disable=no-member
        )
        success, _ = self.send_POST("/Ask", ask_binary)

        return success

    def send_upload(self, file_path, is_url=False):
        """
        Send a file to a receiver.
        """
        # Don't send an upload request if we just sent a link
        if is_url:
            return

        headers = {
            "Content-Type": "application/x-cpio",
        }

        # Create archive in memory ...
        stream = io.BytesIO()
        with libarchive.custom_writer(
            stream.write,
            "cpio",
            filter_name="gzip",
            archive_write_class=AbsArchiveWrite,
        ) as archive:
            for f in [file_path]:
                ff = os.path.basename(f)
                archive.add_abs_file(f, os.path.join(".", ff))
        stream.seek(0)

        # ... then send in chunked mode
        success, _ = self.send_POST("/Upload", stream, headers=headers)

        # TODO better: write archive chunk whenever send_POST does a read to avoid having the whole archive in memory

        return success

    def _get_headers(self):
        """
        Get the headers for requests sent
        """
        headers = {
            "Content-Type": "application/octet-stream",
            "Connection": "keep-alive",
            "Accept": "*/*",
            "User-Agent": "AirDrop/1.0",
            "Accept-Language": "en-us",
            "Accept-Encoding": "br, gzip, deflate",
        }
        return headers


_DEFAULT_TIMEOUT = object()  # Sentinel for "use socket default at call time"


class HTTPSConnectionAWDL(HTTPSConnection):
    """
    Binds HTTPSConnection to a specific network interface for IPv6 with zone IDs.

    Modern Python compatible: configures TLS via context object, not deprecated
    key_file/cert_file keyword args.
    """

    def __init__(
        self,
        host,
        port=None,
        timeout=_DEFAULT_TIMEOUT,
        source_address=None,
        *,
        context=None,
        check_hostname=None,
        interface_name=None,
        # Deprecated, kept only for ABI compatibility with old callers.
        key_file=None,
        cert_file=None,
    ):
        import ssl

        # Resolve timeout at call time, not import time, so callers can change
        # the default before opening a connection.
        if timeout is _DEFAULT_TIMEOUT:
            timeout = socket.getdefaulttimeout()

        # Bind interface to link-local IPv6 address with zone ID if needed
        if interface_name is not None and "%" not in host:
            try:
                if isinstance(ipaddress.ip_address(host), ipaddress.IPv6Address):
                    host = host + "%" + interface_name
            except ValueError:
                # Not an IP address (likely a hostname) — skip zone binding.
                pass

        # Build a permissive context if none was supplied. AirDrop uses
        # self-signed certs by design, so we don't verify hostname or chain.
        if context is None:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            if cert_file:
                context.load_cert_chain(cert_file, keyfile=key_file)

        # Apply check_hostname override on the context (not via __init__)
        if check_hostname is not None:
            context.check_hostname = check_hostname

        super().__init__(
            host=host,
            port=port,
            timeout=timeout,
            source_address=source_address,
            context=context,
        )

        self.interface_name = interface_name
        self._create_connection = self.create_connection_awdl

    def create_connection_awdl(
        self, address, timeout=socket.getdefaulttimeout(), source_address=None
    ):
        """Connect to *address* and return the socket object.

        Convenience function.  Connect to *address* (a 2-tuple ``(host,
        port)``) and return the socket object.  Passing the optional
        *timeout* parameter will set the timeout on the socket instance
        before attempting to connect.  If no *timeout* is supplied, the
        global default timeout setting returned by :func:`getdefaulttimeout`
        is used.  If *source_address* is set it must be a tuple of (host, port)
        for the socket to bind as a source address before making the connection.
        A host of '' or port 0 tells the OS to use the default.
        """

        host, port = address
        err = None
        for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
            af, socktype, proto, _, sa = res
            sock = None
            try:
                sock = socket.socket(af, socktype, proto)
                if timeout is not socket.getdefaulttimeout():
                    sock.settimeout(timeout)
                if self.interface_name == "awdl0" and platform.system() == "Darwin":
                    sock.setsockopt(socket.SOL_SOCKET, 0x1104, 1)
                if source_address:
                    sock.bind(source_address)
                sock.connect(sa)
                # Break explicitly a reference cycle
                return sock

            except socket.error as _:
                err = _
                if sock is not None:
                    sock.close()

        if err is not None:
            raise err
        else:
            raise socket.error("getaddrinfo returns an empty list")
