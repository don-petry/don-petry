#!/usr/bin/env python3
"""printer_diag.py — Multi-tier diagnostic and recovery tool for Brother network laser printers.

Tested on the Brother HL-L2395DW and HL-2370DW; most Brother lasers with a web admin page behave
the same. Printers are named in ../config/household.yaml (see household.example.yaml) or passed
as an IP on the command line.
Performs non-destructive diagnostics:
  - TCP port scan (80, 443, 515, 631, 9100)
  - HTTP maintenance CSV scraping (/etc/mnt_info.csv) for page counts, toner %, drum %, and error history
  - SNMP MIB queries for display buffer text, printer status, and alert tables
  - IPP (Internet Printing Protocol) queries on port 631 for queue state and job acceptance
  - PJL (Printer Job Language) status checks on port 9100
  - Recovery actions:
      --wake: Wakes printer TCP/Wi-Fi stack using HTTP GET /general/status.html
      --flush: Sends PJL Universal Exit Command (\x1b%-12345X) to clear stalled print spoolers

Usage:
  python3 printer_diag.py            # the printer marked default: true in config/household.yaml
  python3 printer_diag.py --list     # printers in the config
  python3 printer_diag.py 192.0.2.200 --wake
  python3 printer_diag.py 192.0.2.200 --flush
  python3 printer_diag.py 192.0.2.200 --full
"""

import argparse
import csv
import io
import socket
import struct
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "household.yaml"


def load_printers(path: Path = CONFIG) -> list:
    """Printers from the household config: [{name, ip, default?}, ...]. Empty if absent."""
    if not path.exists():
        return []
    try:
        import yaml  # PyYAML; optional — without it, pass the IP on the command line
    except ImportError:
        print(f"[!] PyYAML not installed; ignoring {path}. Pass the printer IP instead.", file=sys.stderr)
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [p for p in data.get("printers", []) if isinstance(p, dict) and p.get("ip")]

PORTS = [
    (80, "HTTP (Web Admin)"),
    (443, "HTTPS (Secure Web Admin)"),
    (515, "LPD (Line Printer Daemon)"),
    (631, "IPP / AirPrint"),
    (9100, "RAW / JetDirect / PJL"),
]


def check_tcp_port(ip: str, port: int, timeout: float = 2.0) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.close()
        return True
    except OSError:
        return False


def get_maintenance_csv(ip: str, timeout: float = 3.0) -> dict:
    url = f"http://{ip}/etc/mnt_info.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "PrinterDiag/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("latin1", errors="ignore")
            reader = csv.reader(io.StringIO(content))
            header = next(reader)
            row = next(reader)
            return dict(zip(header, row))
    except (OSError, StopIteration, ValueError) as e:
        return {"error": str(e)}


def query_snmp_oid(ip: str, oid_str: str, community: str = "public", timeout: float = 2.0) -> bytes:
    parts = [int(p) for p in oid_str.strip(".").split(".")]
    oid_bytes = bytes([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        if p < 128:
            oid_bytes += bytes([p])
        else:
            b = []
            while p > 0:
                b.append(p & 0x7F)
                p >>= 7
            b.reverse()
            for i in range(len(b) - 1):
                b[i] |= 0x80
            oid_bytes += bytes(b)

    val_bind = (
        b"\x30"
        + bytes([len(oid_bytes) + 4])
        + b"\x06"
        + bytes([len(oid_bytes)])
        + oid_bytes
        + b"\x05\x00"
    )
    var_bind_list = b"\x30" + bytes([len(val_bind)]) + val_bind
    pdu = (
        b"\xa0"
        + bytes([len(var_bind_list) + 12])
        + b"\x02\x04\x00\x00\x00\x01\x02\x01\x00\x02\x01\x00"
        + var_bind_list
    )
    comm_bytes = community.encode("ascii")
    packet = (
        b"\x30"
        + bytes([len(pdu) + len(comm_bytes) + 5])
        + b"\x02\x01\x00\x04"
        + bytes([len(comm_bytes)])
        + comm_bytes
        + pdu
    )

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(packet, (ip, 161))
        data, _ = s.recvfrom(2048)
        # Parse return value
        oid_idx = data.find(b"\x06", data.find(comm_bytes) + len(comm_bytes))
        if oid_idx == -1:
            return b""
        oid_len = data[oid_idx + 1]
        val_idx = oid_idx + 2 + oid_len
        vlen = data[val_idx + 1]
        return data[val_idx + 2 : val_idx + 2 + vlen]
    except (IndexError, OSError, ValueError):
        return b""
    finally:
        s.close()


def query_pjl_status(ip: str, timeout: float = 3.0) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, 9100))
        pjl = b"\x1b%-12345X@PJL \r\n@PJL INFO STATUS\r\n\x1b%-12345X"
        s.sendall(pjl)
        resp = b""
        while True:
            chunk = s.recv(1024)
            if not chunk:
                break
            resp += chunk
            if b"\x0c" in chunk or len(resp) > 2048:
                break
        return resp.decode("latin1", errors="replace").strip()
    except OSError as e:
        return f"Error: {e}"
    finally:
        s.close()


