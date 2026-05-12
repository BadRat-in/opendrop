"""
Cross-distro platform abstraction for OpenDrop.

The Linux ecosystem is fragmented:
- Init systems: systemd, OpenRC, runit, s6, sysv-init
- Privilege escalation: sudo, doas, pkexec (polkit)
- Package managers: apt, dnf, pacman, zypper, apk, emerge

Rather than scattering `if systemd: ... elif openrc: ...` across the
codebase, this module centralizes the abstractions. Each helper tries
the available implementations in a sensible order and tells the caller
which one it used (so the GUI / installer can report it).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class InitSystem(Enum):
    """Detected init / service manager."""

    SYSTEMD = "systemd"
    OPENRC = "openrc"
    RUNIT = "runit"
    S6 = "s6"
    SYSVINIT = "sysvinit"
    UNKNOWN = "unknown"


class PrivilegeTool(Enum):
    """Detected privilege escalation tool."""

    PKEXEC = "pkexec"  # polkit — best UX, GUI password prompt
    SUDO = "sudo"  # everywhere
    DOAS = "doas"  # OpenBSD-style, popular on Alpine/Void
    NONE = "none"


class PackageManager(Enum):
    """Detected package manager."""

    APT = "apt"  # Debian, Ubuntu, Parrot
    DNF = "dnf"  # Fedora, RHEL 8+
    YUM = "yum"  # RHEL 7
    PACMAN = "pacman"  # Arch, Manjaro
    ZYPPER = "zypper"  # openSUSE
    APK = "apk"  # Alpine
    EMERGE = "emerge"  # Gentoo
    XBPS = "xbps-install"  # Void Linux
    UNKNOWN = "unknown"


@dataclass
class DistroInfo:
    """What `/etc/os-release` says about this host."""

    id: str = ""  # "ubuntu", "fedora", "arch", "parrot", ...
    id_like: str = ""  # "debian", "fedora", ...
    name: str = ""  # "Ubuntu 24.04 LTS"
    version_id: str = ""
    pretty_name: str = ""

    @property
    def is_debian_family(self) -> bool:
        return "debian" in (self.id, self.id_like) or self.id == "debian"

    @property
    def is_fedora_family(self) -> bool:
        return self.id in ("fedora", "rhel", "centos") or "fedora" in self.id_like

    @property
    def is_arch_family(self) -> bool:
        return self.id in ("arch", "manjaro", "endeavouros") or "arch" in self.id_like

    @property
    def is_suse_family(self) -> bool:
        return "suse" in self.id or "suse" in self.id_like


def detect_distro() -> DistroInfo:
    """Read /etc/os-release. Returns an empty DistroInfo if missing."""
    info = DistroInfo()
    try:
        with open("/etc/os-release") as f:
            for line in f:
                line = line.strip()
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                val = val.strip('"')
                if key == "ID":
                    info.id = val.lower()
                elif key == "ID_LIKE":
                    info.id_like = val.lower()
                elif key == "NAME":
                    info.name = val
                elif key == "VERSION_ID":
                    info.version_id = val
                elif key == "PRETTY_NAME":
                    info.pretty_name = val
    except OSError as e:
        logger.debug(f"Could not read /etc/os-release: {e}")
    return info


def detect_init_system() -> InitSystem:
    """
    Identify the init system. Order of checks:
      1. /run/systemd/system exists → systemd
      2. /run/openrc exists → OpenRC
      3. /etc/runit/runsvdir/default exists → runit
      4. /run/service/.s6-svscan exists → s6
      5. /etc/inittab exists with sysv-style entries → sysvinit
    """
    if os.path.isdir("/run/systemd/system"):
        return InitSystem.SYSTEMD
    if os.path.isdir("/run/openrc"):
        return InitSystem.OPENRC
    if os.path.isdir("/etc/runit/runsvdir"):
        return InitSystem.RUNIT
    if os.path.isdir("/run/service") and any(
        ".s6-svscan" in n for n in os.listdir("/run/service") if not n.startswith(".")
    ):
        return InitSystem.S6
    if os.path.exists("/etc/inittab"):
        return InitSystem.SYSVINIT
    return InitSystem.UNKNOWN


def detect_privilege_tool(gui: bool = True) -> PrivilegeTool:
    """
    Choose a privilege-escalation tool.

    Args:
        gui: If True, prefer pkexec (graphical polkit prompt) over sudo
             (which generally requires a terminal for password entry).
    """
    if gui and shutil.which("pkexec"):
        return PrivilegeTool.PKEXEC
    if shutil.which("sudo"):
        return PrivilegeTool.SUDO
    if shutil.which("doas"):
        return PrivilegeTool.DOAS
    if shutil.which("pkexec"):
        return PrivilegeTool.PKEXEC
    return PrivilegeTool.NONE


def detect_package_manager() -> PackageManager:
    """Pick a package manager based on what's installed."""
    candidates = [
        ("apt", PackageManager.APT),
        ("dnf", PackageManager.DNF),
        ("yum", PackageManager.YUM),
        ("pacman", PackageManager.PACMAN),
        ("zypper", PackageManager.ZYPPER),
        ("apk", PackageManager.APK),
        ("emerge", PackageManager.EMERGE),
        ("xbps-install", PackageManager.XBPS),
    ]
    for binary, pm in candidates:
        if shutil.which(binary):
            return pm
    return PackageManager.UNKNOWN


