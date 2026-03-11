"""
Network Skills - 网络技能模块
Provides LAN device scanning, Wake-on-LAN, port scanning, and ping/latency
check functionality.
"""

from .scanner import scan_lan, get_local_subnet
from .wol import send_magic_packet, wake_on_lan
from .port_scanner import scan_ports, get_service_name, DEFAULT_PORTS
from .ping import ping_host

__all__ = [
    "scan_lan",
    "get_local_subnet",
    "send_magic_packet",
    "wake_on_lan",
    "scan_ports",
    "get_service_name",
    "DEFAULT_PORTS",
    "ping_host",
]
