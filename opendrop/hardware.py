"""
Hardware capability detection for OpenDrop.

Tells the GUI (and the user) honestly which features of AirDrop will work
on this machine, *before* anything is attempted. Without this, OpenDrop
will keep trying to start OWL on incompatible chipsets and fail with cryptic
nl80211 errors.

The two questions that drive everything else:

  1. Can we run AWDL (i.e. can OWL bring up an awdl0 interface)?
     - Requires a Wi-Fi chipset that supports concurrent "managed + monitor"
       interface combinations, plus frame injection on the monitor side.
     - Intel CNVi chipsets (e.g. Wireless-AC 9560/9462, AX201/AX211) are
       known to lack the right interface combinations and will fail with
       "Operation not supported" when OWL configures nl80211. Broadcom
       FullMAC and Atheros ath9k_htc generally work.

  2. Can we use Bluetooth LE for AirDrop wake-up and BLE-only discovery?
     - Requires bluetoothd running and a usable adapter.
     - Cheap to detect via the org.bluez D-Bus service.

The check is deliberately read-only — it never reconfigures the host.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class AWDLCompatibility(Enum):
    """How well this host can run AWDL via OWL."""

    UNKNOWN = "unknown"  # We couldn't determine; user should try it
    LIKELY = "likely"  # Chipset is on the known-good list
    UNLIKELY = "unlikely"  # Chipset is on the known-bad list
    NOT_SUPPORTED = "not_supported"  # Driver doesn't even claim monitor mode
    OWL_NOT_INSTALLED = "owl_not_installed"


@dataclass
class WiFiAdapter:
    """One physical Wi-Fi adapter the kernel knows about."""

    phy: str  # e.g. "phy0"
    interface: str  # e.g. "wlo1"
    driver: str  # e.g. "iwlwifi"
    chipset: str  # vendor + model from lspci/lsusb
    bus: str  # "pci" or "usb"
    supports_monitor: bool = False
    supports_concurrent_monitor: bool = False
    """Can hold a managed + monitor interface at the same time?"""


@dataclass
class HardwareReport:
    """Snapshot of the host's AirDrop-relevant capabilities."""

    wifi_adapters: List[WiFiAdapter] = field(default_factory=list)
    bluetooth_available: bool = False
    bluetoothd_running: bool = False
    owl_installed: bool = False
    awdl_compatibility: AWDLCompatibility = AWDLCompatibility.UNKNOWN
    notes: List[str] = field(default_factory=list)

    @property
    def best_adapter(self) -> Optional[WiFiAdapter]:
        """The adapter most likely to support AWDL, or None."""
        # Prefer adapters that support concurrent monitor+managed.
        for a in self.wifi_adapters:
            if a.supports_concurrent_monitor:
                return a
        # Fall back to any monitor-capable adapter.
        for a in self.wifi_adapters:
            if a.supports_monitor:
                return a
        return self.wifi_adapters[0] if self.wifi_adapters else None

    def to_dict(self) -> dict:
        return {
            "wifi_adapters": [
                {
                    "phy": a.phy,
                    "interface": a.interface,
                    "driver": a.driver,
                    "chipset": a.chipset,
                    "bus": a.bus,
                    "supports_monitor": a.supports_monitor,
                    "supports_concurrent_monitor": a.supports_concurrent_monitor,
                }
                for a in self.wifi_adapters
            ],
            "bluetooth_available": self.bluetooth_available,
            "bluetoothd_running": self.bluetoothd_running,
            "owl_installed": self.owl_installed,
            "awdl_compatibility": self.awdl_compatibility.value,
            "notes": list(self.notes),
        }


# Known-bad chipsets that don't support concurrent managed+monitor.
# Add to this list as we learn about more incompatibilities.
_INCOMPATIBLE_CHIPSET_PATTERNS = [
    # Intel CNVi (companion radios that share the BT/Wi-Fi RF block)
    r"Wireless[- ]AC 9560",
    r"Wireless[- ]AC 9462",
    r"AX201",
    r"AX211",
    r"AX210",  # AX210 has been reported to work on some kernels but not most
    r"CNVi",
]

# Chipsets that historically work well with OWL.
_KNOWN_GOOD_CHIPSET_PATTERNS = [
    # Broadcom FullMAC family (used in old MacBooks)
    r"BCM43[0-9]{2}",
    # Atheros chipsets often used in USB dongles
    r"AR9271",
    r"AR9170",
    # Realtek devices commonly bundled in USB dongles
    r"RTL8812",
]


