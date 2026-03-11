"""
Network Skills Example - 网络技能使用示例

Demonstrates scanning the local network and sending Wake-on-LAN packets.
"""

from skills.network.lan_scanner import scan_lan, get_local_subnet
from skills.network.wake_on_lan import wake_on_lan


def demo_scan():
    """Scan the local network and print found devices."""
    subnet = get_local_subnet()
    print(f"=== LAN Scanner / 局域网设备扫描 ===")
    print(f"Scanning subnet: {subnet}\n")

    devices = scan_lan(subnet=subnet)

    if not devices:
        print("No active devices found. (No ARP responses received.)")
        return

    print(f"Found {len(devices)} active device(s):\n")
    for device in devices:
        print(f"  {device}")


def demo_wol(mac: str, broadcast: str = "255.255.255.255"):
    """Send a Wake-on-LAN magic packet to the given MAC address."""
    print(f"\n=== Wake-on-LAN / 网络唤醒 ===")
    print(f"Sending magic packet to {mac} via {broadcast}...")

    result = wake_on_lan(mac, broadcast=broadcast)

    if result["success"]:
        print(f"✓ Magic packet sent successfully to {result['mac']}")
    else:
        print(f"✗ Failed: {result['error']}")


if __name__ == "__main__":
    demo_scan()

    # Example WOL call (replace with the real MAC of your target machine):
    # demo_wol("aa:bb:cc:dd:ee:ff", broadcast="192.168.1.255")
