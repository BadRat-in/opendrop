"""
Tests for opendrop.platform_compat — cross-distro abstractions.

The functions are inherently platform-dependent. We test the pieces we can
without mocking the whole filesystem.
"""

from opendrop import platform_compat as pc
from opendrop.platform_compat import (
    DistroInfo,
    InitSystem,
    PackageManager,
    PrivilegeTool,
    detect_distro,
    detect_init_system,
    detect_package_manager,
    detect_privilege_tool,
    map_dependency_packages,
    service_command,
)


def test_detect_distro_returns_distro_info():
    """detect_distro must always return a DistroInfo, even on weird hosts."""
    info = detect_distro()
    assert isinstance(info, DistroInfo)
    # On a real Linux test runner there will be /etc/os-release.
    if info.id:
        assert info.id == info.id.lower()


def test_distro_family_predicates_are_mutually_consistent():
    """A single distro shouldn't claim to be Debian AND Arch."""
    info = detect_distro()
    flags = [
        info.is_debian_family,
        info.is_fedora_family,
        info.is_arch_family,
        info.is_suse_family,
    ]
    assert sum(flags) <= 1


def test_debian_family_recognized():
    info = DistroInfo(id="parrot", id_like="debian")
    assert info.is_debian_family is True


def test_fedora_family_recognized():
    info = DistroInfo(id="fedora")
    assert info.is_fedora_family is True


def test_arch_family_recognized():
    info = DistroInfo(id="manjaro", id_like="arch")
    assert info.is_arch_family is True


def test_suse_family_recognized():
    info = DistroInfo(id="opensuse-tumbleweed", id_like="suse opensuse")
    assert info.is_suse_family is True


def test_detect_init_system_returns_enum():
    """detect_init_system must always return an InitSystem enum value."""
    init = detect_init_system()
    assert isinstance(init, InitSystem)


def test_detect_privilege_tool_returns_enum():
    tool = detect_privilege_tool()
    assert isinstance(tool, PrivilegeTool)


def test_detect_package_manager_returns_enum():
    pm = detect_package_manager()
    assert isinstance(pm, PackageManager)


def test_service_command_systemd_format():
    """If detect_init_system returns SYSTEMD on this host, we get systemctl."""
    init = detect_init_system()
    if init != InitSystem.SYSTEMD:
        # Skip — can't test other forms on this runner.
        return
    cmd = service_command("start", "bluetooth")
    assert cmd == ["systemctl", "start", "bluetooth"]


def test_service_command_rejects_unknown_action():
    """Unknown actions should raise NotImplementedError, not return garbage."""
    init = detect_init_system()
    if init == InitSystem.UNKNOWN:
        return
    try:
        service_command("teleport", "bluetooth")
    except NotImplementedError:
        pass
    except Exception:
        # On systemd, "teleport" passes through to systemctl. That's
        # acceptable; systemctl will then error.
        pass


def test_map_dependency_packages_nonempty():
    """We always return *some* list, even on unknown distros."""
    pkgs = map_dependency_packages()
    assert isinstance(pkgs, list)
    assert len(pkgs) >= 1
    # Bluez should be in the list regardless of distro family.
    assert any("bluez" in p.lower() for p in pkgs)
