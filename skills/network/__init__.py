"""
Network Skills - 网络技能模块
Provides LAN device scanning and Wake-on-LAN functionality.
"""

from .scanner import scan_lan, get_local_subnet
from .wol import send_magic_packet, wake_on_lan

__all__ = ["scan_lan", "get_local_subnet", "send_magic_packet", "wake_on_lan"]
