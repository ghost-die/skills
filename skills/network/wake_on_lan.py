"""
Wake-on-LAN (WOL) - 网络唤醒

Sends a WOL magic packet to wake a remote machine from sleep or powered-off
state.  The target machine's network card must have WOL enabled in its
firmware/BIOS settings.

Magic packet format (RFC-style):
    6 bytes of 0xFF  followed by  16 repetitions of the target MAC address
    Transmitted as a UDP broadcast on port 9 (or port 7).
"""

from __future__ import annotations

import re
import socket
import struct
from typing import Optional


# Matches common MAC address formats:
#   aa:bb:cc:dd:ee:ff  (colon-separated)
#   aa-bb-cc-dd-ee-ff  (hyphen-separated)
#   aabbccddeeff       (no separator)
_MAC_RE = re.compile(
    r"^([0-9a-fA-F]{2})[:\-]?"
    r"([0-9a-fA-F]{2})[:\-]?"
    r"([0-9a-fA-F]{2})[:\-]?"
    r"([0-9a-fA-F]{2})[:\-]?"
    r"([0-9a-fA-F]{2})[:\-]?"
    r"([0-9a-fA-F]{2})$"
)


def _normalise_mac(mac: str) -> str:
    """
    Validate and normalise a MAC address to ``"aa:bb:cc:dd:ee:ff"`` form.

    Args:
        mac: MAC address in any common format.

    Returns:
        Normalised lower-case colon-separated MAC string.

    Raises:
        ValueError: If *mac* is not a valid 48-bit address.
    """
    mac = mac.strip()
    match = _MAC_RE.match(mac)
    if not match:
        raise ValueError(
            f"Invalid MAC address: {mac!r}. "
            "Expected format: aa:bb:cc:dd:ee:ff or aabbccddeeff."
        )
    return ":".join(g.lower() for g in match.groups())


def build_magic_packet(mac: str) -> bytes:
    """
    Build a WOL magic packet for the given MAC address.

    The magic packet consists of:
    * A synchronisation stream: 6 bytes of ``0xFF``
    * The target MAC address repeated 16 times (96 bytes total)

    Args:
        mac: Target MAC address (any common format).

    Returns:
        102-byte :class:`bytes` magic packet.

    Raises:
        ValueError: If *mac* is invalid.

    Example::

        packet = build_magic_packet("aa:bb:cc:dd:ee:ff")
        assert len(packet) == 102
    """
    mac_norm = _normalise_mac(mac)
    mac_bytes = bytes.fromhex(mac_norm.replace(":", ""))
    return b"\xff" * 6 + mac_bytes * 16


def send_magic_packet(
    mac: str,
    broadcast: str = "255.255.255.255",
    port: int = 9,
) -> None:
    """
    Send a Wake-on-LAN magic packet.

    Args:
        mac: MAC address of the target machine.
        broadcast: Broadcast address to use.  Defaults to the global
                   broadcast ``"255.255.255.255"``.  Use a subnet-directed
                   broadcast (e.g. ``"192.168.1.255"``) for better
                   reliability across some routers.
        port: UDP destination port.  Port ``9`` (discard) is standard;
              port ``7`` (echo) is also commonly used.

    Raises:
        ValueError: If *mac* is invalid.
        OSError: If the UDP socket cannot be created or bound.

    Example::

        from skills.network import send_magic_packet

        send_magic_packet("aa:bb:cc:dd:ee:ff")
    """
    packet = build_magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.connect((broadcast, port))
        sock.send(packet)


def wake_on_lan(
    mac: str,
    broadcast: Optional[str] = None,
    port: int = 9,
) -> dict:
    """
    High-level Wake-on-LAN helper that sends a magic packet and returns
    a result summary dictionary.

    Args:
        mac: MAC address of the target machine.
        broadcast: Broadcast address.  Auto-detected (``"255.255.255.255"``)
                   when ``None``.
        port: UDP destination port (default ``9``).

    Returns:
        A dict with keys:

        * ``"success"`` (:class:`bool`) – whether the packet was sent.
        * ``"mac"`` (:class:`str`) – normalised MAC address.
        * ``"broadcast"`` (:class:`str`) – broadcast address used.
        * ``"port"`` (:class:`int`) – UDP port used.
        * ``"error"`` (:class:`str` or ``None``) – error message on failure.

    Example::

        from skills.network import wake_on_lan

        result = wake_on_lan("aa:bb:cc:dd:ee:ff", broadcast="192.168.1.255")
        if result["success"]:
            print("Magic packet sent to", result["mac"])
        else:
            print("Failed:", result["error"])
    """
    if broadcast is None:
        broadcast = "255.255.255.255"

    try:
        mac_norm = _normalise_mac(mac)
        send_magic_packet(mac_norm, broadcast=broadcast, port=port)
        return {
            "success": True,
            "mac": mac_norm,
            "broadcast": broadcast,
            "port": port,
            "error": None,
        }
    except (ValueError, OSError) as exc:
        return {
            "success": False,
            "mac": mac,
            "broadcast": broadcast,
            "port": port,
            "error": str(exc),
        }
