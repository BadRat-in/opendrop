"""
Tests for opendrop.hardware — hardware capability detection.

These tests verify the classification logic with synthetic inputs so they
don't depend on the test runner's actual hardware (and so they pass in CI).
The integration smoke test at the end calls detect() and just checks that
it doesn't crash.
"""

from opendrop import hardware
from opendrop.hardware import (
    AWDLCompatibility,
    HardwareReport,
    WiFiAdapter,
    _classify_awdl_compat,
)


def _adapter(
    chipset: str = "",
    supports_monitor: bool = True,
    supports_concurrent: bool = False,
    driver: str = "iwlwifi",
    bus: str = "pci",
) -> WiFiAdapter:
    return WiFiAdapter(
        phy="phy0",
        interface="wlo1",
        driver=driver,
        chipset=chipset,
        bus=bus,
        supports_monitor=supports_monitor,
        supports_concurrent_monitor=supports_concurrent,
    )


def test_classify_unknown_when_owl_missing():
    r = HardwareReport(owl_installed=False)
    r.wifi_adapters.append(_adapter())
    assert _classify_awdl_compat(r) == AWDLCompatibility.OWL_NOT_INSTALLED


def test_classify_not_supported_when_no_monitor():
    r = HardwareReport(owl_installed=True)
    r.wifi_adapters.append(_adapter(supports_monitor=False))
    assert _classify_awdl_compat(r) == AWDLCompatibility.NOT_SUPPORTED


def test_classify_unlikely_for_intel_cnvi():
    r = HardwareReport(owl_installed=True)
    r.wifi_adapters.append(_adapter(chipset="Intel Wireless-AC 9560"))
    assert _classify_awdl_compat(r) == AWDLCompatibility.UNLIKELY


def test_classify_unlikely_for_ax201():
    r = HardwareReport(owl_installed=True)
    r.wifi_adapters.append(_adapter(chipset="Intel Wi-Fi 6 AX201 160MHz"))
    assert _classify_awdl_compat(r) == AWDLCompatibility.UNLIKELY


def test_classify_likely_for_broadcom():
    r = HardwareReport(owl_installed=True)
    r.wifi_adapters.append(
        _adapter(chipset="Broadcom BCM4360", supports_concurrent=True)
    )
    assert _classify_awdl_compat(r) == AWDLCompatibility.LIKELY


def test_classify_likely_for_atheros_usb():
    r = HardwareReport(owl_installed=True)
    r.wifi_adapters.append(
        _adapter(chipset="Atheros AR9271 USB", driver="ath9k_htc", bus="usb")
    )
    assert _classify_awdl_compat(r) == AWDLCompatibility.LIKELY


def test_classify_likely_when_concurrent_supported():
    """Even an unknown chipset is 'likely' if it advertises concurrent mode."""
    r = HardwareReport(owl_installed=True)
    r.wifi_adapters.append(
        _adapter(chipset="MysteryCorp WL-1234", supports_concurrent=True)
    )
    assert _classify_awdl_compat(r) == AWDLCompatibility.LIKELY


def test_classify_unknown_when_concurrent_unknown():
    """Unknown chipset without concurrent mode → unknown, let user try."""
    r = HardwareReport(owl_installed=True)
    r.wifi_adapters.append(
        _adapter(chipset="MysteryCorp WL-1234", supports_concurrent=False)
    )
    assert _classify_awdl_compat(r) == AWDLCompatibility.UNKNOWN


def test_best_adapter_prefers_concurrent():
    """Adapter with concurrent support should win over plain monitor-mode one."""
    r = HardwareReport()
    bad = _adapter(chipset="Intel AX201", supports_concurrent=False)
    good = _adapter(
        chipset="Atheros AR9271",
        driver="ath9k_htc",
        bus="usb",
        supports_concurrent=True,
    )
    r.wifi_adapters.extend([bad, good])
    assert r.best_adapter is good


def test_best_adapter_when_no_monitor():
    """When no adapter has monitor mode, return the first one anyway."""
    r = HardwareReport()
    r.wifi_adapters.append(_adapter(supports_monitor=False))
    assert r.best_adapter is r.wifi_adapters[0]


def test_to_dict_round_trip():
    """Report should serialize to JSON-able dict without raising."""
    r = HardwareReport(owl_installed=True)
    r.wifi_adapters.append(_adapter(chipset="Intel AX201"))
    r.notes.append("test note")
    r.awdl_compatibility = AWDLCompatibility.UNLIKELY
    d = r.to_dict()
    assert d["owl_installed"] is True
    assert d["awdl_compatibility"] == "unlikely"
    assert len(d["wifi_adapters"]) == 1
    assert d["notes"] == ["test note"]


def test_detect_smoke():
    """The real detect() must not crash on whatever system runs the tests."""
    report = hardware.detect()
    assert isinstance(report, HardwareReport)
    # We can't assert anything about adapters because CI runners vary, but
    # the AWDL compatibility must always be one of the documented enum values.
    assert report.awdl_compatibility in set(AWDLCompatibility)
