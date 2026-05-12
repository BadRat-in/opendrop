"""
Tests for opendrop.network — local IP detection and interface selection.

These tests deliberately avoid mocking the kernel — they check that our
helpers return sensible answers for the host they actually run on.
"""

import ipaddress

import pytest

from opendrop import network


def test_list_interfaces_returns_something():
    """Every Linux host has at least a loopback interface."""
    interfaces = network.list_interfaces()
    assert len(interfaces) >= 1
    names = [name for name, _ in interfaces]
    assert any(n.startswith("lo") for n in names), f"No loopback found in {names}"


def test_local_ipv6_addresses_includes_loopback():
    """::1 should always be a local IPv6 address."""
    addrs = network.local_ipv6_addresses()
    assert "::1" in addrs


def test_local_ipv4_addresses_includes_loopback():
    """127.0.0.1 should always be a local IPv4 address."""
    addrs = network.local_ipv4_addresses()
    assert "127.0.0.1" in addrs


def test_is_local_address_loopback_v4():
    assert network.is_local_address("127.0.0.1") is True


def test_is_local_address_loopback_v6():
    assert network.is_local_address("::1") is True


def test_is_local_address_strips_zone_id():
    """fe80 addresses come back from getsockname() with a %iface suffix."""
    addrs = network.local_ipv6_addresses()
    # Find any link-local address if we have one
    link_local = [a for a in addrs if a.startswith("fe80")]
    if not link_local:
        pytest.skip("Host has no link-local IPv6 addresses")
    # Append a fake zone ID and verify it's still recognized
    assert network.is_local_address(f"{link_local[0]}%fakezone") is True


def test_is_local_address_rejects_remote():
    assert network.is_local_address("8.8.8.8") is False
    assert network.is_local_address("2001:4860:4860::8888") is False


def test_is_local_address_rejects_garbage():
    assert network.is_local_address("not-an-address") is False
    assert network.is_local_address("") is False
    assert network.is_local_address(None) is False  # type: ignore[arg-type]


def test_find_interface_with_ipv6_returns_string():
    """Should return either an interface name or None — never crash."""
    result = network.find_interface_with_ipv6()
    if result is not None:
        assert isinstance(result, str)
        assert len(result) > 0
