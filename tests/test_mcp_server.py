"""
Tests for skills.mcp_server
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from skills.network.scanner import Device


class TestMcpServerTools:
    """Test the MCP server tool functions directly."""

    def test_scan_lan_returns_list_of_dicts(self):
        from skills.mcp_server import scan_lan

        fake_devices = [
            Device(ip="192.168.1.1", mac="aa:bb:cc:dd:ee:ff", hostname="router"),
            Device(ip="192.168.1.5", mac="11:22:33:44:55:66"),
        ]
        with patch("skills.mcp_server._scan_lan", return_value=fake_devices):
            result = scan_lan()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {
            "ip": "192.168.1.1",
            "mac": "aa:bb:cc:dd:ee:ff",
            "hostname": "router",
        }
        assert result[1] == {
            "ip": "192.168.1.5",
            "mac": "11:22:33:44:55:66",
            "hostname": "",
        }

    def test_scan_lan_passes_subnet_and_timeout(self):
        from skills.mcp_server import scan_lan

        with patch("skills.mcp_server._scan_lan", return_value=[]) as mock:
            scan_lan(subnet="10.0.0.0/24", timeout=5.0)

        mock.assert_called_once_with(subnet="10.0.0.0/24", timeout=5.0)

    def test_scan_lan_empty_network(self):
        from skills.mcp_server import scan_lan

        with patch("skills.mcp_server._scan_lan", return_value=[]):
            result = scan_lan()

        assert result == []

    def test_wake_on_lan_success(self):
        from skills.mcp_server import wake_on_lan

        fake_result = {
            "success": True,
            "mac": "aa:bb:cc:dd:ee:ff",
            "broadcast": "255.255.255.255",
            "port": 9,
            "error": None,
        }
        with patch("skills.mcp_server._wake_on_lan", return_value=fake_result):
            result = wake_on_lan("aa:bb:cc:dd:ee:ff")

        assert result["success"] is True
        assert result["mac"] == "aa:bb:cc:dd:ee:ff"
        assert result["error"] is None

    def test_wake_on_lan_failure(self):
        from skills.mcp_server import wake_on_lan

        fake_result = {
            "success": False,
            "mac": "bad-mac",
            "broadcast": "255.255.255.255",
            "port": 9,
            "error": "Invalid MAC address",
        }
        with patch("skills.mcp_server._wake_on_lan", return_value=fake_result):
            result = wake_on_lan("bad-mac")

        assert result["success"] is False
        assert result["error"] == "Invalid MAC address"

    def test_wake_on_lan_passes_all_params(self):
        from skills.mcp_server import wake_on_lan

        fake_result = {
            "success": True,
            "mac": "aa:bb:cc:dd:ee:ff",
            "broadcast": "192.168.1.255",
            "port": 7,
            "error": None,
        }
        with patch("skills.mcp_server._wake_on_lan", return_value=fake_result) as mock:
            wake_on_lan("aa:bb:cc:dd:ee:ff", broadcast="192.168.1.255", port=7)

        mock.assert_called_once_with(
            mac="aa:bb:cc:dd:ee:ff",
            broadcast="192.168.1.255",
            port=7,
        )


class TestMcpServerRegistration:
    """Test that the MCP server registers tools correctly."""

    def test_mcp_instance_has_tools(self):
        import asyncio
        from skills.mcp_server import mcp

        tools = asyncio.run(mcp.list_tools())
        tool_names = [t.name for t in tools]
        assert "scan_lan" in tool_names
        assert "wake_on_lan" in tool_names

    def test_scan_lan_tool_has_description(self):
        import asyncio
        from skills.mcp_server import mcp

        tools = asyncio.run(mcp.list_tools())
        scan_tool = next(t for t in tools if t.name == "scan_lan")
        assert scan_tool.description
        assert len(scan_tool.description) > 0

    def test_wake_on_lan_tool_has_description(self):
        import asyncio
        from skills.mcp_server import mcp

        tools = asyncio.run(mcp.list_tools())
        wake_tool = next(t for t in tools if t.name == "wake_on_lan")
        assert wake_tool.description
        assert len(wake_tool.description) > 0
