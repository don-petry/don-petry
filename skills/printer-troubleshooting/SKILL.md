---
name: printer-troubleshooting
description: Diagnose and recover Brother network laser printers (tested on HL-L2395DW and HL-2370DW)
  — offline or "looking for printer", jobs stuck in the queue, deep sleep that won't wake, stalled spoolers
  (PJL reset), toner/drum/jam counters, AirPrint across VLANs, and Wi-Fi link quality. Use when a printer
  is offline, not printing, or unreachable from some devices.
license: MIT
---

# Printer Troubleshooting Runbook & Diagnostics

A multi-tier diagnostic protocol and recovery tool for Brother network laser printers (tested on the
HL-L2395DW and HL-2370DW; most Brother lasers with a web admin page behave the same).

Use this skill whenever:
- A printer is reported as "offline", "not printing", "looking for printer", or jobs fail to emerge.
- Print jobs sit in the queue, or a home-automation dashboard shows `printing` without pages leaving the machine.
- AirPrint or mDNS discovery fails from a guest or IoT network.
- The printer drops into a deep sleep that it will not wake from.

---

## Your printers (config)

Read `config/household.yaml` first. It names each printer (model, fixed IP, MAC, which network it is
on), the network layout (main LAN, any guest VLAN, the router), the keep-alive host, and the
Home Assistant entity if one exists. If the file is missing, copy `config/household.example.yaml`,
ask the user for their printers' IPs and models, and write it. Give every printer a fixed DHCP
reservation — a printer whose address moves is the most common "offline" cause.

The examples below use `192.0.2.200`; substitute the printer's IP from the config.

| Port | Use |
| :--- | :--- |
| `80` / `443` | Web admin (HTTP/HTTPS) |
| `515` | LPD |
| `631` | IPP / AirPrint |
| `9100` | RAW / JetDirect / PJL |
| `161` (UDP) | SNMP |

---

## Automated Diagnostic Tool: `printer_diag.py`

The CLI tool is `scripts/printer_diag.py` (Python 3, stdlib; PyYAML optional, to read the config).
With no IP it uses the printer marked `default: true` in the config; `--list` shows them all.

### 1. Run Standard Diagnostic Scan

```bash
python3 scripts/printer_diag.py 192.0.2.200
```

**Checks executed in <2 seconds:**
1. **TCP Port Scan**: Verifies ports `80` (HTTP), `443` (HTTPS), `515` (LPD), `631` (IPP), and `9100` (RAW/PJL).
2. **SNMP Device Status**: Queries OID `1.3.6.1.2.1.43.16.5.1.2.1.1` for current console LCD text (e.g. `Sleep`, `Ready`, `Printing`, `CoverOpen`) and cover interlock status.
3. **Hardware Consumables & Counters**: Scrapes `/etc/mnt_info.csv` for lifetime page counts (Print, Copy, 2-Sided), toner remaining %, drum unit remaining %, and paper jam counts.
4. **IPP Spooler Status**: Decodes binary IPP attributes on port 631 (`printer-state`, `printer-state-reasons`, `printer-is-accepting-jobs`).
5. **PJL Engine Status**: Sends `@PJL INFO STATUS` on port 9100 to verify online readiness and engine status code.

### 2. Flush Stalled / Hung Print Spooler (`--flush`)

If a print job stalled mid-transmission or the printer received corrupt raster data that halted the interpreter:

```bash
python3 scripts/printer_diag.py 192.0.2.200 --flush
```

* **What it does**: Connects to port 9100 and sends the PJL **Universal Exit Command (UEL)** sequence:
  ```text
  \x1b%-12345X@PJL \r\n@PJL RESET\r\n\x1b%-12345X
  ```
* **Why it works**: Instructs the Brother print engine to immediately flush incomplete or abandoned raster buffers from memory, reset the parser, and return the engine to the `Ready` state without requiring a physical reboot.

### 3. Wake Sleeping Printer TCP Stack (`--wake`)

```bash
python3 scripts/printer_diag.py 192.0.2.200 --wake
```

* **What it does**: Issues an HTTP `GET` request to `http://<IP>/general/status.html`.
* **Why it works**: Wakes the printer's network stack and 802.11 power-save mode without sending a physical print page.

---

## Multi-Tier Diagnostic Protocol

When diagnosing print issues, execute the following investigation layers in order:

### Layer 1: Network Reachability & Sleep State
1. **Ping the printer**:
   ```bash
   ping -c 3 192.0.2.200
   ```
   * *If packets drop or RTT > 500ms*: Wi-Fi link degradation or the printer is in deep sleep.
