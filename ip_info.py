#!/usr/bin/env python3
"""
IP Address Information Application
==================================
DEVASC Project Activity 3 - Social Coding (Option 2: IPv4/IPv6 Address Application)

A command-line tool that gives network technicians quick, nicely formatted
information about IP addresses:

  * The computer's current PUBLIC IPv4 and IPv6 address (via the ipify REST API)
  * Geolocation, ISP, ASN, country code and time zone (via the ipapi.co REST API,
    with ip-api.com as an automatic fallback)
  * Lookup of any other IP address
  * Offline analysis of an address (version, private/public, binary, etc.)
  * A subnet calculator (network, broadcast, mask, usable hosts)
  * Exporting the last result to a JSON file

Run interactively:            python ip_info.py
Look up one address and exit: python ip_info.py --lookup 8.8.8.8
Raw JSON output:              python ip_info.py --lookup 8.8.8.8 --json
Disable colours:              python ip_info.py --no-color

Only third-party dependency: requests  (pip install -r requirements.txt)
Everything else is from the Python standard library.
"""

import argparse
import ipaddress
import json
import os
import sys
from datetime import datetime

import requests

# ---------------------------------------------------------------------------
# Configuration - API endpoints (all free, no API key required)
# ---------------------------------------------------------------------------
IPV4_URL = "https://api.ipify.org?format=json"      # returns {"ip": "x.x.x.x"}
IPV6_URL = "https://api6.ipify.org?format=json"     # only answers over IPv6
IPAPI_URL = "https://ipapi.co/{ip}/json/"           # primary details API
IPAPI_SELF_URL = "https://ipapi.co/json/"           # details of the caller's IP
FALLBACK_URL = "http://ip-api.com/json/{ip}"        # backup details API
TIMEOUT = 6                                         # seconds per request


# ---------------------------------------------------------------------------
# Terminal colours (ANSI escape codes - no extra library needed)
# ---------------------------------------------------------------------------
class Color:
    """ANSI colour codes. Call Color.disable() to turn colours off."""
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

    @classmethod
    def disable(cls):
        for name in ("HEADER", "BLUE", "CYAN", "GREEN", "YELLOW", "RED", "BOLD", "END"):
            setattr(cls, name, "")


def colorize(text, color):
    return f"{color}{text}{Color.END}"


# ---------------------------------------------------------------------------
# API layer - every network call lives here so it is easy to test/replace
# ---------------------------------------------------------------------------
def fetch_json(url):
    """GET a URL and return the parsed JSON, or None on any network/JSON error."""
    try:
        response = requests.get(url, timeout=TIMEOUT,
                                headers={"User-Agent": "devasc-ip-info/1.0"})
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def get_public_ipv4():
    """Return the computer's public IPv4 address as a string, or None."""
    data = fetch_json(IPV4_URL)
    return data.get("ip") if data else None


def get_public_ipv6():
    """Return the computer's public IPv6 address, or None if the network has no IPv6."""
    data = fetch_json(IPV6_URL)
    if not data:
        return None
    ip = data.get("ip")
    # Some networks answer the IPv6 endpoint over IPv4 - only accept a real IPv6.
    try:
        return ip if ipaddress.ip_address(ip).version == 6 else None
    except (ValueError, TypeError):
        return None


