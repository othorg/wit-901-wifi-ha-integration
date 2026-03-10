#!/usr/bin/env python3
"""CLI tool to configure a WT901WIFI sensor's WiFi and streaming target.

Sends ASCII commands via UDP to the sensor's LOCALPORT (default 9250).
The sensor must be reachable from this machine (e.g. connected to its AP).

Usage examples:

  # Full provisioning: set WiFi + UDP target in one atomic command
  python tools/configure_sensor.py \\
    --ssid "MyHomeWiFi" --password "secret" \\
    --target-ip 192.168.1.100 --target-port 1399 --protocol udp

  # Probe only: check if sensor is reachable
  python tools/configure_sensor.py --probe-only

  # Change target IP only (sensor already on network)
  python tools/configure_sensor.py \\
    --sensor-host 192.168.1.200 \\
    --target-ip 192.168.1.100 --target-port 1399 --protocol udp \\
    --target-only

  # Listen for frames to discover device ID
  python tools/configure_sensor.py --discover

  # Switch sensor back to AP mode
  python tools/configure_sensor.py --ap-mode
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

# Add project root to path so we can reuse the protocol parser.
# Works from both repo root (tools/) and HACS install (custom_components/wit_901_wifi/tools/).
_TOOL_DIR = Path(__file__).resolve().parent
for _candidate in (_TOOL_DIR.parent, _TOOL_DIR.parent.parent.parent):
    if (_candidate / "custom_components" / "wit_901_wifi" / "protocol.py").exists():
        sys.path.insert(0, str(_candidate))
        break


def probe_sensor(host: str, port: int) -> bool:
    """Check if the sensor is reachable via UDP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(3)
            sock.sendto(b"", (host, port))
            print(f"[OK] Sensor at {host}:{port} is reachable (UDP path open)")
            return True
    except OSError as exc:
        print(f"[FAIL] Cannot reach {host}:{port}: {exc}")
        return False