def query_ipp_attributes(ip: str, timeout: float = 3.0) -> dict:
    payload = b"\x02\x00\x00\x0b\x00\x00\x00\x01\x01"
    payload += b"\x47\x00\x12attributes-charset\x00\x05utf-8"
    payload += b"\x48\x00\x1battributes-natural-language\x00\x02en"
    uri = f"ipp://{ip}:631/ipp/print".encode("ascii")
    payload += b"\x45\x00\x0bprinter-uri" + len(uri).to_bytes(2, "big") + uri
    payload += b"\x03"

    url = f"http://{ip}:631/ipp/print"
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/ipp"}
    )
    res = {}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            idx = 8
            current_name = None
            while idx < len(data):
                tag = data[idx]
                idx += 1
                if tag in (0x01, 0x02, 0x03, 0x04, 0x05):
                    if tag == 0x03:
                        break
                    continue
                name_len = struct.unpack(">H", data[idx : idx + 2])[0]
                idx += 2
                name = data[idx : idx + name_len].decode("utf-8", errors="replace")
                idx += name_len
                val_len = struct.unpack(">H", data[idx : idx + 2])[0]
                idx += 2
                val_bytes = data[idx : idx + val_len]
                idx += val_len
                if name:
                    current_name = name
                    res[current_name] = []
                val = val_bytes
                if tag == 0x21 and len(val_bytes) == 1:
                    val = bool(val_bytes[0])
                elif tag in (0x22, 0x23) and len(val_bytes) == 4:
                    val = struct.unpack(">i", val_bytes)[0]
                elif tag in (0x41, 0x42, 0x44, 0x45, 0x47, 0x48):
                    val = val_bytes.decode("utf-8", errors="replace")
                if current_name:
                    res[current_name].append(val)
        return res
    except (IndexError, OSError, ValueError, struct.error) as e:
        return {"error": str(e)}