def normalize_ipapi(data):
    """Convert an ipapi.co response into the app's standard dictionary."""
    return {
        "ip": data.get("ip"),
        "version": data.get("version"),
        "city": data.get("city"),
        "region": data.get("region"),
        "country": data.get("country_name"),
        "country_code": data.get("country_code"),
        "postal": data.get("postal"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timezone": data.get("timezone"),
        "utc_offset": data.get("utc_offset"),
        "isp": data.get("org"),
        "asn": data.get("asn"),
        "source": "ipapi.co",
    }


def normalize_ip_api(data):
    """Convert an ip-api.com response into the app's standard dictionary."""
    asn = (data.get("as") or "").split(" ")[0] or None  # "AS15169 Google LLC" -> "AS15169"
    ip = data.get("query")
    return {
        "ip": ip,
        "version": f"IPv{ipaddress.ip_address(ip).version}" if ip else None,
        "city": data.get("city"),
        "region": data.get("regionName"),
        "country": data.get("country"),
        "country_code": data.get("countryCode"),
        "postal": data.get("zip"),
        "latitude": data.get("lat"),
        "longitude": data.get("lon"),
        "timezone": data.get("timezone"),
        "utc_offset": None,
        "isp": data.get("isp") or data.get("org"),
        "asn": asn,
        "source": "ip-api.com",
    }


def get_ip_details(ip=None):
    """
    Return geolocation/ISP/ASN details for `ip` (or for this computer if ip is None).
    Tries ipapi.co first; if it fails or is rate-limited, falls back to ip-api.com.
    Returns None if both APIs fail.
    """
    primary = fetch_json(IPAPI_URL.format(ip=ip) if ip else IPAPI_SELF_URL)
    if primary and not primary.get("error"):
        return normalize_ipapi(primary)

    backup = fetch_json(FALLBACK_URL.format(ip=ip or ""))
    if backup and backup.get("status") == "success":
        return normalize_ip_api(backup)
    return None


# ---------------------------------------------------------------------------
# Offline helpers (standard-library ipaddress module, no internet needed)
# ---------------------------------------------------------------------------
def classify_ip(ip_obj):
    """Return a human-readable address type for an ipaddress object."""
    if ip_obj.is_loopback:
        return "Loopback"
    if ip_obj.is_link_local:
        return "Link-local"
    if ip_obj.is_multicast:
        return "Multicast"
    if ip_obj.is_private:
        return "Private (not routable on the internet)"
    if ip_obj.is_reserved or ip_obj.is_unspecified:
        return "Reserved / unspecified"
    if ip_obj.is_global:
        return "Public (globally routable)"
    return "Special-purpose"


def analyze_ip(ip_text):
    """Analyse an IP address locally. Raises ValueError if it is not a valid IP."""
    ip_obj = ipaddress.ip_address(ip_text.strip())
    info = {
        "ip": str(ip_obj),
        "version": f"IPv{ip_obj.version}",
        "type": classify_ip(ip_obj),
        "reverse_dns_name": ip_obj.reverse_pointer,
    }
    if ip_obj.version == 4:
        first_octet = int(str(ip_obj).split(".")[0])
        info["class"] = ("A" if first_octet < 128 else "B" if first_octet < 192
                         else "C" if first_octet < 224 else "D (multicast)"
                         if first_octet < 240 else "E (experimental)")
        info["binary"] = ".".join(f"{int(o):08b}" for o in str(ip_obj).split("."))
    else:
        info["compressed"] = ip_obj.compressed
        info["exploded"] = ip_obj.exploded
    return info


def subnet_info(cidr_text):
    """Calculate subnet details from CIDR notation, e.g. 192.168.1.10/24."""
    net = ipaddress.ip_network(cidr_text.strip(), strict=False)
    info = {
        "network": str(net.network_address),
        "prefix_length": f"/{net.prefixlen}",
        "total_addresses": net.num_addresses,
    }
    if net.version == 4:
        usable = net.num_addresses - 2 if net.prefixlen < 31 else net.num_addresses
        hosts = list(net.hosts()) if net.num_addresses <= 2 ** 16 else None
        info.update({
            "subnet_mask": str(net.netmask),
            "wildcard_mask": str(net.hostmask),
            "broadcast": str(net.broadcast_address),
            "first_usable": str(hosts[0]) if hosts else str(net.network_address + 1),
            "last_usable": str(hosts[-1]) if hosts else str(net.broadcast_address - 1),
            "usable_hosts": usable,
        })
    else:
        info["last_address"] = str(net.broadcast_address)
    return info


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
LABELS = {
    "ip": "IP Address", "version": "Version", "city": "City", "region": "Region",
    "country": "Country", "country_code": "Country Code", "postal": "Postal Code",
    "latitude": "Latitude", "longitude": "Longitude", "timezone": "Time Zone",
    "utc_offset": "UTC Offset", "isp": "ISP / Provider", "asn": "ASN",
    "source": "Data Source", "type": "Address Type", "class": "IPv4 Class",
    "binary": "Binary", "compressed": "Compressed", "exploded": "Exploded",
    "reverse_dns_name": "Reverse DNS Name", "network": "Network Address",
    "prefix_length": "Prefix Length", "subnet_mask": "Subnet Mask",
    "wildcard_mask": "Wildcard Mask", "broadcast": "Broadcast Address",
    "first_usable": "First Usable Host", "last_usable": "Last Usable Host",
    "usable_hosts": "Usable Hosts", "total_addresses": "Total Addresses",
    "last_address": "Last Address", "public_ipv4": "Public IPv4",
    "public_ipv6": "Public IPv6",
}


def print_table(title, data):
    """Print a dictionary as a boxed two-column table. Empty values are skipped."""
    rows = [(LABELS.get(k, k), str(v)) for k, v in data.items() if v not in (None, "")]
    if not rows:
        print(colorize("  No data to display.", Color.YELLOW))
        return
    key_w = max(len(k) for k, _ in rows)
    val_w = max(max(len(v) for _, v in rows), len(title) - key_w - 3)
    line = "+" + "-" * (key_w + 2) + "+" + "-" * (val_w + 2) + "+"
    print()
    print(line)
    print("| " + colorize(title.center(key_w + val_w + 3), Color.BOLD + Color.CYAN) + " |")
    print(line)
    for key, val in rows:
        print(f"| {colorize(key.ljust(key_w), Color.YELLOW)} | {val.ljust(val_w)} |")
    print(line)


def print_error(message):
    print(colorize(f"  [!] {message}", Color.RED))


def print_banner():
    print(colorize("=" * 56, Color.BLUE))
    print(colorize("        IP ADDRESS INFORMATION TOOL  (IPv4 / IPv6)", Color.BOLD))
    print(colorize("        DEVASC Project Activity 3 - Option 2", Color.CYAN))
    print(colorize("=" * 56, Color.BLUE))


# ---------------------------------------------------------------------------
# Menu actions - each returns the data it displayed (so it can be exported)
# ---------------------------------------------------------------------------
def action_my_ips():
    print(colorize("  Contacting ipify...", Color.CYAN))
    data = {"public_ipv4": get_public_ipv4() or "Not available",
            "public_ipv6": get_public_ipv6() or "Not available (no IPv6 on this network)"}
    print_table("YOUR PUBLIC IP ADDRESSES", data)
    return data


def action_my_details():
    print(colorize("  Looking up your connection details...", Color.CYAN))
    data = get_ip_details()
    if data is None:
        print_error("Could not reach the IP information APIs. Check your internet connection.")
        return None
    print_table("YOUR CONNECTION DETAILS", data)
    return data


def action_lookup(ip_text):
    try:
        ip_obj = ipaddress.ip_address(ip_text.strip())
    except ValueError:
        print_error(f"'{ip_text}' is not a valid IPv4 or IPv6 address.")
        return None
    if not ip_obj.is_global:
        # Private/reserved addresses have no geolocation - show the local analysis instead.
        print(colorize(f"  {ip_obj} is a {classify_ip(ip_obj).lower()} address - "
                       "showing local analysis instead.", Color.YELLOW))
        return action_analyze(str(ip_obj))
    print(colorize(f"  Looking up {ip_obj}...", Color.CYAN))
    data = get_ip_details(str(ip_obj))
    if data is None:
        print_error("Lookup failed (API unreachable or rate-limited). Try again later.")
        return None
    print_table(f"DETAILS FOR {ip_obj}", data)
    return data


def action_analyze(ip_text):
    try:
        data = analyze_ip(ip_text)
    except ValueError:
        print_error(f"'{ip_text}' is not a valid IPv4 or IPv6 address.")
        return None
    print_table("ADDRESS ANALYSIS", data)
    return data


def action_subnet(cidr_text):
    try:
        data = subnet_info(cidr_text)
    except ValueError:
        print_error(f"'{cidr_text}' is not valid CIDR notation (example: 192.168.1.0/24).")
        return None
    print_table(f"SUBNET {cidr_text.strip()}", data)
    return data


def save_json(data, filename=None):
    """Save a result dictionary to a timestamped JSON file. Returns the file name."""
    filename = filename or f"ip_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"generated": datetime.now().isoformat(timespec="seconds"),
                   "result": data}, f, indent=2)
    return filename


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------
MENU = """
  1. Show my public IPv4 and IPv6 address
  2. Show my full connection details (location, ISP, ASN)
  3. Look up another IP address
  4. Analyze an IP address (offline)
  5. Subnet calculator
  6. Save last result to a JSON file
  0. Exit
"""


