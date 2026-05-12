"""
Tests for AirDropBrowser._is_self — the self-discovery filter.

When OpenDrop advertises itself via mDNS and then browses for services, the
zeroconf library naturally returns our own advertisement back to us. The GUI
must not display the local host as a remote device. This is the lowest-
priority but most-visible polish issue mentioned in the audit (A1).
"""

from unittest.mock import MagicMock

import pytest

from opendrop import network
from opendrop.client import AirDropBrowser
from opendrop.config import AirDropConfig


def _loopback_iface() -> str:
    import ifaddr

    for adapter in ifaddr.get_adapters():
        if adapter.name.startswith("lo"):
            return adapter.name
    pytest.skip("No loopback interface")


def test_is_self_recognizes_loopback_ipv6():
    """If a service advertises ::1, it must be classified as self."""
    config = AirDropConfig(interface=_loopback_iface())
    browser = AirDropBrowser(config)
    try:
        info = MagicMock()
        info.parsed_addresses.return_value = ["::1"]
        assert browser._is_self(info) is True
    finally:
        # AirDropBrowser holds a zeroconf instance; clean up.
        try:
            browser.zeroconf.close()
        except Exception:
            pass


def test_is_self_recognizes_loopback_ipv4():
    config = AirDropConfig(interface=_loopback_iface())
    browser = AirDropBrowser(config)
    try:
        info = MagicMock()
        info.parsed_addresses.return_value = ["127.0.0.1"]
        assert browser._is_self(info) is True
    finally:
        try:
            browser.zeroconf.close()
        except Exception:
            pass


def test_is_self_rejects_remote_address():
    config = AirDropConfig(interface=_loopback_iface())
    browser = AirDropBrowser(config)
    try:
        info = MagicMock()
        info.parsed_addresses.return_value = ["2001:db8::1"]
        assert browser._is_self(info) is False
    finally:
        try:
            browser.zeroconf.close()
        except Exception:
            pass


def test_is_self_handles_none_info():
    """info is None can happen during teardown — must not crash."""
    config = AirDropConfig(interface=_loopback_iface())
    browser = AirDropBrowser(config)
    try:
        assert browser._is_self(None) is False
    finally:
        try:
            browser.zeroconf.close()
        except Exception:
            pass


def test_is_self_handles_parse_failure():
    """A ServiceInfo whose addresses can't be parsed shouldn't crash."""
    config = AirDropConfig(interface=_loopback_iface())
    browser = AirDropBrowser(config)
    try:
        info = MagicMock()
        info.parsed_addresses.side_effect = RuntimeError("broken")
        assert browser._is_self(info) is False
    finally:
        try:
            browser.zeroconf.close()
        except Exception:
            pass


def test_add_service_filters_self(monkeypatch):
    """
    The critical integration: when zeroconf hands us back our own service,
    add_service must not invoke callback_add.
    """
    config = AirDropConfig(interface=_loopback_iface())
    browser = AirDropBrowser(config)
    try:
        called = []
        browser.callback_add = lambda info: called.append(info)

        info = MagicMock()
        info.parsed_addresses.return_value = ["::1"]
        zc = MagicMock()
        zc.get_service_info.return_value = info

        browser.add_service(zc, "_airdrop._tcp.local.", "self._airdrop._tcp.local.")
        assert called == [], "Self-advertisement should be filtered"
    finally:
        try:
            browser.zeroconf.close()
        except Exception:
            pass


def test_add_service_passes_through_remote(monkeypatch):
    """A genuinely remote service should fire the callback."""
    config = AirDropConfig(interface=_loopback_iface())
    browser = AirDropBrowser(config)
    try:
        called = []
        browser.callback_add = lambda info: called.append(info)

        info = MagicMock()
        info.parsed_addresses.return_value = ["2001:db8::42"]
        zc = MagicMock()
        zc.get_service_info.return_value = info

        browser.add_service(zc, "_airdrop._tcp.local.", "remote._airdrop._tcp.local.")
        assert len(called) == 1, "Remote service should pass through"
    finally:
        try:
            browser.zeroconf.close()
        except Exception:
            pass