def detect() -> HardwareReport:
    """
    Run a non-invasive hardware probe and return a HardwareReport.

    This function never modifies any system state and never asks for
    elevated privileges. If a tool isn't installed, the corresponding
    fields are left blank.
    """
    report = HardwareReport()
    report.wifi_adapters = _detect_wifi_adapters()
    report.bluetooth_available, report.bluetoothd_running = _detect_bluetooth()
    report.owl_installed = shutil.which("owl") is not None
    report.awdl_compatibility = _classify_awdl_compat(report)
    _annotate(report)
    return report


def _detect_wifi_adapters() -> List[WiFiAdapter]:
    """
    Enumerate Wi-Fi adapters by walking /sys/class/net and consulting `iw`.

    We deliberately don't use NetworkManager / nmcli — we want to work
    on systems running systemd-networkd, iwd, ConnMan, etc.
    """
    adapters: List[WiFiAdapter] = []
    sys_net = "/sys/class/net"
    if not os.path.isdir(sys_net):
        return adapters

    for ifname in os.listdir(sys_net):
        wireless_dir = os.path.join(sys_net, ifname, "wireless")
        phy80211 = os.path.join(sys_net, ifname, "phy80211")
        if not (os.path.isdir(wireless_dir) or os.path.isdir(phy80211)):
            continue

        phy = _read_link(os.path.join(sys_net, ifname, "phy80211"))
        if phy:
            phy = os.path.basename(phy)
        else:
            phy = "phy0"

        driver_path = os.path.join(sys_net, ifname, "device", "driver")
        driver_link = _read_link(driver_path)
        driver = os.path.basename(driver_link) if driver_link else ""

        chipset, bus = _identify_chipset(ifname)
        supports_monitor, supports_concurrent = _iw_capabilities(phy)

        adapters.append(
            WiFiAdapter(
                phy=phy,
                interface=ifname,
                driver=driver,
                chipset=chipset,
                bus=bus,
                supports_monitor=supports_monitor,
                supports_concurrent_monitor=supports_concurrent,
            )
        )

    return adapters


def _read_link(path: str) -> Optional[str]:
    try:
        return os.readlink(path)
    except OSError:
        return None


def _identify_chipset(ifname: str) -> tuple[str, str]:
    """Return (chipset_description, bus) using lspci/lsusb fallbacks."""
    sys_device = f"/sys/class/net/{ifname}/device"
    real = os.path.realpath(sys_device)
    if "/pci" in real:
        return (_lspci_for(ifname), "pci")
    if "/usb" in real:
        return (_lsusb_for(ifname), "usb")
    return ("", "unknown")


def _lspci_for(ifname: str) -> str:
    """Look up the PCI device backing ifname and return its description."""
    if shutil.which("lspci") is None:
        return ""
    try:
        # Walk up the symlink to find the PCI slot
        device_path = os.path.realpath(f"/sys/class/net/{ifname}/device")
        pci_id = os.path.basename(device_path)
        out = subprocess.run(
            ["lspci", "-s", pci_id],
            capture_output=True,
            text=True,
            timeout=2,
        )
        line = out.stdout.strip().split("\n")[0]
        # Drop the slot id prefix like "00:14.3 "
        return re.sub(r"^[0-9a-f:.]+\s+", "", line, count=1).strip()
    except Exception as e:
        logger.debug(f"lspci lookup failed for {ifname}: {e}")
        return ""