def send_command(host: str, port: int, payload: bytes, description: str) -> None:
    """Send a UDP command to the sensor."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload, (host, port))
    print(f"[SENT] {description}")
    print(f"       → {host}:{port}")


def discover_device(listen_port: int, timeout: int) -> None:
    """Listen for streaming frames and extract device info."""
    from custom_components.wit_901_wifi.protocol import parse_streaming_frame

    print(f"Listening on UDP 0.0.0.0:{listen_port} for {timeout}s ...")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", listen_port))
        sock.settimeout(timeout)
        try:
            data, addr = sock.recvfrom(1024)
            parsed = parse_streaming_frame(data)
            if parsed:
                print(f"\n[FOUND] Device streaming from {addr[0]}:{addr[1]}")
                print(f"        Device ID:    {parsed['device_id']}")
                print(f"        Roll:         {parsed['roll_deg']}°")
                print(f"        Pitch:        {parsed['pitch_deg']}°")
                print(f"        Yaw:          {parsed['yaw_deg']}°")
                print(f"        Temperature:  {parsed['temperature_c']}°C")
                print(
                    "        Battery:      "
                    f"{parsed['battery_voltage_v']}V ({parsed['battery_percentage']}%)"
                )
                print(f"        RSSI:         {parsed['rssi_dbm']} dBm")
                print(f"        Version:      {parsed['version']}")
                print(f"\n        Full frame: {json.dumps(parsed, indent=2)}")
            else:
                print(f"[WARN] Received {len(data)} bytes from {addr} but parse failed")
                print(f"       Hex: {data.hex(' ')}")
        except TimeoutError:
            print("[TIMEOUT] No frames received. Is the sensor streaming to this port?")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure a WT901WIFI sensor via UDP ASCII commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Sensor connection
    parser.add_argument(
        "--sensor-host",
        default="192.168.4.1",
        help="Sensor IP address (default: 192.168.4.1 for AP mode)",
    )
    parser.add_argument(
        "--sensor-port",
        type=int,
        default=9250,
        help="Sensor LOCALPORT (default: 9250)",
    )

    # WiFi credentials
    parser.add_argument(
        "--ssid",
        help="WiFi SSID (2.4 GHz) for the sensor to connect to",
    )
    parser.add_argument("--password", help="WiFi password")

    # Streaming target
    parser.add_argument(
        "--protocol",
        choices=["udp", "tcp"],
        default="udp",
        help="Streaming protocol (default: udp)",
    )
    parser.add_argument("--target-ip", help="Target IP for streaming (your HA server)")
    parser.add_argument(
        "--target-port",
        type=int,
        default=1399,
        help="Target port (default: 1399)",
    )

    # Modes
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="Only probe sensor reachability, don't send commands",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Listen for frames and display device info",
    )
    parser.add_argument(
        "--discover-port",
        type=int,
        default=1399,
        help="Port to listen on for --discover (default: 1399)",
    )
    parser.add_argument(
        "--discover-timeout",
        type=int,
        default=10,
        help="Timeout in seconds for --discover (default: 10)",
    )
    parser.add_argument(
        "--target-only",
        action="store_true",
        help="Only change streaming target (no WiFi change)",
    )
    parser.add_argument(
        "--ap-mode",
        action="store_true",
        help="Switch sensor back to AP mode (UDP)",
    )

    args = parser.parse_args()

    # --- Discover mode ---
    if args.discover:
        discover_device(args.discover_port, args.discover_timeout)
        return

    # --- Probe ---
    if args.probe_only:
        ok = probe_sensor(args.sensor_host, args.sensor_port)
        sys.exit(0 if ok else 1)

    # --- AP mode ---
    if args.ap_mode:
        probe_sensor(args.sensor_host, args.sensor_port)
        cmd = b"WITAPUDP\r\n"
        send_command(args.sensor_host, args.sensor_port, cmd, "Switch to AP mode (UDP)")
        print("\n[INFO] Sensor will restart in AP mode. Connect to its WiFi network.")
        return

    # --- Target only ---
    if args.target_only:
        if not args.target_ip:
            parser.error("--target-ip is required with --target-only")
        probe_sensor(args.sensor_host, args.sensor_port)
        proto_tag = "TCP" if args.protocol == "tcp" else "UDP"
        cmd = f"{proto_tag}IP:{args.target_ip},{args.target_port}\r\n".encode("ascii")
        send_command(
            args.sensor_host,
            args.sensor_port,
            cmd,
            f"Set streaming target to {args.protocol.upper()} {args.target_ip}:{args.target_port}",
        )
        print("\n[INFO] Sensor will restart and stream to the new target.")
        return

    # --- Full provisioning ---
    if not args.ssid:
        parser.error(
            "--ssid is required for full provisioning "
            "(or use --target-only / --probe-only / --discover)"
        )
    if not args.password:
        parser.error("--password is required for full provisioning")
    if not args.target_ip:
        parser.error("--target-ip is required for full provisioning")

    probe_sensor(args.sensor_host, args.sensor_port)

    proto_tag = "TCP" if args.protocol == "tcp" else "UDP"
    cmd = (
        f'IPWIFI:"{args.ssid}","{args.password}";'
        f"{proto_tag}{args.target_ip},{args.target_port}\r\n"
    ).encode("ascii")
    send_command(
        args.sensor_host,
        args.sensor_port,
        cmd,
        "Full provisioning: "
        f"WiFi={args.ssid}, Target={proto_tag} {args.target_ip}:{args.target_port}",
    )

    print("\n[INFO] Command sent. The sensor will now:")
    print("       1. Restart")
    print(f"       2. Connect to WiFi '{args.ssid}'")
    print(f"       3. Stream {args.protocol.upper()} to {args.target_ip}:{args.target_port}")
    print("\n[TIP]  Reconnect to your home WiFi, then run:")
    print(f"       python tools/configure_sensor.py --discover --discover-port {args.target_port}")


if __name__ == "__main__":
    main()