def interactive():
    print_banner()
    last_result = None
    while True:
        print(colorize(MENU, Color.GREEN))
        choice = input("  Choose an option: ").strip().lower()
        if choice in ("0", "q", "quit", "exit"):
            print(colorize("  Goodbye!", Color.CYAN))
            break
        elif choice == "1":
            last_result = action_my_ips()
        elif choice == "2":
            last_result = action_my_details() or last_result
        elif choice == "3":
            last_result = action_lookup(input("  Enter an IP address: ")) or last_result
        elif choice == "4":
            last_result = action_analyze(input("  Enter an IP address: ")) or last_result
        elif choice == "5":
            last_result = action_subnet(input("  Enter a network in CIDR (e.g. 10.0.0.0/24): ")) \
                or last_result
        elif choice == "6":
            if last_result:
                print(colorize(f"  Saved to {save_json(last_result)}", Color.GREEN))
            else:
                print_error("Nothing to save yet - run another option first.")
        else:
            print_error("Invalid option. Please enter a number from the menu.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Public IPv4/IPv6 address information tool")
    parser.add_argument("--lookup", metavar="IP", help="look up one IP address and exit "
                        "(use 'me' for your own connection)")
    parser.add_argument("--json", action="store_true", help="print raw JSON instead of a table")
    parser.add_argument("--no-color", action="store_true", help="disable coloured output")
    args = parser.parse_args(argv)

    if args.no_color or not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        Color.disable()

    if args.lookup:
        if args.lookup.lower() == "me":
            data = get_ip_details()
        else:
            try:
                ipaddress.ip_address(args.lookup)
            except ValueError:
                print_error(f"'{args.lookup}' is not a valid IP address.")
                return 1
            data = get_ip_details(args.lookup)
        if data is None:
            print_error("Lookup failed.")
            return 1
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print_table(f"DETAILS FOR {data.get('ip')}", data)
        return 0

    try:
        interactive()
    except (KeyboardInterrupt, EOFError):
        print(colorize("\n  Goodbye!", Color.CYAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
