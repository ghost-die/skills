"""
Ping / Latency Check - 网络延迟检测

Checks host reachability and measures round-trip latency using the system
``ping`` command.  Supports Linux, macOS, and Windows.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Optional


def ping_host(
    host: str,
    count: int = 4,
    timeout: float = 2.0,
) -> dict:
    """
    Ping a host and measure round-trip latency.

    Uses the system ``ping`` command for cross-platform compatibility.

    Args:
        host: IP address or hostname to ping.
        count: Number of ICMP packets to send (default: ``4``).
        timeout: Per-packet wait timeout in seconds (default: ``2.0``).

    Returns:
        A dict with keys:

        * ``"host"`` (:class:`str`) – target host
        * ``"reachable"`` (:class:`bool`) – ``True`` if at least one reply was
          received
        * ``"sent"`` (:class:`int`) – packets transmitted
        * ``"received"`` (:class:`int`) – packets received
        * ``"packet_loss_pct"`` (:class:`float`) – percentage of lost packets
        * ``"rtt_min_ms"`` (:class:`float` or ``None``) – minimum RTT in ms
        * ``"rtt_avg_ms"`` (:class:`float` or ``None``) – average RTT in ms
        * ``"rtt_max_ms"`` (:class:`float` or ``None``) – maximum RTT in ms
        * ``"error"`` (:class:`str` or ``None``) – error message on failure,
          ``None`` on success

    Example::

        from skills.network import ping_host

        result = ping_host("8.8.8.8")
        if result["reachable"]:
            print(f"RTT avg: {result['rtt_avg_ms']:.1f} ms")
        else:
            print("Host unreachable")
    """
    is_windows = sys.platform == "win32"

    if is_windows:
        timeout_ms = int(timeout * 1000)
        cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
    else:
        timeout_int = max(1, int(timeout))
        cmd = ["ping", "-c", str(count), "-W", str(timeout_int), host]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout * count + 10,
        )
        output = proc.stdout or ""
    except subprocess.TimeoutExpired:
        return _error_result(host, count, "Command timed out")
    except FileNotFoundError:
        return _error_result(host, count, "ping command not found")

    sent, received, loss_pct = _parse_packet_stats(output, count)
    rtt_min, rtt_avg, rtt_max = _parse_rtt_stats(output)

    return {
        "host": host,
        "reachable": received > 0,
        "sent": sent,
        "received": received,
        "packet_loss_pct": loss_pct,
        "rtt_min_ms": rtt_min,
        "rtt_avg_ms": rtt_avg,
        "rtt_max_ms": rtt_max,
        "error": None,
    }


def _error_result(host: str, count: int, message: str) -> dict:
    """Return a failure result dict."""
    return {
        "host": host,
        "reachable": False,
        "sent": count,
        "received": 0,
        "packet_loss_pct": 100.0,
        "rtt_min_ms": None,
        "rtt_avg_ms": None,
        "rtt_max_ms": None,
        "error": message,
    }


def _parse_packet_stats(output: str, default_count: int) -> tuple[int, int, float]:
    """
    Parse transmitted / received / loss percentage from ping output.

    Returns:
        ``(sent, received, loss_pct)`` tuple.
    """
    # Linux/macOS: "4 packets transmitted, 4 received, 0% packet loss"
    m = re.search(
        r"(\d+) packets? transmitted,\s*(\d+)(?:\s+packets?)? received",
        output,
        re.IGNORECASE,
    )
    if m:
        sent = int(m.group(1))
        received = int(m.group(2))
        loss_pct = ((sent - received) / sent * 100) if sent > 0 else 100.0
        return sent, received, round(loss_pct, 1)

    # Windows: "Packets: Sent = 4, Received = 3, Lost = 1 (25% loss)"
    m = re.search(
        r"Sent\s*=\s*(\d+),\s*Received\s*=\s*(\d+)",
        output,
        re.IGNORECASE,
    )
    if m:
        sent = int(m.group(1))
        received = int(m.group(2))
        loss_pct = ((sent - received) / sent * 100) if sent > 0 else 100.0
        return sent, received, round(loss_pct, 1)

    return default_count, 0, 100.0


def _parse_rtt_stats(
    output: str,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Parse min / avg / max RTT statistics from ping output.

    Returns:
        ``(rtt_min_ms, rtt_avg_ms, rtt_max_ms)`` in milliseconds, or
        ``(None, None, None)`` if statistics could not be parsed.
    """
    # Linux/macOS: "rtt min/avg/max/mdev = 0.123/0.456/0.789/0.100 ms"
    m = re.search(
        r"(?:rtt|round-trip)\s+min/avg/max[^\d]+([\d.]+)/([\d.]+)/([\d.]+)",
        output,
        re.IGNORECASE,
    )
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))

    # Windows: "Minimum = 12ms, Maximum = 15ms, Average = 13ms"
    m_min = re.search(r"Minimum\s*=\s*([\d.]+)\s*ms", output, re.IGNORECASE)
    m_max = re.search(r"Maximum\s*=\s*([\d.]+)\s*ms", output, re.IGNORECASE)
    m_avg = re.search(r"Average\s*=\s*([\d.]+)\s*ms", output, re.IGNORECASE)
    if m_min and m_max and m_avg:
        return (
            float(m_min.group(1)),
            float(m_avg.group(1)),
            float(m_max.group(1)),
        )

    return None, None, None