def _lsusb_for(ifname: str) -> str:
    """Look up the USB device backing ifname."""
    if shutil.which("lsusb") is None:
        return ""
    try:
        device_path = os.path.realpath(f"/sys/class/net/{ifname}/device")
        # The vendor/product IDs live in idVendor/idProduct files near here
        for parent in [device_path, os.path.dirname(device_path)]:
            vendor_file = os.path.join(parent, "idVendor")
            product_file = os.path.join(parent, "idProduct")
            if os.path.exists(vendor_file) and os.path.exists(product_file):
                vendor = open(vendor_file).read().strip()
                product = open(product_file).read().strip()
                out = subprocess.run(
                    ["lsusb", "-d", f"{vendor}:{product}"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                line = out.stdout.strip().split("\n")[0]
                # Strip "Bus xxx Device yyy: ID vvvv:pppp " prefix
                return re.sub(
                    r"^Bus \d+ Device \d+: ID [0-9a-f]+:[0-9a-f]+\s+",
                    "",
                    line,
                ).strip()
        return ""
    except Exception as e:
        logger.debug(f"lsusb lookup failed for {ifname}: {e}")
        return ""


def _iw_capabilities(phy: str) -> tuple[bool, bool]:
    """
    Parse `iw phy <phy> info` to learn:
      - supports_monitor: does the driver advertise a "monitor" interface type?
      - supports_concurrent: is there a "valid interface combination" that
        lists *both* managed and monitor?
    """
    if shutil.which("iw") is None:
        logger.debug("iw not installed; cannot check capabilities")
        return (False, False)
    try:
        out = subprocess.run(
            ["iw", "phy", phy, "info"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        text = out.stdout
    except Exception as e:
        logger.debug(f"iw phy {phy} info failed: {e}")
        return (False, False)

    supports_monitor = bool(re.search(r"^\s*\*\s*monitor\s*$", text, re.M))

    # Look at the "valid interface combinations" block. A combination string
    # like "#{ managed, monitor } <= 2" indicates concurrent support.
    supports_concurrent = False
    in_combos = False
    for line in text.splitlines():
        if "valid interface combinations" in line:
            in_combos = True
            continue
        if in_combos:
            stripped = line.strip()
            if not stripped.startswith("*") and not stripped.startswith("#"):
                # Block of combos ended.
                if stripped == "" or stripped.endswith(":"):
                    continue
                in_combos = False
                continue
            if "managed" in line and "monitor" in line:
                supports_concurrent = True
                break

    return (supports_monitor, supports_concurrent)


def _detect_bluetooth() -> tuple[bool, bool]:
    """
    Returns (adapter_present, bluetoothd_running).

    Adapter presence is checked by looking at /sys/class/bluetooth; the
    daemon by trying to talk to org.bluez over D-Bus. We don't require
    bluetoothctl to be installed.
    """
    adapter_present = os.path.isdir("/sys/class/bluetooth") and any(
        name.startswith("hci")
        for name in os.listdir("/sys/class/bluetooth")
        if os.path.isdir(f"/sys/class/bluetooth/{name}")
    )
    bluetoothd_running = False
    try:
        # `systemctl is-active --quiet bluetooth` is cheap on systemd systems
        # but unreliable elsewhere. Try multiple paths.
        if shutil.which("systemctl"):
            r = subprocess.run(
                ["systemctl", "is-active", "--quiet", "bluetooth"],
                timeout=2,
            )
            bluetoothd_running = r.returncode == 0
        else:
            # Fallback: look for the daemon in /proc.
            for pid in os.listdir("/proc"):
                if not pid.isdigit():
                    continue
                try:
                    with open(f"/proc/{pid}/comm") as f:
                        if f.read().strip() == "bluetoothd":
                            bluetoothd_running = True
                            break
                except OSError:
                    continue
    except Exception as e:
        logger.debug(f"bluetoothd detection failed: {e}")

    return (adapter_present, bluetoothd_running)


def _classify_awdl_compat(report: HardwareReport) -> AWDLCompatibility:
    if not report.owl_installed:
        return AWDLCompatibility.OWL_NOT_INSTALLED

    best = report.best_adapter
    if best is None:
        return AWDLCompatibility.NOT_SUPPORTED
    if not best.supports_monitor:
        return AWDLCompatibility.NOT_SUPPORTED

    chipset = best.chipset or ""
    for pat in _INCOMPATIBLE_CHIPSET_PATTERNS:
        if re.search(pat, chipset, re.I):
            return AWDLCompatibility.UNLIKELY
    for pat in _KNOWN_GOOD_CHIPSET_PATTERNS:
        if re.search(pat, chipset, re.I):
            return AWDLCompatibility.LIKELY

    # We have monitor mode and an unknown chipset — let the user try.
    if best.supports_concurrent_monitor:
        return AWDLCompatibility.LIKELY
    return AWDLCompatibility.UNKNOWN


def _annotate(report: HardwareReport) -> None:
    """Add human-readable hints based on what we found."""
    if not report.wifi_adapters:
        report.notes.append("No Wi-Fi adapter detected.")
        return

    if report.awdl_compatibility == AWDLCompatibility.OWL_NOT_INSTALLED:
        report.notes.append(
            "OWL (Open Wireless Link) is not installed. AirDrop discovery "
            "of Apple devices requires OWL. Install with: "
            "https://github.com/seemoo-lab/owl"
        )

    if report.awdl_compatibility == AWDLCompatibility.UNLIKELY:
        best = report.best_adapter
        report.notes.append(
            f"Your Wi-Fi chipset ({best.chipset!r}) is known to be incompatible "
            "with OWL. Intel CNVi adapters cannot run a monitor interface "
            "alongside the managed (connected) one, which OWL requires. "
            "Recommended fix: plug in a USB Wi-Fi adapter using a different "
            "chipset (Atheros AR9271 or Realtek RTL8812 work well)."
        )

    if not report.bluetooth_available:
        report.notes.append(
            "No Bluetooth adapter detected. BLE wake-up is unavailable; "
            "Apple devices will only appear if they happen to also be "
            "active on AWDL/mDNS at scan time."
        )
    elif not report.bluetoothd_running:
        report.notes.append(
            "bluetoothd is not running. Enable it: " "sudo systemctl start bluetooth"
        )
