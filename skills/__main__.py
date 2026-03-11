"""
CLI entry point for the skills package.

Usage:
    python -m skills scan [--subnet SUBNET] [--timeout TIMEOUT]
    python -m skills wake <MAC> [--broadcast BROADCAST] [--port PORT]
"""

from __future__ import annotations

import argparse
import sys

from skills.network.scanner import scan_lan, get_local_subnet
from skills.network.wol import wake_on_lan


def cmd_scan(args: argparse.Namespace) -> int:
    subnet = args.subnet or get_local_subnet()
    print(f"Scanning subnet: {subnet} ...")
    devices = scan_lan(subnet=subnet, timeout=args.timeout)
    if not devices:
        print("No devices found.")
        return 0
    print(f"Found {len(devices)} device(s):\n")
    for device in devices:
        print(f"  {device}")
    return 0


def cmd_wake(args: argparse.Namespace) -> int:
    result = wake_on_lan(
        mac=args.mac,
        broadcast=args.broadcast,
        port=args.port,
    )
    if result["success"]:
        print(
            f"Magic packet sent to {result['mac']} "
            f"via {result['broadcast']}:{result['port']}"
        )
        return 0
    else:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="skills",
        description="智能体技能集合 – Intelligent Agent Skills",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- scan ---
    scan_parser = subparsers.add_parser(
        "scan",
        help="扫描局域网设备 / Scan LAN for active devices",
    )
    scan_parser.add_argument(
        "--subnet",
        default=None,
        help="CIDR subnet to scan (e.g. 192.168.1.0/24). "
        "Defaults to the local /24 subnet.",
    )
    scan_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="ARP reply timeout in seconds (default: 2.0)",
    )

    # --- wake ---
    wake_parser = subparsers.add_parser(
        "wake",
        help="发送网络唤醒包 / Send Wake-on-LAN magic packet",
    )
    wake_parser.add_argument(
        "mac",
        help="MAC address of the target machine (e.g. aa:bb:cc:dd:ee:ff)",
    )
    wake_parser.add_argument(
        "--broadcast",
        default="255.255.255.255",
        help="Broadcast address (default: 255.255.255.255)",
    )
    wake_parser.add_argument(
        "--port",
        type=int,
        default=9,
        help="UDP port (default: 9)",
    )

    args = parser.parse_args()

    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "wake":
        return cmd_wake(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