2. **Test HTTP Admin**:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" --connect-timeout 2 http://192.0.2.200/general/status.html
   ```
   * *Must return `200`*. If it returns `000` or times out, the printer is powered off or disconnected from Wi-Fi.

### Layer 2: Hardware Consumables & Physical Jam Check
Run the diagnostic script or fetch `/etc/mnt_info.csv` directly:
```bash
curl -s http://192.0.2.200/etc/mnt_info.csv | python3 -c "
import sys, csv
r = csv.reader(sys.stdin)
header, row = next(r), next(r)
for h, v in zip(header, row):
    if any(k in h for k in ['Page Counter', 'Toner', 'Drum', 'Jam', 'Error']):
        print(f'{h}: {v}')
"
```
* **Page Counter**: Records lifetime pages printed.
* **Toner % / Drum %**: Verify supplies are not depleted.
* **Total Paper Jams**: If non-zero, inspect Tray 1, inside cavity, and rear duplex door.

### Layer 3: Home Automation Telemetry & Job History
If Home Assistant (Brother or IPP integration) or another monitor tracks the printer, read the entity's
recent state history — the config's `home_assistant` block says how on this household's host. In
Home Assistant the recorder database is `home-assistant_v2.db`:
```sql
SELECT s.state, s.last_updated_ts
FROM states s JOIN states_meta sm ON s.metadata_id = sm.metadata_id
WHERE sm.entity_id = 'sensor.brother_hl_l2395dw_series'
ORDER BY s.state_id DESC LIMIT 10;
```
* **Pattern Analysis**:
  * `idle` $\rightarrow$ `printing` (60s) $\rightarrow$ `idle` without the page counter incrementing: the client sent a job that stalled during rasterization or hit an I/O timeout.
  * `unavailable`: the printer lost network connectivity or entered un-wakeable deep sleep.

### Layer 4: Deep Sleep Prevention (Keep-Alive Cron)
Brother printers on Wi-Fi drop their network interfaces into un-wakeable deep sleep if idle for long
periods. Fix it with a keep-alive on any always-on machine (NAS, Raspberry Pi, router with cron) —
the config's `keepalive` block records where this household runs it:
```sh
#!/bin/sh
# printer_keepalive.sh — run every 5 minutes: */5 * * * *
PRINTERS="192.0.2.200 192.0.2.163"
for ip in $PRINTERS; do
  curl -s -o /dev/null --connect-timeout 2 --max-time 10 "http://$ip/general/status.html" &
done
wait
```
* **CRITICAL GOTCHA**: the embedded web server (`debut/1.30`) **rejects HTTP HEAD (`-I`) requests with `HTTP/1.1 411 Length Required`**. The keep-alive **must** use a GET, as above. Never switch it to `-I`.

### Layer 5: Cross-VLAN Routing & Wi-Fi Link Quality
If printing fails only from phones, Macs or guest laptops:
1. **Check the client's network** against the config's `network` block. A client on the same LAN reaches the printer directly; a client on a guest or IoT VLAN needs routing and discovery help.
2. **Verify a firewall allow rule** from the guest zone to the printer's IP (the config names it, e.g. `guest_firewall_rule`), protocol all or at least TCP 631/9100 and UDP 5353.
3. **Verify cross-VLAN mDNS**: AirPrint discovery is multicast, so the router's mDNS reflector/repeater must cover both networks (UniFi: Settings → Networks → Multicast DNS; OpenWrt: `umdns` or `avahi` reflector).
4. **Inspect Wi-Fi link quality** in the router's client list: signal, PHY rate, TX retries. On UniFi:
   ```bash
   curl -sk -H "X-API-KEY: $UNIFI_API_KEY" https://192.0.2.1/proxy/network/api/s/default/stat/sta | python3 -c "
   import sys, json
   for c in json.loads(sys.stdin.read()).get('data', []):
       if c.get('ip') in ['192.0.2.200', '192.0.2.163']:
           print(c.get('name'), c.get('ip'), 'Signal:', c.get('signal'), 'Retries:', c.get('tx_retries'))
   "
   ```
   High retry counts (>1,000) or low PHY rates (<12 Mbps) cause high-resolution AirPrint PDF raster streams (15–30 MB) to exceed the printer's 60-second connection timeout.

### Layer 6: PJL Firmware Variables & Tray Myth
* **`INTRAY1=LOCKED` is Normal**: Running `@PJL INFO VARIABLES` on single-tray Brother printers (HL-L2395DW, HL-2370DW) lists `INTRAY1=LOCKED`. This is an internal read-only firmware variable inherited from multi-tray enterprise codebases. **There is no user-facing "Tray Lock" setting on these compact printers.** Do not attempt to toggle it in hardware menus.
