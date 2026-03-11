"""
Port Scanner - 端口扫描器

Scans TCP ports on a host to discover running services.
Uses concurrent socket connections for fast scanning.
"""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# Well-known service names for common ports
_COMMON_SERVICES: dict[int, str] = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "dns",
    80: "http",
    110: "pop3",
    143: "imap",
    443: "https",
    445: "smb",
    3306: "mysql",
    3389: "rdp",
    5432: "postgresql",
    5900: "vnc",
    6379: "redis",
    8080: "http-alt",
    8443: "https-alt",
    27017: "mongodb",
}

# Default ports to scan when none are specified
DEFAULT_PORTS: list[int] = sorted(_COMMON_SERVICES.keys())


def _check_port(host: str, port: int, timeout: float) -> bool:
    """Return True if *port* is open on *host*."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_service_name(port: int) -> str:
    """
    Return the well-known service name for *port*.

    First checks the built-in :data:`_COMMON_SERVICES` mapping, then falls
    back to ``socket.getservbyport``.  Returns an empty string if unknown.

    Args:
        port: TCP port number.

    Returns:
        Service name string, e.g. ``"http"``, or ``""`` if not recognised.
    """
    if port in _COMMON_SERVICES:
        return _COMMON_SERVICES[port]
    try:
        return socket.getservbyport(port, "tcp")
    except OSError:
        return ""


def scan_ports(
    host: str,
    ports: Optional[list[int]] = None,
    timeout: float = 1.0,
    max_workers: int = 100,
) -> list[dict]:
    """
    Scan TCP ports on a host and return the open ones.

    Args:
        host: IP address or hostname to scan.
        ports: List of port numbers to scan.  Defaults to
               :data:`DEFAULT_PORTS` (a curated set of 18 common service
               ports).
        timeout: Per-port connection timeout in seconds (default: ``1.0``).
        max_workers: Maximum number of concurrent connection attempts
                     (default: ``100``).

    Returns:
        List of dicts for **open** ports, sorted by port number.  Each dict
        contains:

        * ``"port"`` (:class:`int`) – port number
        * ``"service"`` (:class:`str`) – service name (empty string if unknown)
        * ``"state"`` (:class:`str`) – always ``"open"``

    Example::

        from skills.network import scan_ports

        for r in scan_ports("192.168.1.1"):
            print(f"{r['port']}/{r['service']}: {r['state']}")
    """
    if ports is None:
        ports = DEFAULT_PORTS

    if not ports:
        return []

    open_ports: list[dict] = []
    workers = min(max_workers, len(ports))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_port = {
            executor.submit(_check_port, host, port, timeout): port
            for port in ports
        }
        for future in as_completed(future_to_port):
            port = future_to_port[future]
            try:
                is_open = future.result()
            except Exception:
                is_open = False
            if is_open:
                open_ports.append(
                    {
                        "port": port,
                        "service": get_service_name(port),
                        "state": "open",
                    }
                )

    open_ports.sort(key=lambda r: r["port"])
    return open_ports
