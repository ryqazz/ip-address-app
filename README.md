# IP Address Information Tool (IPv4 / IPv6)

**DEVASC Project Activity 3 – Social Coding, Option 2: New Application**
System Integration · Team members: Daniel De Dios, [Member 2], [Member 3]

A Python command-line application that gives network technicians formatted information
about their current public IP addresses and any other IP address, using free public REST APIs.

## Features

| # | Feature | How it works |
|---|---------|--------------|
| 1 | Show public IPv4 **and** IPv6 address | `api.ipify.org` and `api6.ipify.org` REST APIs |
| 2 | Full connection details: city, region, country, country code, coordinates, time zone, **ISP**, **ASN** | `ipapi.co` REST API |
| 3 | Look up any other IP address (private addresses are detected and analysed locally instead) | `ipapi.co`, with input validation |
| 4 | Offline address analysis: version, public/private/loopback/multicast, IPv4 class, binary form, IPv6 compressed/exploded, reverse-DNS name | Python `ipaddress` module |
| 5 | Subnet calculator: network, mask, wildcard, broadcast, first/last usable host, host count | Python `ipaddress` module |
| 6 | Export the last result to a timestamped JSON file | `json` module |
| – | Automatic fallback API if `ipapi.co` is down or rate-limited | `ip-api.com` |
| – | Coloured, boxed table output (disable with `--no-color`) | ANSI escape codes |
| – | Command-line mode for scripting (`--lookup`, `--json`) | `argparse` |

## Installation

Requires Python 3.8+.

```bash
git clone <your-repo-url>
cd ip-address-app
pip install -r requirements.txt
```

## Usage

```bash
python ip_info.py                         # interactive menu
python ip_info.py --lookup 8.8.8.8        # one lookup, formatted table
python ip_info.py --lookup me --json      # your own details as raw JSON
python ip_info.py --no-color              # plain output (e.g. for Windows cmd)
```

Sample output:

```
+----------------+---------------------+
|         DETAILS FOR 8.8.8.8          |
+----------------+---------------------+
| IP Address     | 8.8.8.8             |
| Country        | United States       |
| Country Code   | US                  |
| ISP / Provider | GOOGLE              |
| ASN            | AS15169             |
| Data Source    | ipapi.co            |
+----------------+---------------------+
```

## Running the tests

```bash
python -m unittest -v
```

The 14 unit tests mock every network call, so they run without internet access.

## Code structure (for teams continuing the project)

`ip_info.py` is organised in layers, top to bottom:

1. **Configuration** – API URLs and timeout. Change an endpoint here only.
2. **`Color`** – ANSI colour codes; `Color.disable()` turns them off.
3. **API layer** – `fetch_json()` is the *only* function that touches the network.
   `get_public_ipv4()`, `get_public_ipv6()` and `get_ip_details()` build on it.
   Each API's response is converted to one standard dictionary by
   `normalize_ipapi()` / `normalize_ip_api()`, so the rest of the app does not care which API answered.
4. **Offline helpers** – `classify_ip()`, `analyze_ip()`, `subnet_info()`.
5. **Output** – `print_table()` prints any dictionary as a table; field names come from `LABELS`.
6. **Menu actions** – one `action_*()` function per menu item; each returns the data it showed so it can be exported.
7. **`interactive()` and `main()`** – the menu loop and command-line arguments.

**To add a new feature:** write an `action_*()` function, add a line to `MENU`, add a branch in
`interactive()`, add any new field names to `LABELS`, and add a unit test in `test_ip_info.py`.

**To add another API:** write a `normalize_*()` function that returns the standard dictionary keys
and add it to the fallback chain in `get_ip_details()`.

## API notes and limits

- `ipapi.co` free tier: about 1,000 requests/day, no key needed. It returns `{"error": true}` when rate-limited – the app then switches to `ip-api.com` automatically.
- `ip-api.com` free tier uses plain HTTP and allows 45 requests/minute.
- `api6.ipify.org` only answers over IPv6; on IPv4-only networks the app shows "Not available".

## Git workflow

- `main` – stable, reviewed code only. Protected: changes arrive through pull requests.
- `feature/<name>` – one branch per feature/member (e.g. `feature/api-layer`, `feature/subnet-calculator`).
- Every pull request needs one reviewer's approval and passing tests before merge.

## Backlog (future enhancements – Project Activity 4)

See the presentation / rubric for the prioritised list: GUI or web dashboard, map link for coordinates,
batch lookup from a file, ping/traceroute, reverse DNS hostname lookup, WHOIS, history log, VPN/proxy detection, CSV export.
