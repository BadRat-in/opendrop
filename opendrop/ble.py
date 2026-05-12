"""
Bluetooth Low Energy support for AirDrop discovery.

This module implements the BLE half of the AirDrop discovery protocol that
Apple devices use. Specifically:

1. **Scanning**: detect nearby Apple devices that are actively advertising
   AirDrop. Apple manufacturer data is identified by company ID 0x004C and
   the AirDrop entry by sub-type 0x05.

2. **Advertising**: broadcast our own AirDrop BLE beacon so that Apple
   devices in "Everyone" mode start their AWDL interface and become
   discoverable on mDNS.

Why this matters: Apple keeps the awdl0 interface and the AirDrop HTTPS
service inactive to save power. AWDL only wakes up after the device sees
an AirDrop BLE advertisement. Without this module, Linux clients (even
with OWL running) will never find Apple devices because Apple stays silent
on mDNS until BLE-poked.

BLE frame layout (per Stute et al., USENIX Security 2019):

    Manufacturer Data (company id 0x004C - Apple):
        type     1 byte    0x05  (AirDrop)
        length   1 byte    0x12  (18 octets following)
        zeros    8 bytes   0x00 * 8  (reserved / version)
        appleid  2 bytes   first 2 bytes of SHA-256(apple-id)
        phone    2 bytes   first 2 bytes of SHA-256(phone number)
        email    2 bytes   first 2 bytes of SHA-256(email)
        email2   2 bytes   first 2 bytes of SHA-256(other email)

In Contacts Only mode the receiver checks these hashes against its address
book and ignores the beacon if nothing matches. In Everyone mode the
receiver accepts any beacon.

Linux dependencies: bleak >= 0.21, BlueZ 5.50+, a working Bluetooth adapter.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Apple's assigned Bluetooth SIG company identifier.
APPLE_COMPANY_ID = 0x004C

# Sub-type byte inside Apple manufacturer data for the AirDrop beacon.
AIRDROP_TYPE = 0x05

# Default length byte announced by Apple AirDrop beacons (matches paper).
AIRDROP_PAYLOAD_LEN = 0x12


@dataclass
class AppleBLEDevice:
    """
    A nearby Apple device that's advertising AirDrop over BLE.

    Carries enough information to display the device in the GUI before any
    mDNS or AWDL communication has happened.
    """

    address: str  # MAC address (or randomized RPA)
    rssi: int
    name: Optional[str] = None
    apple_id_hash: Optional[bytes] = None
    phone_hash: Optional[bytes] = None
    email_hash: Optional[bytes] = None
    email2_hash: Optional[bytes] = None
    raw_payload: bytes = b""
    last_seen: float = 0.0

    @property
    def short_id(self) -> str:
        """A short stable identifier for deduplication."""
        return self.address.replace(":", "").lower()


def parse_airdrop_beacon(payload: bytes) -> Optional[Dict[str, bytes]]:
    """
    Parse the payload bytes following an Apple manufacturer-data prefix.

    The expected layout (after the Apple company id has been stripped):
        byte 0       sub-type    must be 0x05 to be an AirDrop beacon
        byte 1       length      typically 0x12 (18)
        bytes 2-9    zero padding
        bytes 10-11  apple-id hash
        bytes 12-13  phone hash
        bytes 14-15  email hash
        bytes 16-17  email2 hash

    Args:
        payload: The bytes that come right after the Apple company id (0x004C).

    Returns:
        A dict with keys apple_id_hash, phone_hash, email_hash, email2_hash
        if this is an AirDrop beacon. None otherwise.
    """
    if len(payload) < 2:
        return None
    if payload[0] != AIRDROP_TYPE:
        return None

    # The length byte tells us how many bytes follow, but we only need 18 for
    # the standard AirDrop layout. Tolerate slightly shorter beacons by zero-
    # padding so a fragmented advertisement doesn't crash the parser.
    if len(payload) < 18:
        payload = payload + b"\x00" * (18 - len(payload))

    return {
        "apple_id_hash": payload[10:12],
        "phone_hash": payload[12:14],
        "email_hash": payload[14:16],
        "email2_hash": payload[16:18],
    }


def build_airdrop_beacon(
    apple_id_hash: bytes = b"\x00\x00",
    phone_hash: bytes = b"\x00\x00",
    email_hash: bytes = b"\x00\x00",
    email2_hash: bytes = b"\x00\x00",
) -> bytes:
    """
    Build the manufacturer-data payload for an AirDrop BLE advertisement.

    By default all four contact-hash fields are zero. Apple devices in
    Everyone mode will respond regardless; devices in Contacts Only mode
    will ignore us, which is the correct behavior (we don't pretend to
    be a known contact).

    Args:
        apple_id_hash: 2-byte hash slot. Pad/truncate to exactly 2 bytes.
        phone_hash:    2-byte hash slot.
        email_hash:    2-byte hash slot.
        email2_hash:   2-byte hash slot.

    Returns:
        The full Apple manufacturer-data payload (without the 0x004C prefix —
        BlueZ will prepend that when we register the advertisement).
    """

    def pad(b: bytes) -> bytes:
        if len(b) >= 2:
            return b[:2]
        return b + b"\x00" * (2 - len(b))

    return (
        bytes([AIRDROP_TYPE, AIRDROP_PAYLOAD_LEN])
        + b"\x00" * 8
        + pad(apple_id_hash)
        + pad(phone_hash)
        + pad(email_hash)
        + pad(email2_hash)
    )


def random_airdrop_beacon() -> bytes:
    """
    Build an AirDrop beacon with random hash bytes.

    Useful when you want to wake up Apple receivers without claiming to be a
    particular contact. The randomness avoids accidentally matching a real
    contact hash (which would be confusing on macOS / iOS).
    """
    return build_airdrop_beacon(
        apple_id_hash=secrets.token_bytes(2),
        phone_hash=secrets.token_bytes(2),
        email_hash=secrets.token_bytes(2),
        email2_hash=secrets.token_bytes(2),
    )


@dataclass
class BLEScanner:
    """
    Async-driven BLE scanner that surfaces Apple AirDrop beacons.

    Usage:

        scanner = BLEScanner(on_device=lambda dev: print(dev))
        async with scanner:
            await asyncio.sleep(10)

    Or run as a long-lived task:

        scanner = BLEScanner(on_device=callback)
        await scanner.start()
        ...
        await scanner.stop()
    """

    on_device: Callable[[AppleBLEDevice], None]
    scan_interval: float = 30.0  # seconds before re-scanning RSSI
    _devices: Dict[str, AppleBLEDevice] = field(default_factory=dict)
    _scanner: object = None
    _running: bool = False

    async def __aenter__(self) -> "BLEScanner":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    async def start(self) -> None:
        """Begin BLE scanning. Raises RuntimeError if BLE stack unavailable."""
        if self._running:
            return

        try:
            from bleak import BleakScanner  # local import — bleak is optional
        except ImportError as e:
            raise RuntimeError(
                "BLE support requires the 'bleak' package. "
                "Install it with: pip install bleak"
            ) from e

        self._scanner = BleakScanner(detection_callback=self._on_advertisement)
        try:
            await self._scanner.start()
        except Exception as e:
            self._scanner = None
            raise RuntimeError(
                f"Failed to start BLE scanner: {e}. "
                "Make sure Bluetooth is enabled and the bluetoothd service "
                "is running."
            ) from e

        self._running = True
        logger.info("BLE scanner started")

    async def stop(self) -> None:
        if not self._running:
            return
        try:
            if self._scanner is not None:
                await self._scanner.stop()
        except Exception as e:
            logger.debug(f"Error stopping BLE scanner: {e}")
        finally:
            self._scanner = None
            self._running = False
            logger.info("BLE scanner stopped")

    def _on_advertisement(self, device, advertisement_data) -> None:
        """
        Called by bleak for every BLE advertisement.

        Filter for Apple manufacturer data and decode AirDrop beacons.
        """
        manufacturer = advertisement_data.manufacturer_data or {}
        if APPLE_COMPANY_ID not in manufacturer:
            return

        payload = manufacturer[APPLE_COMPANY_ID]
        parsed = parse_airdrop_beacon(payload)
        if parsed is None:
            return

        addr = str(device.address)
        rssi = getattr(advertisement_data, "rssi", 0)
        if rssi == 0:
            # Some bleak versions report RSSI on the device object instead.
            rssi = getattr(device, "rssi", 0) or 0

        ble_dev = AppleBLEDevice(
            address=addr,
            rssi=rssi,
            name=getattr(device, "name", None)
            or getattr(advertisement_data, "local_name", None),
            apple_id_hash=parsed["apple_id_hash"],
            phone_hash=parsed["phone_hash"],
            email_hash=parsed["email_hash"],
            email2_hash=parsed["email2_hash"],
            raw_payload=payload,
            last_seen=_now(),
        )

        existing = self._devices.get(ble_dev.short_id)
        self._devices[ble_dev.short_id] = ble_dev

        if existing is None:
            logger.info(
                f"New Apple AirDrop device via BLE: {ble_dev.address} (rssi {rssi})"
            )

        try:
            self.on_device(ble_dev)
        except Exception as e:
            logger.warning(f"BLE on_device callback raised: {e}")

    @property
    def devices(self) -> List[AppleBLEDevice]:
        """Snapshot of all Apple devices seen so far."""
        return list(self._devices.values())


def _now() -> float:
    """Monotonic-ish timestamp; uses time.time() so it can be compared across runs."""
    import time

    return time.time()


# ---------------------------------------------------------------------------
# BLE Advertiser (Linux/BlueZ-only — depends on org.bluez.LEAdvertisingManager1)
# ---------------------------------------------------------------------------


class BLEAdvertiser:
    """
    Advertise an AirDrop BLE beacon so nearby Apple devices wake their AWDL
    interface and become discoverable on mDNS.

    On Linux this requires:
      - BlueZ 5.42+ (LE Advertising D-Bus API)
      - bluetoothd running
      - The user (or our process) able to talk to the org.bluez D-Bus service.
        Typically the `bluetooth` group; pkexec/polkit can be used otherwise.

    Implementation uses dbus-fast (a transitive dependency of bleak) so we
    don't pull in a separate D-Bus library.

    NOTE: This is a thin Linux-only implementation. macOS / Windows would
    need different backends, but those platforms have native AirDrop so the
    omission is fine.
    """

    BLUEZ_BUS = "org.bluez"
    ADAPTER_IFACE = "org.bluez.Adapter1"
    LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
    LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

    def __init__(
        self,
        payload: Optional[bytes] = None,
        adapter: str = "hci0",
        local_name: str = "OpenDrop",
    ):
        """
        Args:
            payload: AirDrop beacon bytes. If None, a random one is generated.
            adapter: Bluetooth adapter name (default hci0).
            local_name: BLE local name field — visible in some BLE tools.
        """
        self.payload = payload if payload is not None else random_airdrop_beacon()
        self.adapter = adapter
        self.local_name = local_name
        self._bus = None
        self._ad_path = "/org/opendrop/airdrop_beacon"
        self._registered = False

    async def start(self) -> None:
        """Register the advertisement with BlueZ and start broadcasting."""
        from dbus_fast.aio import MessageBus  # local import: optional dep
        from dbus_fast import BusType, Message

        # We need a system-bus connection because BlueZ lives on the system bus.
        try:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        except Exception as e:
            raise RuntimeError(
                "Could not connect to system D-Bus. Bluetooth advertising "
                "requires bluetoothd to be running and your user to be in "
                "the 'bluetooth' group (or use pkexec)."
            ) from e

        try:
            await self._export_advertisement()
            await self._register_advertisement()
            self._registered = True
            logger.info(
                f"AirDrop BLE beacon registered on {self.adapter} ({len(self.payload)} bytes payload)"
            )
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        if not self._bus:
            return
        try:
            if self._registered:
                await self._unregister_advertisement()
        except Exception as e:
            logger.debug(f"Error unregistering advertisement: {e}")
        finally:
            self._registered = False
            try:
                self._bus.disconnect()
            except Exception:
                pass
            self._bus = None
            logger.info("AirDrop BLE beacon stopped")

    async def _export_advertisement(self) -> None:
        """
        Export an object on our D-Bus connection that implements
        org.bluez.LEAdvertisement1. BlueZ will read our manufacturer data
        from this object after we register it.

        We intentionally omit LocalName because the BLE advertising packet
        is capped at 31 bytes. With a 22-byte manufacturer-data field
        (2-byte Apple id + 18-byte AirDrop payload + headers) and a
        ~10-byte local name we'd overflow and BlueZ would reject the
        advertisement with "Failed to parse advertisement".
        """
        from dbus_fast.service import ServiceInterface, dbus_property, method
        from dbus_fast import PropertyAccess, Variant

        payload = self.payload

        class Advertisement(ServiceInterface):
            def __init__(self):
                super().__init__(BLEAdvertiser.LE_ADVERTISEMENT_IFACE)

            @dbus_property(access=PropertyAccess.READ)
            def Type(self) -> "s":  # type: ignore[name-defined]
                return "broadcast"

            @dbus_property(access=PropertyAccess.READ)
            def ManufacturerData(self) -> "a{qv}":  # type: ignore[name-defined]
                # Map: company id (uint16) -> Variant("ay", bytes).
                # dbus-fast wants real `bytes` for "ay" signatures.
                return {APPLE_COMPANY_ID: Variant("ay", payload)}

            @method()
            def Release(self):  # noqa: N802 (BlueZ-mandated name)
                logger.debug("BlueZ released our advertisement")

        self._advertisement = Advertisement()
        self._bus.export(self._ad_path, self._advertisement)

    async def _register_advertisement(self) -> None:
        from dbus_fast import Message, MessageType

        path = f"/org/bluez/{self.adapter}"

        msg = Message(
            destination=self.BLUEZ_BUS,
            path=path,
            interface=self.LE_ADVERTISING_MANAGER_IFACE,
            member="RegisterAdvertisement",
            signature="oa{sv}",
            body=[self._ad_path, {}],
        )
        reply = await self._bus.call(msg)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(
                f"BlueZ rejected our advertisement on {self.adapter}: {reply.body}"
            )

    async def _unregister_advertisement(self) -> None:
        from dbus_fast import Message

        path = f"/org/bluez/{self.adapter}"
        msg = Message(
            destination=self.BLUEZ_BUS,
            path=path,
            interface=self.LE_ADVERTISING_MANAGER_IFACE,
            member="UnregisterAdvertisement",
            signature="o",
            body=[self._ad_path],
        )
        try:
            await self._bus.call(msg)
        except Exception as e:
            logger.debug(f"UnregisterAdvertisement: {e}")