def wake_printer(ip: str, timeout: float = 3.0) -> bool:
    """Send an HTTP GET request to /general/status.html to wake up the network stack."""
    url = f"http://{ip}/general/status.html"
    req = urllib.request.Request(url, headers={"User-Agent": "PrinterDiag/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except OSError:
        return False


def flush_pjl_queue(ip: str, timeout: float = 3.0) -> bool:
    """Send the PJL Universal Exit Command (UEL) on port 9100 to clear hung buffers."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, 9100))
        # Universal Exit Language (UEL) sequence
        s.sendall(b"\x1b%-12345X@PJL \r\n@PJL RESET\r\n\x1b%-12345X")
        s.close()
        return True
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Brother network printer diagnostic and recovery tool."
    )
    parser.add_argument(
        "ip",
        nargs="?",
        help="Printer IP address (default: the printer marked default: true in config/household.yaml)",
    )
    parser.add_argument("--config", type=Path, default=CONFIG, help="Household printer config (YAML)")
    parser.add_argument("--list", action="store_true", help="List printers in the config and exit")
    parser.add_argument(
        "--wake",
        action="store_true",
        help="Send HTTP GET to wake up sleeping network/Wi-Fi stack",
    )
    parser.add_argument(
        "--flush",
        action="store_true",
        help="Send PJL Universal Exit Command (UEL) to flush hung print jobs",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show extended details including PJL variables and all IPP attributes",
    )
    args = parser.parse_args()

    printers = load_printers(args.config)
    if args.list:
        for p in printers:
            print(f"{p['ip']:16} {p.get('name', '')}{'  (default)' if p.get('default') else ''}")
        return
    ip = args.ip or next((p["ip"] for p in printers if p.get("default")), None) \
        or (printers[0]["ip"] if printers else None)
    if not ip:
        parser.error(f"no printer IP given and none configured in {args.config} "
                     "(copy config/household.example.yaml to config/household.yaml)")
    desc = next((p.get("name", "") for p in printers if p["ip"] == ip), "Unknown Printer")
    print(f"=== Printer Diagnostic: {desc} ({ip}) ===")

    if args.wake:
        print(f"[*] Sending HTTP GET wake-up query to http://{ip}/general/status.html...")
        success = wake_printer(ip)
        print(f"    Result: {'SUCCESS (HTTP 200 OK)' if success else 'FAILED'}")
        return

    if args.flush:
        print(f"[*] Sending PJL Universal Exit reset to {ip}:9100...")
        success = flush_pjl_queue(ip)
        print(f"    Result: {'SUCCESS (Buffer Reset Sent)' if success else 'FAILED'}")
        return

    # 1. Port scan
    print("\n[1] TCP Network Ports:")
    for port, name in PORTS:
        open_status = check_tcp_port(ip, port)
        status_str = "OPEN" if open_status else "CLOSED / TIMED OUT"
        print(f"    Port {port:4d} ({name:30s}): {status_str}")

    # 2. SNMP Display & Status
    print("\n[2] SNMP Device Status (Port 161):")
    display_bytes = query_snmp_oid(ip, "1.3.6.1.2.1.43.16.5.1.2.1.1")
    display_text = (
        display_bytes.decode("latin1", errors="replace") if display_bytes else "N/A"
    )
    query_snmp_oid(ip, "1.3.6.1.2.1.1.3.0")
    cover_raw = query_snmp_oid(ip, "1.3.6.1.2.1.43.6.1.1.3.1.1")
    cover_status = (
        "Closed"
        if cover_raw == b"\x04"
        else f"Code {cover_raw}"
        if cover_raw
        else "N/A"
    )

    print(f"    Console LCD Display : '{display_text}'")
    print(f"    Cover Status        : {cover_status}")

    # 3. HTTP Maintenance Info
    print("\n[3] Hardware Consumables & Counters (/etc/mnt_info.csv):")
    mnt = get_maintenance_csv(ip)
    if "error" in mnt:
        print(f"    HTTP maintenance scrape failed: {mnt['error']}")
    else:
        print(f"    Model Name          : {mnt.get('Model Name', 'N/A')}")
        print(f"    Serial Number       : {mnt.get('Serial No.', 'N/A')}")
        print(f"    Firmware Versions   : Main {mnt.get('Main Firmware Version')} / Sub1 {mnt.get('Sub1 Firmware Version')}")
        print(f"    Lifetime Pages      : {mnt.get('Page Counter', 'N/A')} (Print: {mnt.get('Print')}, Copy: {mnt.get('Copy')}, 2-Sided: {mnt.get('Total 2-sided Print')})")
        print(f"    Toner Remaining     : {mnt.get('% of Life Remaining(Toner)', 'N/A')}%")
        print(f"    Drum Remaining      : {mnt.get('% of Life Remaining(Drum Unit)', 'N/A')}%")
        print(f"    Total Paper Jams    : {mnt.get('Total Paper Jams', 'N/A')}")

    # 4. IPP Attributes
    print("\n[4] IPP Spooler Status (Port 631):")
    ipp = query_ipp_attributes(ip)
    if "error" in ipp:
        print(f"    IPP query failed: {ipp['error']}")
    else:
        state_map = {3: "3 (Idle)", 4: "4 (Processing / Printing)", 5: "5 (Stopped)"}
        st = ipp.get("printer-state", ["Unknown"])[0]
        st_desc = state_map.get(st, str(st))
        reasons = ipp.get("printer-state-reasons", ["none"])
        accepting = ipp.get("printer-is-accepting-jobs", [False])[0]
        jobs = ipp.get("queued-job-count", [0])[0]
        print(f"    Printer State       : {st_desc}")
        print(f"    State Reasons       : {reasons}")
        print(f"    Accepting Jobs      : {accepting}")
        print(f"    Queued Jobs         : {jobs}")

    # 5. PJL Status
    print("\n[5] PJL Engine Status (Port 9100):")
    pjl = query_pjl_status(ip)
    for line in pjl.split("\n"):
        if line.strip():
            print(f"    {line.strip()}")

    print("\n--- Diagnostic Complete ---")


if __name__ == "__main__":
    main()
