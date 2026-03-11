"""
LAN Device Scanner - 局域网设备扫描器

Discovers devices on the local network using ARP requests.
Supports both scapy-based ARP scanning (more accurate) and
a fallback method that reads the system ARP cache after a ping sweep.
"""

from __future__ import annotations

import ipaddress
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

_SCAPY_AVAILABLE = False
try:
    from scapy.all import ARP, Ether, srp  # type: ignore

    _SCAPY_AVAILABLE = True
except ImportError:
    pass

_NMAP_AVAILABLE = False
try:
    import nmap as _nmap  # type: ignore

    _nmap.PortScanner()  # raises PortScannerError if nmap binary is not installed
    _NMAP_AVAILABLE = True
except ImportError:
    pass  # python-nmap library not installed
except Exception:
    pass  # nmap binary not found or other initialisation error


@dataclass
class Device:
    """Represents a device found on the local network."""

    ip: str
    mac: str = ""
    hostname: str = ""
    extra: dict = field(default_factory=dict)

    def __str__(self) -> str:
        parts = [f"IP: {self.ip}"]
        if self.mac:
            parts.append(f"MAC: {self.mac}")
        if self.hostname:
            parts.append(f"Hostname: {self.hostname}")
        return "  ".join(parts)


def get_local_subnet() -> str:
    """
    Detect the local machine's primary subnet in CIDR notation.

    Returns:
        A CIDR string such as ``"192.168.1.0/24"``.

    Raises:
        RuntimeError: If the subnet cannot be determined.
    """
    try:
        # Connect to a public address to discover the local interface IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
        return str(network)
    except OSError as exc:
        raise RuntimeError("Cannot determine local subnet") from exc


