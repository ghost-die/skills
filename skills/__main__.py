"""
CLI entry point for the skills package.

Usage:
    python -m skills scan [--subnet SUBNET] [--timeout TIMEOUT]
    python -m skills wake <MAC> [--broadcast BROADCAST] [--port PORT]
    python -m skills port-scan <HOST> [--ports PORTS] [--timeout TIMEOUT]
    python -m skills ping <HOST> [--count COUNT] [--timeout TIMEOUT]
    python -m skills mcp
"""

from __future__ import annotations

import argparse
import sys

from skills.network.scanner import scan_lan, get_local_subnet
from skills.network.wol import wake_on_lan
from skills.network.port_scanner import scan_ports
from skills.network.ping import ping_host


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


def cmd_mcp(args: argparse.Namespace) -> int:  # noqa: ARG001
    from skills.mcp_server import main as mcp_main
    mcp_main()
    return 0


def cmd_port_scan(args: argparse.Namespace) -> int:
    ports = None
    if args.ports:
        try:
            ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
        except ValueError:
            print("Error: --ports must be a comma-separated list of integers.", file=sys.stderr)
            return 1

    print(f"Scanning ports on {args.host} ...")
    results = scan_ports(host=args.host, ports=ports, timeout=args.timeout)
    if not results:
        print("No open ports found.")
        return 0
    print(f"Found {len(results)} open port(s):\n")
    for r in results:
        service = f"/{r['service']}" if r["service"] else ""
        print(f"  {r['port']}{service}  ({r['state']})")
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    result = ping_host(host=args.host, count=args.count, timeout=args.timeout)
    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1
    status = "reachable" if result["reachable"] else "unreachable"
    print(
        f"PING {result['host']}: {result['sent']} sent, "
        f"{result['received']} received, "
        f"{result['packet_loss_pct']:.0f}% loss — {status}"
    )
    if result["rtt_avg_ms"] is not None:
        print(
            f"RTT: min={result['rtt_min_ms']:.3f} ms  "
            f"avg={result['rtt_avg_ms']:.3f} ms  "
            f"max={result['rtt_max_ms']:.3f} ms"
        )
    return 0 if result["reachable"] else 1


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

    # --- port-scan ---
    port_scan_parser = subparsers.add_parser(
        "port-scan",
        help="扫描主机开放端口 / Scan TCP ports on a host",
    )
    port_scan_parser.add_argument(
        "host",
        help="IP address or hostname to scan (e.g. 192.168.1.1)",
    )
    port_scan_parser.add_argument(
        "--ports",
        default=None,
        help="Comma-separated list of ports (e.g. 22,80,443). "
        "Defaults to 18 common service ports.",
    )
    port_scan_parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Per-port connection timeout in seconds (default: 1.0)",
    )

    # --- ping ---
    ping_parser = subparsers.add_parser(
        "ping",
        help="测试主机延迟 / Ping a host and measure RTT latency",
    )
    ping_parser.add_argument(
        "host",
        help="IP address or hostname to ping (e.g. 192.168.1.1 or 8.8.8.8)",
    )
    ping_parser.add_argument(
        "--count",
        type=int,
        default=4,
        help="Number of ICMP packets to send (default: 4)",
    )
    ping_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Per-packet wait timeout in seconds (default: 2.0)",
    )

    # --- mcp ---
    subparsers.add_parser(
        "mcp",
        help="启动 MCP 服务器 / Start the MCP server for Claude Code",
    )

    args = parser.parse_args()

    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "wake":
        return cmd_wake(args)
    elif args.command == "port-scan":
        return cmd_port_scan(args)
    elif args.command == "ping":
        return cmd_ping(args)
    elif args.command == "mcp":
        return cmd_mcp(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
