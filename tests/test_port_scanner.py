"""
Tests for skills.network.port_scanner
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from skills.network.port_scanner import (
    DEFAULT_PORTS,
    _check_port,
    get_service_name,
    scan_ports,
)


class TestCheckPort:
    def test_returns_true_for_open_port(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch(
            "skills.network.port_scanner.socket.create_connection",
            return_value=mock_conn,
        ):
            assert _check_port("192.168.1.1", 80, timeout=1.0) is True

    def test_returns_false_for_closed_port(self):
        with patch(
            "skills.network.port_scanner.socket.create_connection",
            side_effect=ConnectionRefusedError,
        ):
            assert _check_port("192.168.1.1", 9999, timeout=1.0) is False

    def test_returns_false_on_timeout(self):
        with patch(
            "skills.network.port_scanner.socket.create_connection",
            side_effect=OSError("timed out"),
        ):
            assert _check_port("192.168.1.1", 80, timeout=0.1) is False


class TestGetServiceName:
    @pytest.mark.parametrize(
        "port, expected",
        [
            (22, "ssh"),
            (80, "http"),
            (443, "https"),
            (3306, "mysql"),
            (3389, "rdp"),
        ],
    )
    def test_known_ports(self, port, expected):
        assert get_service_name(port) == expected

    def test_unknown_port_falls_back_to_socket(self):
        with patch(
            "skills.network.port_scanner.socket.getservbyport",
            return_value="custom",
        ):
            assert get_service_name(12345) == "custom"

    def test_unknown_port_returns_empty_string(self):
        with patch(
            "skills.network.port_scanner.socket.getservbyport",
            side_effect=OSError,
        ):
            assert get_service_name(12345) == ""


class TestDefaultPorts:
    def test_default_ports_is_sorted(self):
        assert DEFAULT_PORTS == sorted(DEFAULT_PORTS)

    def test_default_ports_not_empty(self):
        assert len(DEFAULT_PORTS) > 0

    def test_common_ports_included(self):
        assert 22 in DEFAULT_PORTS  # ssh
        assert 80 in DEFAULT_PORTS  # http
        assert 443 in DEFAULT_PORTS  # https


class TestScanPorts:
    def test_returns_open_ports_only(self):
        def fake_check(host, port, timeout):
            return port in (22, 80)

        with patch("skills.network.port_scanner._check_port", side_effect=fake_check):
            results = scan_ports("192.168.1.1", ports=[22, 80, 443, 8080])

        assert len(results) == 2
        ports = [r["port"] for r in results]
        assert 22 in ports
        assert 80 in ports
        assert 443 not in ports

    def test_results_sorted_by_port(self):
        def fake_check(host, port, timeout):
            return True  # all open

        with patch("skills.network.port_scanner._check_port", side_effect=fake_check):
            results = scan_ports("10.0.0.1", ports=[8080, 22, 443, 80])

        port_nums = [r["port"] for r in results]
        assert port_nums == sorted(port_nums)

    def test_result_dict_has_required_keys(self):
        with patch(
            "skills.network.port_scanner._check_port", return_value=True
        ):
            results = scan_ports("10.0.0.1", ports=[80])

        assert len(results) == 1
        r = results[0]
        assert "port" in r
        assert "service" in r
        assert "state" in r
        assert r["state"] == "open"
        assert r["port"] == 80
        assert r["service"] == "http"

    def test_empty_ports_returns_empty_list(self):
        results = scan_ports("192.168.1.1", ports=[])
        assert results == []

    def test_all_ports_closed_returns_empty_list(self):
        with patch("skills.network.port_scanner._check_port", return_value=False):
            results = scan_ports("192.168.1.1", ports=[22, 80, 443])
        assert results == []

    def test_uses_default_ports_when_none_given(self):
        with patch(
            "skills.network.port_scanner._check_port", return_value=False
        ) as mock_check:
            scan_ports("192.168.1.1")

        scanned_ports = {call.args[1] for call in mock_check.call_args_list}
        for port in DEFAULT_PORTS:
            assert port in scanned_ports

    def test_service_name_populated(self):
        with patch("skills.network.port_scanner._check_port", return_value=True):
            results = scan_ports("10.0.0.1", ports=[22, 443])

        by_port = {r["port"]: r for r in results}
        assert by_port[22]["service"] == "ssh"
        assert by_port[443]["service"] == "https"

    def test_unknown_service_port_has_empty_or_named_service(self):
        with patch(
            "skills.network.port_scanner._check_port", return_value=True
        ), patch(
            "skills.network.port_scanner.socket.getservbyport",
            side_effect=OSError,
        ):
            results = scan_ports("10.0.0.1", ports=[12345])

        assert len(results) == 1
        assert results[0]["service"] == ""
