"""
Tests for skills.network.lan_scanner
"""

from __future__ import annotations

import ipaddress
import sys
from unittest.mock import MagicMock, patch

import pytest

from skills.network.lan_scanner import (
    Device,
    _read_arp_cache,
    _resolve_hostname,
    _scan_with_nmap,
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
        with patch("skills.network.lan_scanner.socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock.__exit__ = MagicMock(return_value=False)
            mock_sock.connect.side_effect = OSError("no network")
            mock_sock_cls.return_value = mock_sock

            with pytest.raises(RuntimeError):
                get_local_subnet()


class TestResolveHostname:
    def test_returns_string_on_success(self):
        with patch("skills.network.lan_scanner.socket.gethostbyaddr") as mock:
            mock.return_value = ("myhost", [], ["192.168.1.5"])
            assert _resolve_hostname("192.168.1.5") == "myhost"

    def test_returns_empty_on_failure(self):
        import socket as _socket
        with patch("skills.network.lan_scanner.socket.gethostbyaddr") as mock:
            mock.side_effect = _socket.herror()
            assert _resolve_hostname("192.168.1.99") == ""

    def test_returns_empty_on_timeout(self):
        import socket as _socket
        with patch("skills.network.lan_scanner.socket.gethostbyaddr") as mock:
            mock.side_effect = _socket.timeout("timed out")
            assert _resolve_hostname("192.168.1.100") == ""

    def test_returns_empty_on_os_error(self):
        with patch("skills.network.lan_scanner.socket.gethostbyaddr") as mock:
            mock.side_effect = OSError("network unreachable")
            assert _resolve_hostname("192.168.1.101") == ""


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


class TestScanWithNmap:
    def test_scan_with_nmap_returns_devices(self):
        fake_nm = MagicMock()
        fake_nm.all_hosts.return_value = ["192.168.1.1", "192.168.1.5"]
        host_data = {
            "192.168.1.1": {
                "addresses": {"mac": "aa:bb:cc:dd:ee:ff"},
                "hostnames": [{"name": "router.local", "type": "PTR"}],
            },
            "192.168.1.5": {
                "addresses": {"mac": "11:22:33:44:55:66"},
                "hostnames": [],
            },
        }
        fake_nm.__getitem__ = MagicMock(side_effect=lambda ip: host_data[ip])

        mock_nmap_module = MagicMock()
        mock_nmap_module.PortScanner.return_value = fake_nm

        with patch.dict("sys.modules", {"nmap": mock_nmap_module}):
            devices = _scan_with_nmap("192.168.1.0/24", timeout=2.0)

        assert len(devices) == 2
        router = next(d for d in devices if d.ip == "192.168.1.1")
        assert router.mac == "aa:bb:cc:dd:ee:ff"
        assert router.hostname == "router.local"

        other = next(d for d in devices if d.ip == "192.168.1.5")
        assert other.hostname == ""

    def test_scan_with_nmap_no_mac(self):
        fake_nm = MagicMock()
        fake_nm.all_hosts.return_value = ["10.0.0.1"]
        fake_nm.__getitem__ = MagicMock(return_value={
            "addresses": {},
            "hostnames": [{"name": "device.local", "type": "PTR"}],
        })

        mock_nmap_module = MagicMock()
        mock_nmap_module.PortScanner.return_value = fake_nm

        with patch.dict("sys.modules", {"nmap": mock_nmap_module}):
            devices = _scan_with_nmap("10.0.0.0/24")

        assert len(devices) == 1
        assert devices[0].mac == ""
        assert devices[0].hostname == "device.local"


class TestScanLan:
    def test_scan_returns_devices_sorted_by_ip(self):
        fake_devices = [
            Device(ip="192.168.1.10", mac="cc:cc:cc:cc:cc:cc"),
            Device(ip="192.168.1.2", mac="aa:aa:aa:aa:aa:aa"),
            Device(ip="192.168.1.5", mac="bb:bb:bb:bb:bb:bb"),
        ]
        with patch("skills.network.lan_scanner._NMAP_AVAILABLE", False), \
             patch("skills.network.lan_scanner._SCAPY_AVAILABLE", False), \
             patch("skills.network.lan_scanner._scan_with_ping", return_value=fake_devices):
            result = scan_lan(subnet="192.168.1.0/24")

        ips = [d.ip for d in result]
        assert ips == sorted(ips, key=ipaddress.IPv4Address)

    def test_scan_uses_nmap_when_available(self):
        fake_devices = [Device(ip="10.0.0.1", mac="de:ad:be:ef:00:01", hostname="mypc")]
        with patch("skills.network.lan_scanner._NMAP_AVAILABLE", True), \
             patch("skills.network.lan_scanner._scan_with_nmap", return_value=fake_devices) as mock_nmap, \
             patch("skills.network.lan_scanner._SCAPY_AVAILABLE", False), \
             patch("skills.network.lan_scanner._scan_with_ping") as mock_ping:
            result = scan_lan(subnet="10.0.0.0/24")

        mock_nmap.assert_called_once()
        mock_ping.assert_not_called()
        assert len(result) == 1
        assert result[0].hostname == "mypc"

    def test_scan_uses_scapy_when_nmap_unavailable(self):
        fake_devices = [Device(ip="10.0.0.1", mac="de:ad:be:ef:00:01")]
        with patch("skills.network.lan_scanner._NMAP_AVAILABLE", False), \
             patch("skills.network.lan_scanner._SCAPY_AVAILABLE", True), \
             patch("skills.network.lan_scanner._scan_with_scapy", return_value=fake_devices) as mock_scapy, \
             patch("skills.network.lan_scanner._scan_with_ping") as mock_ping:
            result = scan_lan(subnet="10.0.0.0/24")

        mock_scapy.assert_called_once()
        mock_ping.assert_not_called()
        assert len(result) == 1

    def test_scan_auto_detects_subnet(self):
        with patch("skills.network.lan_scanner.get_local_subnet", return_value="172.16.0.0/24"), \
             patch("skills.network.lan_scanner._NMAP_AVAILABLE", False), \
             patch("skills.network.lan_scanner._SCAPY_AVAILABLE", False), \
             patch("skills.network.lan_scanner._scan_with_ping", return_value=[]) as mock_ping:
            scan_lan()

        call_args = mock_ping.call_args
        assert call_args[0][0] == "172.16.0.0/24" or call_args[1].get("subnet") == "172.16.0.0/24"

