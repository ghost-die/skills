"""
Tests for skills.network.scanner
"""

from __future__ import annotations

import ipaddress
import sys
from unittest.mock import MagicMock, patch

import pytest

from skills.network.scanner import (
    Device,
    _read_arp_cache,
    _resolve_hostname,
    get_local_subnet,
    scan_lan,
)


class TestDevice:
    def test_str_full(self):
        d = Device(ip="192.168.1.1", mac="aa:bb:cc:dd:ee:ff", hostname="router")
        text = str(d)
        assert "192.168.1.1" in text
        assert "aa:bb:cc:dd:ee:ff" in text
        assert "router" in text

    def test_str_no_mac_no_hostname(self):
        d = Device(ip="10.0.0.1")
        assert "10.0.0.1" in str(d)

    def test_extra_field_defaults_to_empty_dict(self):
        d = Device(ip="1.2.3.4")
        assert d.extra == {}


class TestGetLocalSubnet:
    def test_returns_cidr_string(self):
        subnet = get_local_subnet()
        # Must be a valid network
        net = ipaddress.IPv4Network(subnet, strict=False)
        assert net.prefixlen == 24

    def test_raises_on_socket_error(self):
        with patch("skills.network.scanner.socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock.__exit__ = MagicMock(return_value=False)
            mock_sock.connect.side_effect = OSError("no network")
            mock_sock_cls.return_value = mock_sock

            with pytest.raises(RuntimeError):
                get_local_subnet()


class TestResolveHostname:
    def test_returns_string_on_success(self):
        with patch("skills.network.scanner.socket.gethostbyaddr") as mock:
            mock.return_value = ("myhost", [], ["192.168.1.5"])
            assert _resolve_hostname("192.168.1.5") == "myhost"

    def test_returns_empty_on_failure(self):
        import socket as _socket
        with patch("skills.network.scanner.socket.gethostbyaddr") as mock:
            mock.side_effect = _socket.herror()
            assert _resolve_hostname("192.168.1.99") == ""


class TestReadArpCache:
    def test_reads_proc_net_arp(self):
        arp_content = (
            "IP address       HW type     Flags       HW address            Mask     Device\n"
            "192.168.1.1      0x1         0x2         aa:bb:cc:dd:ee:ff     *        eth0\n"
            "192.168.1.5      0x1         0x2         11:22:33:44:55:66     *        eth0\n"
            "192.168.1.9      0x1         0x0         00:00:00:00:00:00     *        eth0\n"
        )
        from unittest.mock import mock_open
        m = mock_open(read_data=arp_content)
        with patch("builtins.open", m):
            cache = _read_arp_cache()
        assert cache.get("192.168.1.1") == "aa:bb:cc:dd:ee:ff"
        assert cache.get("192.168.1.5") == "11:22:33:44:55:66"
        # Incomplete/0x0 entry should be skipped
        assert "192.168.1.9" not in cache


class TestScanLan:
    def test_scan_returns_devices_sorted_by_ip(self):
        fake_devices = [
            Device(ip="192.168.1.10", mac="cc:cc:cc:cc:cc:cc"),
            Device(ip="192.168.1.2", mac="aa:aa:aa:aa:aa:aa"),
            Device(ip="192.168.1.5", mac="bb:bb:bb:bb:bb:bb"),
        ]
        with patch("skills.network.scanner._SCAPY_AVAILABLE", False), \
             patch("skills.network.scanner._scan_with_ping", return_value=fake_devices):
            result = scan_lan(subnet="192.168.1.0/24")

        ips = [d.ip for d in result]
        assert ips == sorted(ips, key=ipaddress.IPv4Address)

    def test_scan_uses_scapy_when_available(self):
        fake_devices = [Device(ip="10.0.0.1", mac="de:ad:be:ef:00:01")]
        with patch("skills.network.scanner._SCAPY_AVAILABLE", True), \
             patch("skills.network.scanner._scan_with_scapy", return_value=fake_devices) as mock_scapy, \
             patch("skills.network.scanner._scan_with_ping") as mock_ping:
            result = scan_lan(subnet="10.0.0.0/24")

        mock_scapy.assert_called_once()
        mock_ping.assert_not_called()
        assert len(result) == 1

    def test_scan_auto_detects_subnet(self):
        with patch("skills.network.scanner.get_local_subnet", return_value="172.16.0.0/24"), \
             patch("skills.network.scanner._SCAPY_AVAILABLE", False), \
             patch("skills.network.scanner._scan_with_ping", return_value=[]) as mock_ping:
            scan_lan()

        call_args = mock_ping.call_args
        assert call_args[0][0] == "172.16.0.0/24" or call_args[1].get("subnet") == "172.16.0.0/24"

