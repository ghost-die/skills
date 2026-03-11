"""
Tests for skills.network.ping
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from skills.network.ping import (
    _error_result,
    _parse_packet_stats,
    _parse_rtt_stats,
    ping_host,
)


# ---------------------------------------------------------------------------
# Sample ping outputs
# ---------------------------------------------------------------------------

LINUX_PING_OUTPUT_SUCCESS = """\
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.1 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=11.8 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=118 time=12.5 ms
64 bytes from 8.8.8.8: icmp_seq=4 ttl=118 time=11.9 ms

--- 8.8.8.8 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3003ms
rtt min/avg/max/mdev = 11.800/12.075/12.500/0.265 ms
"""

LINUX_PING_OUTPUT_PARTIAL_LOSS = """\
PING 10.0.0.1 (10.0.0.1) 56(84) bytes of data.
64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=1.5 ms
64 bytes from 10.0.0.1: icmp_seq=3 ttl=64 time=1.7 ms

--- 10.0.0.1 ping statistics ---
4 packets transmitted, 2 received, 50% packet loss, time 3000ms
rtt min/avg/max/mdev = 1.500/1.600/1.700/0.100 ms
"""

LINUX_PING_OUTPUT_NO_REPLY = """\
PING 192.168.1.254 (192.168.1.254) 56(84) bytes of data.

--- 192.168.1.254 ping statistics ---
4 packets transmitted, 0 received, 100% packet loss, time 3000ms
"""

WINDOWS_PING_OUTPUT_SUCCESS = """\
Pinging 8.8.8.8 with 32 bytes of data:
Reply from 8.8.8.8: bytes=32 time=13ms TTL=118
Reply from 8.8.8.8: bytes=32 time=12ms TTL=118
Reply from 8.8.8.8: bytes=32 time=14ms TTL=118
Reply from 8.8.8.8: bytes=32 time=13ms TTL=118

Ping statistics for 8.8.8.8:
    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 12ms, Maximum = 14ms, Average = 13ms
"""

WINDOWS_PING_OUTPUT_NO_REPLY = """\
Pinging 192.168.1.254 with 32 bytes of data:
Request timed out.
Request timed out.
Request timed out.
Request timed out.

Ping statistics for 192.168.1.254:
    Packets: Sent = 4, Received = 0, Lost = 4 (100% loss),
