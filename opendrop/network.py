"""
OpenDrop network utilities.

Centralized helpers for:
- Local interface enumeration and IP address detection
- Self-identification (so we can filter out our own mDNS announcements)
- Interface selection heuristics (which interface to use when none specified)

This module exists so the rest of the codebase has a single, well-tested place
to ask "what are my local IPs?" and "is this address mine?".
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import List, Optional, Set, Tuple

import ifaddr

logger = logging.getLogger(__name__)


def list_interfaces() -> List[Tuple[str, List[str]]]:
    """
    Enumerate all network interfaces with their IP addresses.

    Returns:
        List of (interface_name, [ip_address_strings]).
        IPv6 addresses are returned without zone IDs.
    """
    out: List[Tuple[str, List[str]]] = []
    for adapter in ifaddr.get_adapters():
        ips: List[str] = []
        for ip in adapter.ips:
            if ip.is_IPv4:
                ips.append(str(ip.ip))
            elif ip.is_IPv6:
                # ip.ip is (addr, flowinfo, scope_id) for IPv6
                addr = ip.ip[0] if isinstance(ip.ip, tuple) else str(ip.ip)
                ips.append(str(addr))
        out.append((adapter.name, ips))
    return out


def local_ipv6_addresses() -> Set[str]:
    """
    All IPv6 addresses currently configured on this host, stripped of zone IDs.

    Useful for detecting "is this remote address actually me?" when filtering
    out our own mDNS service announcements.

    Returns:
        Set of IPv6 address strings.
    """
    out: Set[str] = set()
    for _, ips in list_interfaces():
        for ip_str in ips:
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if isinstance(addr, ipaddress.IPv6Address):
                out.add(str(addr))
    return out


def local_ipv4_addresses() -> Set[str]:
    """
    All IPv4 addresses currently configured on this host.

    Returns:
        Set of IPv4 address strings.
    """
    out: Set[str] = set()
    for _, ips in list_interfaces():
        for ip_str in ips:
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if isinstance(addr, ipaddress.IPv4Address):
                out.add(str(addr))
    return out


def is_local_address(addr: str) -> bool:
    """
    Check whether the given address belongs to one of this host's interfaces.

    Strips IPv6 zone IDs ("fe80::1%wlo1") before comparison.

    Args:
        addr: An IPv4 or IPv6 address string.

    Returns:
        True if the address is configured on this host.
    """
    if not addr:
        return False
    # Strip IPv6 zone ID if present
    if "%" in addr:
        addr = addr.split("%", 1)[0]
    try:
        normalized = str(ipaddress.ip_address(addr))
    except ValueError:
        return False
    return normalized in local_ipv6_addresses() or normalized in local_ipv4_addresses()


def find_interface_with_ipv6() -> Optional[str]:
    """
    Find a usable interface for AirDrop, preferring AWDL when available.

    Preference order:
    1. awdl0 if it has an IPv6 address (OWL is running)
    2. The interface backing the host's default route, if it has IPv6
    3. The first non-loopback interface with an IPv6 address

    Returns:
        Interface name or None if no interface with IPv6 exists.
    """
    interfaces = list_interfaces()

    # 1. Prefer awdl0 if up
    for name, ips in interfaces:
        if name == "awdl0":
            for ip_str in ips:
                try:
                    if isinstance(ipaddress.ip_address(ip_str), ipaddress.IPv6Address):
                        return name
                except ValueError:
                    continue

    # 2. Try default-route interface
    default_iface = _default_route_interface()
    if default_iface is not None:
        for name, ips in interfaces:
            if name != default_iface:
                continue
            for ip_str in ips:
                try:
                    if isinstance(ipaddress.ip_address(ip_str), ipaddress.IPv6Address):
                        return name
                except ValueError:
                    continue

    # 3. First non-loopback interface with IPv6
    for name, ips in interfaces:
        if name.startswith("lo"):
            continue
        for ip_str in ips:
            try:
                if isinstance(ipaddress.ip_address(ip_str), ipaddress.IPv6Address):
                    return name
            except ValueError:
                continue

    return None


def _default_route_interface() -> Optional[str]:
    """
    Detect which interface carries the default route.

    Uses a UDP connect trick that doesn't actually send a packet — it just makes
    the kernel pick a source address based on the routing table.

    Returns:
        Interface name backing the default route, or None.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Connect to a public IP; no packet is actually sent for SOCK_DGRAM
            # but the kernel picks a source address.
            s.connect(("8.8.8.8", 53))
            local_ip = s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None

    # Map IP back to interface name
    for adapter in ifaddr.get_adapters():
        for ip in adapter.ips:
            if ip.is_IPv4 and str(ip.ip) == local_ip:
                return adapter.name

    return None
