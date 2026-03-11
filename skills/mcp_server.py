"""
MCP Server for the skills package – Claude Code Integration.

Exposes the following tools via the Model Context Protocol (MCP):
- scan_lan   – Scan the local network for active devices
- wake_on_lan – Send a Wake-on-LAN magic packet to a remote machine

Run as a standalone stdio MCP server:
    python -m skills mcp          # via the CLI
    skills-mcp                    # via the installed entry point
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from skills.network.scanner import scan_lan as _scan_lan
from skills.network.wol import wake_on_lan as _wake_on_lan

mcp = FastMCP(
    name="skills",
    instructions=(
        "Skills toolkit: scan the local network for devices and send "
        "Wake-on-LAN magic packets to wake remote machines."
    ),
)


@mcp.tool()
def scan_lan(
    subnet: Optional[str] = None,
    timeout: float = 2.0,
) -> list[dict]:
    """Scan the local area network for active devices.

    Args:
        subnet: CIDR subnet to scan (e.g. "192.168.1.0/24").
                When omitted, the local machine's /24 subnet is used.
        timeout: Seconds to wait for ARP replies (default: 2.0).

    Returns:
        A list of dicts, each containing:
        - ip       (str)  – IP address of the device
        - mac      (str)  – MAC address (empty string if unknown)
        - hostname (str)  – Resolved hostname (empty string if unknown)
    """
    devices = _scan_lan(subnet=subnet, timeout=timeout)
    return [
        {"ip": d.ip, "mac": d.mac, "hostname": d.hostname}
        for d in devices
    ]


@mcp.tool()
def wake_on_lan(
    mac: str,
    broadcast: str = "255.255.255.255",
    port: int = 9,
) -> dict:
    """Send a Wake-on-LAN magic packet to wake a remote machine.

    The target machine must have Wake-on-LAN enabled in its firmware/BIOS.

    Args:
        mac: MAC address of the target machine (e.g. "aa:bb:cc:dd:ee:ff").
             Accepts colon-separated, hyphen-separated, or plain hex formats.
        broadcast: Broadcast address (default: "255.255.255.255").
                   Use a subnet-directed address (e.g. "192.168.1.255") for
                   better reliability across some routers.
        port: UDP destination port (default: 9).

    Returns:
        A dict with keys:
        - success   (bool) – True if the magic packet was sent successfully
        - mac       (str)  – Normalised MAC address
        - broadcast (str)  – Broadcast address used
        - port      (int)  – UDP port used
        - error     (str | None) – Error message on failure, None on success
    """
    return _wake_on_lan(mac=mac, broadcast=broadcast, port=port)


def main() -> None:
    """Entry point for the ``skills-mcp`` command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