def _resolve_hostname(ip: str) -> str:
    """Attempt a reverse DNS lookup; return empty string on failure."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror, socket.timeout, OSError):
        return ""


def _scan_with_scapy(subnet: str, timeout: float = 2.0) -> list[Device]:
    """
    Perform an ARP sweep using scapy (requires root/admin privileges).

    Args:
        subnet: Network to scan in CIDR notation (e.g. ``"192.168.1.0/24"``).
        timeout: Time in seconds to wait for ARP replies.

    Returns:
        List of :class:`Device` objects found on the network.
    """
    packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet)
    answered, _ = srp(packet, timeout=timeout, verbose=False)
    devices: list[Device] = []
    for sent, received in answered:
        ip = received.psrc
        mac = received.hwsrc
        hostname = _resolve_hostname(ip)
        devices.append(Device(ip=ip, mac=mac, hostname=hostname))
    return devices


def _scan_with_nmap(subnet: str, timeout: float = 2.0) -> list[Device]:
    """
    Scan a subnet using nmap (requires the ``nmap`` binary on the system).

    nmap discovers hosts via ARP/ICMP probes and resolves hostnames through
    multiple methods (reverse DNS, mDNS/Bonjour, NetBIOS) – far more
    reliable than a plain ``gethostbyaddr`` call.

    Args:
        subnet: Network to scan in CIDR notation (e.g. ``"192.168.1.0/24"``).
        timeout: Host-discovery timeout in seconds passed to nmap.

    Returns:
        List of :class:`Device` objects found on the network.
    """
    import nmap as _nmap  # type: ignore  # noqa: PLC0415

    nm = _nmap.PortScanner()
    # -sn  = ping/ARP scan (no port scan)
    # -R   = always resolve hostnames
    # --host-timeout = per-host timeout in milliseconds
    host_timeout_ms = int(timeout * 1000)
    nm.scan(
        hosts=subnet,
        arguments=f"-sn -R --host-timeout {host_timeout_ms}ms",
    )
    devices: list[Device] = []
    for ip in nm.all_hosts():
        host = nm[ip]
        mac = host["addresses"].get("mac", "")
        # nmap can return multiple hostnames; prefer the first PTR name
        hostnames = host.get("hostnames", [])
        hostname = hostnames[0]["name"] if hostnames else ""
        devices.append(Device(ip=ip, mac=mac, hostname=hostname))
    return devices


def _ping_host(ip: str) -> bool:
    """Send a single ICMP ping and return True if the host responds."""
    flag = "-n" if sys.platform == "win32" else "-c"
    result = subprocess.run(
        ["ping", flag, "1", "-W", "1", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=3,
    )
    return result.returncode == 0


def _read_arp_cache() -> dict[str, str]:
    """
    Read the system ARP cache and return a mapping of ``ip -> mac``.

    Works on Linux (``/proc/net/arp``) and falls back to parsing
    ``arp -a`` output on other platforms.
    """
    ip_mac: dict[str, str] = {}

    # Linux fast path: read /proc/net/arp
    try:
        with open("/proc/net/arp", encoding="utf-8") as f:
            for line in f.readlines()[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 4 and parts[2] != "0x0":
                    ip_mac[parts[0]] = parts[3]
        return ip_mac
    except FileNotFoundError:
        pass

    # Cross-platform fallback: parse `arp -a`
    try:
        output = subprocess.check_output(
            ["arp", "-a"], stderr=subprocess.DEVNULL, text=True
        )
        for line in output.splitlines():
            # Typical output: "hostname (192.168.1.1) at aa:bb:cc:dd:ee:ff ..."
            parts = line.split()
            if len(parts) >= 4:
                ip = parts[1].strip("()")
                mac_candidate = parts[3]
                if ":" in mac_candidate or "-" in mac_candidate:
                    ip_mac[ip] = mac_candidate.replace("-", ":")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return ip_mac


def _scan_with_ping(
    subnet: str,
    max_workers: int = 50,
) -> list[Device]:
    """
    Scan a subnet by pinging all hosts then reading the ARP cache.

    This method does **not** require elevated privileges but is slower
    and less reliable than the scapy-based approach.

    Args:
        subnet: Network to scan in CIDR notation (e.g. ``"192.168.1.0/24"``).
        max_workers: Maximum number of concurrent ping threads.

    Returns:
        List of :class:`Device` objects found on the network.
    """
    network = ipaddress.IPv4Network(subnet, strict=False)
    hosts = [str(h) for h in network.hosts()]

    # Ping all hosts concurrently to populate the ARP cache
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_ping_host, ip): ip for ip in hosts}
        for future in as_completed(futures):
            future.result()  # we only care about side effects (ARP cache)

    arp_cache = _read_arp_cache()
    devices: list[Device] = []
    for ip in hosts:
        if ip in arp_cache:
            hostname = _resolve_hostname(ip)
            devices.append(Device(ip=ip, mac=arp_cache[ip], hostname=hostname))
    return devices


def scan_lan(
    subnet: Optional[str] = None,
    timeout: float = 2.0,
    max_workers: int = 50,
) -> list[Device]:
    """
    Scan the local area network for active devices.

    Automatically selects the best available scanning strategy:

    * **nmap scan** – most accurate; resolves hostnames via DNS, mDNS, and
      NetBIOS; requires the ``nmap`` binary (install as *OpenClaw*: see README).
    * **scapy ARP sweep** – accurate and fast; requires root/admin.
    * **ping sweep + ARP cache** – no elevated privileges needed; slower.

    Args:
        subnet: CIDR subnet to scan (e.g. ``"192.168.1.0/24"``).
                Defaults to the local machine's ``/24`` subnet.
        timeout: Seconds to wait for ARP replies / host discovery.
        max_workers: Concurrent ping threads (ping-fallback mode only).

    Returns:
        List of :class:`Device` objects sorted by IP address.

    Example::

        from skills.network import scan_lan

        for device in scan_lan():
            print(device)
    """
    if subnet is None:
        subnet = get_local_subnet()

    if _NMAP_AVAILABLE:
        devices = _scan_with_nmap(subnet, timeout=timeout)
    elif _SCAPY_AVAILABLE:
        devices = _scan_with_scapy(subnet, timeout=timeout)
    else:
        devices = _scan_with_ping(subnet, max_workers=max_workers)

    # Sort by IP address numerically
    devices.sort(key=lambda d: ipaddress.IPv4Address(d.ip))
    return devices