def service_command(action: str, service: str) -> List[str]:
    """
    Build a command list to operate on a system service.

    Examples:
        service_command("start", "bluetooth")
        → ["systemctl", "start", "bluetooth"]   on systemd
        → ["rc-service", "bluetooth", "start"]  on OpenRC

    Args:
        action: "start", "stop", "restart", "status", "enable", "disable"
        service: service name (without .service suffix)

    Returns:
        Argv list ready to pass to subprocess.run.
        Raises NotImplementedError if action is unsupported on the detected
        init system.
    """
    init = detect_init_system()

    if init == InitSystem.SYSTEMD:
        return ["systemctl", action, service]
    if init == InitSystem.OPENRC:
        # openrc: "rc-service name start" for start/stop/status,
        #         "rc-update add name default" for enable
        if action in ("start", "stop", "restart", "status"):
            return ["rc-service", service, action]
        if action == "enable":
            return ["rc-update", "add", service, "default"]
        if action == "disable":
            return ["rc-update", "del", service, "default"]
    if init == InitSystem.RUNIT:
        if action in ("start", "stop", "restart", "status"):
            return ["sv", action, service]
        if action == "enable":
            return ["ln", "-s", f"/etc/sv/{service}", "/var/service/"]
        if action == "disable":
            return ["rm", f"/var/service/{service}"]
    if init == InitSystem.SYSVINIT:
        if action in ("start", "stop", "restart", "status"):
            return [f"/etc/init.d/{service}", action]
    raise NotImplementedError(
        f"Service action {action!r} is not implemented for {init.value}"
    )


def privileged_command(argv: List[str], description: str = "") -> List[str]:
    """
    Wrap argv with the detected privilege-escalation tool.

    For pkexec, ``description`` is unused (polkit reads the action from
    /usr/share/polkit-1/actions). For sudo we pass `-A` so the user agent
    can prompt graphically if SUDO_ASKPASS is set; otherwise sudo will
    fall back to tty input.

    Returns:
        New argv ready to subprocess.run.
    """
    tool = detect_privilege_tool()
    if tool == PrivilegeTool.PKEXEC:
        return ["pkexec", *argv]
    if tool == PrivilegeTool.SUDO:
        return ["sudo", *argv]
    if tool == PrivilegeTool.DOAS:
        return ["doas", *argv]
    # No tool found — return as-is and let it fail with a clear permission
    # error rather than a "command not found" mystery.
    return argv


def install_packages(packages: List[str]) -> Tuple[bool, str]:
    """
    Install OS packages via the detected package manager.

    This is the only function in this module that *modifies* the system.
    The caller is expected to already hold elevated privileges (it is
    intended to be called from a privileged installer script, not from
    the unprivileged GUI process).

    Returns:
        (success, stderr_or_message)
    """
    pm = detect_package_manager()
    if pm == PackageManager.UNKNOWN:
        return (False, "No supported package manager found.")

    cmd_map = {
        PackageManager.APT: ["apt", "install", "-y"],
        PackageManager.DNF: ["dnf", "install", "-y"],
        PackageManager.YUM: ["yum", "install", "-y"],
        PackageManager.PACMAN: ["pacman", "-S", "--needed", "--noconfirm"],
        PackageManager.ZYPPER: ["zypper", "install", "-y"],
        PackageManager.APK: ["apk", "add"],
        PackageManager.EMERGE: ["emerge", "-n"],
        PackageManager.XBPS: ["xbps-install", "-y"],
    }
    cmd = cmd_map[pm] + list(packages)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode == 0:
            return (True, r.stdout)
        return (False, r.stderr.strip() or r.stdout.strip())
    except FileNotFoundError as e:
        return (False, str(e))


def map_dependency_packages() -> List[str]:
    """
    Return the OS package names that OpenDrop (and OWL) need on this distro.

    These are *system* packages — Python deps are installed via pip/uv.
    """
    info = detect_distro()
    if info.is_debian_family:
        return [
            "libpcap0.8",
            "libev4",
            "libnl-3-200",
            "libnl-genl-3-200",
            "bluetooth",
            "bluez",
        ]
    if info.is_fedora_family:
        return [
            "libpcap",
            "libev",
            "libnl3",
            "bluez",
        ]
    if info.is_arch_family:
        return [
            "libpcap",
            "libev",
            "libnl",
            "bluez",
            "bluez-utils",
        ]
    if info.is_suse_family:
        return [
            "libpcap1",
            "libev4",
            "libnl3-200",
            "bluez",
        ]
    # Generic fallback — names that exist on most package archives.
    return ["libpcap", "libev", "libnl3", "bluez"]
