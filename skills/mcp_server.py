"""
MCP Server for the skills package – Claude Code Integration.

Exposes the following tools via the Model Context Protocol (MCP):
- scan_lan     – Scan the local network for active devices
- wake_on_lan  – Send a Wake-on-LAN magic packet to a remote machine
- scan_ports   – Scan TCP ports on a host to discover open services
- ping_host    – Check host reachability and measure round-trip latency

Run as a standalone stdio MCP server:
    python -m skills mcp          # via the CLI
    skills-mcp                    # via the installed entry point
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from skills.network.scanner import scan_lan as _scan_lan
from skills.network.wol import wake_on_lan as _wake_on_lan
from skills.network.port_scanner import scan_ports as _scan_ports
from skills.network.ping import ping_host as _ping_host

mcp = FastMCP(
    name="skills",
    instructions=(
        "Skills toolkit: scan the local network for devices, send "
        "Wake-on-LAN magic packets to wake remote machines, scan TCP ports "
        "on a host to discover open services, and ping hosts to measure "
        "round-trip latency."
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


@mcp.tool()
def scan_ports(
    host: str,
    ports: Optional[list[int]] = None,
    timeout: float = 1.0,
) -> list[dict]:
    """Scan TCP ports on a host to discover open services.

    Args:
        host: IP address or hostname to scan (e.g. "192.168.1.1").
        ports: List of port numbers to check.  When omitted, a curated set of
               18 common service ports is used (SSH, HTTP, HTTPS, MySQL, …).
        timeout: Per-port connection timeout in seconds (default: 1.0).

    Returns:
        A list of dicts for open ports, sorted by port number.  Each dict:
        - port    (int) – port number
        - service (str) – service name (empty string if unknown)
        - state   (str) – always "open"
    """
    return _scan_ports(host=host, ports=ports, timeout=timeout)


@mcp.tool()
def ping_host(
    host: str,
    count: int = 4,
    timeout: float = 2.0,
) -> dict:
    """Ping a host and measure round-trip latency.

    Args:
        host: IP address or hostname to ping (e.g. "192.168.1.1" or "8.8.8.8").
        count: Number of ICMP packets to send (default: 4).
        timeout: Per-packet wait timeout in seconds (default: 2.0).

    Returns:
        A dict with keys:
        - host             (str)        – target host
        - reachable        (bool)       – True if at least one reply received
        - sent             (int)        – packets transmitted
        - received         (int)        – packets received
        - packet_loss_pct  (float)      – percentage of lost packets
        - rtt_min_ms       (float|None) – minimum RTT in milliseconds
        - rtt_avg_ms       (float|None) – average RTT in milliseconds
        - rtt_max_ms       (float|None) – maximum RTT in milliseconds
        - error            (str|None)   – error message on failure, None on success
    """
    return _ping_host(host=host, count=count, timeout=timeout)


def main() -> None:
    """Entry point for the ``skills-mcp`` command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
