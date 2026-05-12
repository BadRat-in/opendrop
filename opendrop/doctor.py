"""
`opendrop-doctor` — a one-shot diagnostic for end users.

Prints a human-readable summary of the host's AirDrop-relevant capabilities
and tells the user, in plain language, what to expect from the GUI:

  - Will Apple devices be discoverable?
  - Will OWL be usable on this hardware?
  - Is Bluetooth set up for BLE wake-up?
  - Where to go from here if something is missing.

This is intentionally a *separate entrypoint*, not the GUI, so support can
ask a user to run it and paste the output without GUI weirdness getting in
the way.
"""

from __future__ import annotations

import argparse
import json
import sys
from textwrap import dedent

from . import hardware
from .hardware import AWDLCompatibility


def _print_section(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def _format_yesno(b: bool) -> str:
    return "yes" if b else "no"


def run(json_output: bool = False) -> int:
    report = hardware.detect()

    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.awdl_compatibility != AWDLCompatibility.NOT_SUPPORTED else 2

    _print_section("OpenDrop hardware diagnostic")

    if not report.wifi_adapters:
        print("No Wi-Fi adapters detected. OpenDrop needs at least one.")
        return 2

    _print_section("Wi-Fi adapters")
    for a in report.wifi_adapters:
        print(f"  • {a.interface}  driver={a.driver}  bus={a.bus}")
        print(f"      chipset: {a.chipset or 'unknown'}")
        print(
            f"      monitor mode: {_format_yesno(a.supports_monitor)};"
            f"   concurrent with managed: {_format_yesno(a.supports_concurrent_monitor)}"
        )

    _print_section("Bluetooth")
    print(f"  adapter present: {_format_yesno(report.bluetooth_available)}")
    print(f"  bluetoothd running: {_format_yesno(report.bluetoothd_running)}")

    _print_section("OWL (Open Wireless Link)")
    print(f"  installed: {_format_yesno(report.owl_installed)}")

    _print_section("AWDL compatibility verdict")
    verdict_lines = {
        AWDLCompatibility.LIKELY: (
            "LIKELY  — Your hardware should be able to run AWDL. Start OWL "
            "from the GUI to bring up awdl0."
        ),
        AWDLCompatibility.UNKNOWN: (
            "UNKNOWN — Your chipset isn't on our known-good or known-bad list. "
            "Try starting OWL and report your results so we can update the "
            "compatibility table."
        ),
        AWDLCompatibility.UNLIKELY: (
            "UNLIKELY — Your Wi-Fi chipset is known to refuse the kernel "
            "interface combination OWL needs. Use a different Wi-Fi adapter "
            "(USB dongles with Atheros AR9271 or Realtek RTL8812 work well)."
        ),
        AWDLCompatibility.NOT_SUPPORTED: (
            "NOT SUPPORTED — Your Wi-Fi driver doesn't advertise monitor mode. "
            "AWDL is unreachable. Use a USB adapter with a compatible chipset."
        ),
        AWDLCompatibility.OWL_NOT_INSTALLED: (
            "OWL is not installed. Without it, OpenDrop cannot reach Apple "
            "devices over AWDL. Install OWL from "
            "https://github.com/seemoo-lab/owl"
        ),
    }
    print(f"  {verdict_lines[report.awdl_compatibility]}")

    if report.notes:
        _print_section("Notes")
        for note in report.notes:
            print(f"  • {note}")

    _print_section("What will work right now")
    can_advertise_mdns = bool(report.wifi_adapters)
    can_ble_scan = report.bluetooth_available and report.bluetoothd_running
    can_awdl = report.awdl_compatibility in (
        AWDLCompatibility.LIKELY,
        AWDLCompatibility.UNKNOWN,
    )
    print(
        f"  mDNS advertising (Apple devices can see OpenDrop):  "
        f"{_format_yesno(can_advertise_mdns)}"
    )
    print(
        f"  BLE scan (wake-aware nearby Apple device detection):  {_format_yesno(can_ble_scan)}"
    )
    print(
        f"  AWDL discovery (full bidirectional with Apple devices):  {_format_yesno(can_awdl)}"
    )

    print()
    if report.awdl_compatibility == AWDLCompatibility.UNLIKELY:
        print(dedent("""\
            Recommended next step:
              Plug in a compatible USB Wi-Fi adapter. Suggested models:
                - Alfa AWUS036NHA (Atheros AR9271)
                - TP-Link TL-WN722N v1 (Atheros AR9271)
                - Alfa AWUS036ACH (Realtek RTL8812AU)
        """))

    # Exit code: 0 = green, 1 = degraded (works but not for Apple), 2 = broken
    if report.awdl_compatibility == AWDLCompatibility.LIKELY:
        return 0
    if report.awdl_compatibility in (
        AWDLCompatibility.UNKNOWN,
        AWDLCompatibility.OWL_NOT_INSTALLED,
    ):
        return 1
    return 2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose OpenDrop hardware compatibility."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON report instead of human-readable text.",
    )
    args = parser.parse_args()
    sys.exit(run(json_output=args.json))


if __name__ == "__main__":
    main()
