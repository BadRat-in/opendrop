"""
Tests for opendrop.ble — Apple AirDrop BLE beacon parsing and building.

These tests exercise the parser/builder logic. The actual scanner/advertiser
classes are integration-level and exercised manually (they need a real BLE
adapter on the host).
"""

import pytest

from opendrop.ble import (
    AIRDROP_PAYLOAD_LEN,
    AIRDROP_TYPE,
    APPLE_COMPANY_ID,
    AppleBLEDevice,
    build_airdrop_beacon,
    parse_airdrop_beacon,
    random_airdrop_beacon,
)


def test_build_returns_18_bytes():
    """An AirDrop beacon payload is always 18 bytes by spec."""
    beacon = build_airdrop_beacon()
    assert len(beacon) == 18


def test_build_starts_with_type_and_length():
    beacon = build_airdrop_beacon()
    assert beacon[0] == AIRDROP_TYPE
    assert beacon[1] == AIRDROP_PAYLOAD_LEN


def test_build_zeroes_padding():
    beacon = build_airdrop_beacon()
    assert beacon[2:10] == b"\x00" * 8


def test_build_default_hashes_zero():
    beacon = build_airdrop_beacon()
    assert beacon[10:18] == b"\x00" * 8


def test_build_with_custom_hashes():
    beacon = build_airdrop_beacon(
        apple_id_hash=b"\xaa\xbb",
        phone_hash=b"\xcc\xdd",
        email_hash=b"\xee\xff",
        email2_hash=b"\x11\x22",
    )
    assert beacon[10:12] == b"\xaa\xbb"
    assert beacon[12:14] == b"\xcc\xdd"
    assert beacon[14:16] == b"\xee\xff"
    assert beacon[16:18] == b"\x11\x22"


def test_build_pads_short_hash():
    """A 1-byte hash should be padded with zeros."""
    beacon = build_airdrop_beacon(apple_id_hash=b"\xaa")
    assert beacon[10:12] == b"\xaa\x00"


def test_build_truncates_long_hash():
    """A 4-byte hash should be truncated to 2 bytes."""
    beacon = build_airdrop_beacon(apple_id_hash=b"\xaa\xbb\xcc\xdd")
    assert beacon[10:12] == b"\xaa\xbb"


def test_parse_round_trip():
    """A built beacon should parse back to the same hashes."""
    built = build_airdrop_beacon(
        apple_id_hash=b"\x12\x34",
        phone_hash=b"\x56\x78",
        email_hash=b"\x9a\xbc",
        email2_hash=b"\xde\xf0",
    )
    parsed = parse_airdrop_beacon(built)
    assert parsed is not None
    assert parsed["apple_id_hash"] == b"\x12\x34"
    assert parsed["phone_hash"] == b"\x56\x78"
    assert parsed["email_hash"] == b"\x9a\xbc"
    assert parsed["email2_hash"] == b"\xde\xf0"


def test_parse_rejects_non_airdrop_type():
    """Apple advertises lots of types; only 0x05 is AirDrop."""
    # Type 0x0c is "Handoff", for example.
    not_airdrop = bytes([0x0C, 0x10]) + b"\x00" * 16
    assert parse_airdrop_beacon(not_airdrop) is None


def test_parse_rejects_short_payload():
    """Empty or 1-byte payload is not a beacon."""
    assert parse_airdrop_beacon(b"") is None
    assert parse_airdrop_beacon(b"\x05") is None


def test_parse_tolerates_short_but_typed_payload():
    """A truncated AirDrop beacon should zero-pad rather than crash."""
    short = bytes([AIRDROP_TYPE, 0x12]) + b"\x00" * 5  # only 7 bytes
    parsed = parse_airdrop_beacon(short)
    assert parsed is not None
    assert parsed["apple_id_hash"] == b"\x00\x00"


def test_random_beacon_is_18_bytes_and_starts_correctly():
    beacon = random_airdrop_beacon()
    assert len(beacon) == 18
    assert beacon[0] == AIRDROP_TYPE
    assert beacon[1] == AIRDROP_PAYLOAD_LEN
    # Zero pad still zero
    assert beacon[2:10] == b"\x00" * 8


def test_random_beacon_has_random_hashes():
    """Two random beacons should differ in their hash fields."""
    a = random_airdrop_beacon()
    b = random_airdrop_beacon()
    # Vanishing probability they collide.
    assert a[10:18] != b[10:18]


def test_apple_company_id_is_correct():
    """0x004C is Apple's Bluetooth SIG company ID."""
    assert APPLE_COMPANY_ID == 0x004C


def test_apple_ble_device_short_id():
    """short_id should be a lower-hex stripped of colons."""
    dev = AppleBLEDevice(address="AA:BB:CC:DD:EE:FF", rssi=-50)
    assert dev.short_id == "aabbccddeeff"
