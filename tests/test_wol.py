"""
Tests for skills.network.wol
"""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, call, patch

import pytest

from skills.network.wol import (
    _normalise_mac,
    build_magic_packet,
    send_magic_packet,
    wake_on_lan,
)


class TestNormaliseMac:
    @pytest.mark.parametrize(
        "mac, expected",
        [
            ("AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"),
            ("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
            ("AA-BB-CC-DD-EE-FF", "aa:bb:cc:dd:ee:ff"),
            ("aabbccddeeff", "aa:bb:cc:dd:ee:ff"),
            ("AABBCCDDEEFF", "aa:bb:cc:dd:ee:ff"),
        ],
    )
    def test_valid_formats(self, mac, expected):
        assert _normalise_mac(mac) == expected

    @pytest.mark.parametrize(
        "mac",
        [
            "gg:bb:cc:dd:ee:ff",   # invalid hex
            "aa:bb:cc:dd:ee",      # too short
            "aa:bb:cc:dd:ee:ff:00",  # too long
            "",
            "not-a-mac",
        ],
    )
    def test_invalid_formats_raise(self, mac):
        with pytest.raises(ValueError):
            _normalise_mac(mac)


class TestBuildMagicPacket:
    def test_length_is_102_bytes(self):
        packet = build_magic_packet("aa:bb:cc:dd:ee:ff")
        assert len(packet) == 102

    def test_starts_with_six_ff_bytes(self):
        packet = build_magic_packet("aa:bb:cc:dd:ee:ff")
        assert packet[:6] == b"\xff\xff\xff\xff\xff\xff"

    def test_mac_repeated_16_times(self):
        mac = "aa:bb:cc:dd:ee:ff"
        mac_bytes = bytes.fromhex(mac.replace(":", ""))
        packet = build_magic_packet(mac)
        assert packet[6:] == mac_bytes * 16

    def test_case_insensitive(self):
        p1 = build_magic_packet("AA:BB:CC:DD:EE:FF")
        p2 = build_magic_packet("aa:bb:cc:dd:ee:ff")
        assert p1 == p2

    def test_raises_on_bad_mac(self):
        with pytest.raises(ValueError):
            build_magic_packet("not-a-mac")


class TestSendMagicPacket:
    def test_sends_correct_packet(self):
        mac = "aa:bb:cc:dd:ee:ff"
        expected_packet = build_magic_packet(mac)

        mock_socket = MagicMock()
        mock_socket.__enter__ = MagicMock(return_value=mock_socket)
        mock_socket.__exit__ = MagicMock(return_value=False)

        with patch("skills.network.wol.socket.socket", return_value=mock_socket):
            send_magic_packet(mac)

        mock_socket.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET, socket.SO_BROADCAST, 1
        )
        mock_socket.connect.assert_called_once_with(("255.255.255.255", 9))
        mock_socket.send.assert_called_once_with(expected_packet)

    def test_custom_broadcast_and_port(self):
        mock_socket = MagicMock()
        mock_socket.__enter__ = MagicMock(return_value=mock_socket)
        mock_socket.__exit__ = MagicMock(return_value=False)

        with patch("skills.network.wol.socket.socket", return_value=mock_socket):
            send_magic_packet(
                "aa:bb:cc:dd:ee:ff",
                broadcast="192.168.1.255",
                port=7,
            )

        mock_socket.connect.assert_called_once_with(("192.168.1.255", 7))


class TestWakeOnLan:
    def test_success_returns_dict(self):
        with patch("skills.network.wol.send_magic_packet") as mock_send:
            result = wake_on_lan("aa:bb:cc:dd:ee:ff")

        assert result["success"] is True
        assert result["mac"] == "aa:bb:cc:dd:ee:ff"
        assert result["broadcast"] == "255.255.255.255"
        assert result["port"] == 9
        assert result["error"] is None
        mock_send.assert_called_once()

    def test_failure_on_invalid_mac(self):
        result = wake_on_lan("invalid-mac")
        assert result["success"] is False
        assert result["error"] is not None

    def test_failure_on_socket_error(self):
        with patch(
            "skills.network.wol.send_magic_packet",
            side_effect=OSError("socket error"),
        ):
            result = wake_on_lan("aa:bb:cc:dd:ee:ff")

        assert result["success"] is False
        assert "socket error" in result["error"]

    def test_custom_broadcast(self):
        with patch("skills.network.wol.send_magic_packet") as mock_send:
            result = wake_on_lan(
                "aa:bb:cc:dd:ee:ff",
                broadcast="192.168.0.255",
                port=7,
            )

        assert result["broadcast"] == "192.168.0.255"
        assert result["port"] == 7
        mock_send.assert_called_once_with(
            "aa:bb:cc:dd:ee:ff", broadcast="192.168.0.255", port=7
        )

    def test_default_broadcast_is_255(self):
        with patch("skills.network.wol.send_magic_packet"):
            result = wake_on_lan("aa:bb:cc:dd:ee:ff")
        assert result["broadcast"] == "255.255.255.255"