"""


# ---------------------------------------------------------------------------
# _parse_packet_stats
# ---------------------------------------------------------------------------


class TestParsePacketStats:
    def test_linux_full_success(self):
        sent, received, loss = _parse_packet_stats(LINUX_PING_OUTPUT_SUCCESS, 4)
        assert sent == 4
        assert received == 4
        assert loss == 0.0

    def test_linux_partial_loss(self):
        sent, received, loss = _parse_packet_stats(LINUX_PING_OUTPUT_PARTIAL_LOSS, 4)
        assert sent == 4
        assert received == 2
        assert loss == 50.0

    def test_linux_no_reply(self):
        sent, received, loss = _parse_packet_stats(LINUX_PING_OUTPUT_NO_REPLY, 4)
        assert sent == 4
        assert received == 0
        assert loss == 100.0

    def test_windows_full_success(self):
        sent, received, loss = _parse_packet_stats(WINDOWS_PING_OUTPUT_SUCCESS, 4)
        assert sent == 4
        assert received == 4
        assert loss == 0.0

    def test_windows_no_reply(self):
        sent, received, loss = _parse_packet_stats(WINDOWS_PING_OUTPUT_NO_REPLY, 4)
        assert sent == 4
        assert received == 0
        assert loss == 100.0

    def test_unparseable_uses_defaults(self):
        sent, received, loss = _parse_packet_stats("garbage output", 4)
        assert sent == 4
        assert received == 0
        assert loss == 100.0


# ---------------------------------------------------------------------------
# _parse_rtt_stats
# ---------------------------------------------------------------------------


class TestParseRttStats:
    def test_linux_success(self):
        rtt_min, rtt_avg, rtt_max = _parse_rtt_stats(LINUX_PING_OUTPUT_SUCCESS)
        assert rtt_min == pytest.approx(11.8)
        assert rtt_avg == pytest.approx(12.075)
        assert rtt_max == pytest.approx(12.5)

    def test_linux_no_reply_returns_nones(self):
        rtt_min, rtt_avg, rtt_max = _parse_rtt_stats(LINUX_PING_OUTPUT_NO_REPLY)
        assert rtt_min is None
        assert rtt_avg is None
        assert rtt_max is None

    def test_windows_success(self):
        rtt_min, rtt_avg, rtt_max = _parse_rtt_stats(WINDOWS_PING_OUTPUT_SUCCESS)
        assert rtt_min == pytest.approx(12.0)
        assert rtt_avg == pytest.approx(13.0)
        assert rtt_max == pytest.approx(14.0)

    def test_unparseable_returns_nones(self):
        rtt_min, rtt_avg, rtt_max = _parse_rtt_stats("garbage")
        assert rtt_min is None
        assert rtt_avg is None
        assert rtt_max is None


# ---------------------------------------------------------------------------
# _error_result
# ---------------------------------------------------------------------------


class TestErrorResult:
    def test_structure(self):
        result = _error_result("myhost", 4, "test error")
        assert result["host"] == "myhost"
        assert result["reachable"] is False
        assert result["sent"] == 4
        assert result["received"] == 0
        assert result["packet_loss_pct"] == 100.0
        assert result["rtt_min_ms"] is None
        assert result["rtt_avg_ms"] is None
        assert result["rtt_max_ms"] is None
        assert result["error"] == "test error"


# ---------------------------------------------------------------------------
# ping_host (integration with subprocess mock)
# ---------------------------------------------------------------------------


class TestPingHost:
    def _make_completed_process(self, stdout, returncode=0):
        proc = subprocess.CompletedProcess(args=[], returncode=returncode)
        proc.stdout = stdout
        return proc

    def test_reachable_host_linux(self):
        with patch(
            "skills.network.ping.subprocess.run",
            return_value=self._make_completed_process(LINUX_PING_OUTPUT_SUCCESS),
        ):
            result = ping_host("8.8.8.8", count=4)

        assert result["host"] == "8.8.8.8"
        assert result["reachable"] is True
        assert result["sent"] == 4
        assert result["received"] == 4
        assert result["packet_loss_pct"] == 0.0
        assert result["rtt_avg_ms"] == pytest.approx(12.075)
        assert result["error"] is None

    def test_unreachable_host_linux(self):
        with patch(
            "skills.network.ping.subprocess.run",
            return_value=self._make_completed_process(LINUX_PING_OUTPUT_NO_REPLY, 1),
        ):
            result = ping_host("192.168.1.254", count=4)

        assert result["reachable"] is False
        assert result["received"] == 0
        assert result["packet_loss_pct"] == 100.0
        assert result["rtt_avg_ms"] is None

    def test_partial_loss_linux(self):
        with patch(
            "skills.network.ping.subprocess.run",
            return_value=self._make_completed_process(LINUX_PING_OUTPUT_PARTIAL_LOSS),
        ):
            result = ping_host("10.0.0.1", count=4)

        assert result["reachable"] is True
        assert result["received"] == 2
        assert result["packet_loss_pct"] == 50.0

    def test_reachable_host_windows(self):
        with patch("skills.network.ping.sys.platform", "win32"), patch(
            "skills.network.ping.subprocess.run",
            return_value=self._make_completed_process(WINDOWS_PING_OUTPUT_SUCCESS),
        ):
            result = ping_host("8.8.8.8", count=4)

        assert result["reachable"] is True
        assert result["rtt_min_ms"] == pytest.approx(12.0)
        assert result["rtt_max_ms"] == pytest.approx(14.0)

    def test_timeout_expired_returns_error(self):
        with patch(
            "skills.network.ping.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ping", timeout=10),
        ):
            result = ping_host("192.168.1.1", count=4)

        assert result["reachable"] is False
        assert result["error"] == "Command timed out"

    def test_ping_not_found_returns_error(self):
        with patch(
            "skills.network.ping.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = ping_host("192.168.1.1", count=4)

        assert result["reachable"] is False
        assert result["error"] == "ping command not found"

    def test_result_has_all_keys(self):
        with patch(
            "skills.network.ping.subprocess.run",
            return_value=self._make_completed_process(LINUX_PING_OUTPUT_SUCCESS),
        ):
            result = ping_host("8.8.8.8")

        for key in (
            "host",
            "reachable",
            "sent",
            "received",
            "packet_loss_pct",
            "rtt_min_ms",
            "rtt_avg_ms",
            "rtt_max_ms",
            "error",
        ):
            assert key in result, f"Missing key: {key}"
