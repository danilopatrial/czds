# CZDS Command Line Interface

> A simple CLI for downloading and searching ICANN Centralized Zone Data Service (CZDS) zone files.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![pipx](https://img.shields.io/badge/install%20with-pipx-orange)](https://pypa.github.io/pipx/)

---

## Overview

**CZDS-CLI** is a tool for interacting with ICANN's [Centralized Zone Data Service](https://czds.icann.org). It allows you to:

- **Download** approved TLD zone files directly from the CZDS API
- **Search** downloaded zone files at high speed using memory-mapped binary search
- Pipe queries in bulk via `stdin` for scripted workflows

---

## Requirements

- Python **3.10** or higher
- An approved [ICANN CZDS account](https://czds.icann.org/home), for downloading zone files.
- [`pipx`](https://pypa.github.io/pipx/) (recommended) or `pip`

---

## Installation

### With pipx (recommended)

[`pipx`](https://pypa.github.io/pipx/) installs CLI tools in isolated environments, keeping your system Python clean.

```bash
# Install pipx if you don't have it
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install CZDS
pipx install czds
```

### From source

```bash
git clone https://github.com/youruser/czds.git
cd czds
pipx install .
```

### Verify installation

```bash
czds --help
```

---

## Configuration

On first run, the CLI auto-generates a configuration file at the platform-appropriate config directory:

| Platform | Path |
|----------|------|
| Linux    | `~/.config/czdscli/config.json` |
| macOS    | `~/Library/Application Support/czdscli/config.json` |
| Windows  | `%APPDATA%\czdscli\config.json` |

Run `czds getpath -x config` to print the exact path on your system.

### `config.json`

```json
{
  "icann.account.username": "username@example.com",
  "icann.account.password": "Abcdef#12345678",
  "authentication.base.url": "https://account-api.icann.org",
  "czds.base.url": "https://czds-api.icann.org",
  "working.directory": "/where/zonefiles/will/be/saved",
  "tlds": []
}
```

| Key | Description |
|-----|-------------|
| `icann.account.username` | Your ICANN CZDS account email |
| `icann.account.password` | Your ICANN CZDS account password |
| `authentication.base.url` | ICANN authentication API base URL (do not change) |
| `czds.base.url` | CZDS API base URL (do not change) |
| `working.directory` | Directory where downloaded zone files are stored |
| `tlds` | Default list of TLDs to download, e.g. `["com", "net", "org"]`. Leave empty `[]` to download all approved zones |

### Environment variable override

You can override the config file entirely by setting the `CZDS_CONFIG` environment variable to a JSON string:

```bash
export CZDS_CONFIG='{"icann.account.username":"me@example.com","icann.account.password":"secret",...}'
czds download --zone com
```

---

## Commands

### `download`

Download zone files from the CZDS API for approved TLDs.

```
czds download [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--username TEXT` | `-u` | ICANN account username (overrides config) |
| `--password TEXT` | `-p` | ICANN account password (overrides config) |
| `--zone TEXT` | `-z` | Comma-separated TLDs to download, e.g. `com,net,org` |
| `--output-dir PATH` | `-o` | Directory to save zone files (overrides config) |
| `--no-gunzip` | `-G` | Skip automatic decompression of `.gz` files |
| `--ignore-cooldown` | | ⚠️ Bypass the 24-hour download cooldown (see warning below) |

**Notes:**
- If `--zone` is omitted and `tlds` is empty in config, **all approved zones** will be downloaded.
- Downloads are automatically decompressed from `.txt.gz` to `.txt` unless `--no-gunzip` is set.
- A **24-hour cooldown** per TLD is enforced by default to comply with CZDS terms of service.

---

### `search`

Search for a domain across all downloaded zone files.

```
czds search [OPTIONS] [QUERY]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--zone TEXT` | `-z` | Limit search to specific zone(s), e.g. `com` or `com,net,org` |
| `--exact` | `-x` | Exact match only (default is substring) |
| `--line` | `-l` | Output the full zone record line instead of just the domain |
| `--flagged` | `-f` | Tag each result as `available` or `unavailable` |
| `--available` | `-A` | Output only domains that are **not registered** |
| `--unavailable` | `-U` | Output only domains that **are registered** |
| `--zones-dir PATH` | | Override the zone files directory |

**`QUERY`** is optional — if omitted, `stdin` is read automatically, enabling bulk lookups via pipes.

---

## Search Flags Reference

### Default (substring) vs `--exact`

By default, searching for `google.com` will match **any domain containing that string**:

```
1google.com
google.com
googleplex.com
notgoogle.com
```

With `--exact` / `-x`, only the precise domain matches:

```
google.com
```

### `--line` / `-l`

Without `--line`, only the domain name is returned:

```
google.com
```

With `--line`, the complete zone record is returned:

```
google.com.    172800    in    ns    ns1.google.com.
google.com.    172800    in    ns    ns2.google.com.
```

### `--flagged` / `-f`

Tags each result with its registration status:

```
google.com,unavailable
missing-domain.com,available
```

### `--available` / `-A` and `--unavailable` / `-U`

Filters output to only one status. The flag tag is **omitted** from output when using `-A` or `-U` without `-f`:

```bash
# Only show unregistered domains (clean output, no tag)
cat domains.txt | czds search -x -A

# Only show registered domains with tag
cat domains.txt | czds search -x -U -f
```

> **⚠️ Availability is not guaranteed.** A domain not found in a zone file is not
> necessarily available for registration. Zone files only contain domains with
> active DNS delegations — domains that are registered but have no nameservers
> configured will not appear. Always verify availability through an official
> registrar or WHOIS before acting on results.

---

## Usage Examples

### Download zone files

```bash
# Download all approved zone files
czds download

# Download specific zones
czds download --zone com,net,org

# Download to a custom directory
czds download --zone com --output-dir /data/zones

# Download with credentials inline (overrides config)
czds download -u me@example.com -p MyPassword --zone com
```

### Search a single domain

```bash
# Substring search across all zones
czds search google

# Exact match in the .com zone only
czds search -x -z com google.com

# Return full zone record lines
czds search -x -l -z com google.com

# Check if a domain is available
czds search -x -f google.com
# -> google.com,unavailable

czds search -x -f totallyfree123456.com
# -> totallyfree123456.com,available
```

### Bulk lookups via stdin

```bash
# Check a list of domains for availability
cat domains.txt | czds search --exact --flagged

# Show only available domains from a list (no tag in output)
cat domains.txt | czds search -x -A

# Show only taken domains with full record lines
cat domains.txt | czds search -x -U -l

# Pipe from another command
echo "github.com" | czds search -x -z com
```

### Domain availability checker workflow

```bash
# Generate candidate domains, check availability, save available ones
cat candidates.txt | czds search -x -A > available.txt
echo "Found $(wc -l < available.txt) available domains."
```

### Search across multiple specific zones

```bash
# Search in .com, .net, and .org simultaneously
czds search -x google.com -z "com, net, org"
```

---

## How It Works

### Download

The CLI authenticates against the ICANN API, fetches your list of approved zone file URLs, and streams each file with a live progress indicator. Files are automatically decompressed from `.txt.gz` format on download.

A per-TLD cooldown timestamp is written to the cache directory after each download. Re-downloading within 24 hours is blocked by default to respect CZDS rate limits.

### Search

Zone files are sorted lexicographically by domain name, which makes them suitable for binary search. The CLI uses Python's `mmap` module to map zone files directly into virtual memory — no file is ever fully loaded into the memory.

**Exact search** runs a pure O(log n) binary search, landing on the target domain in ~30 comparisons regardless of file size, then scans adjacent lines to collect all records for that domain (e.g. multiple NS entries).

**Substring search** uses binary search to find the approximate insertion point, walks back a window of lines to catch domains that sort before the target (e.g. `1google.com` when searching `google`), then scans forward collecting all substring matches.

Results are deduplicated and returned in file order.

---

## File Structure

```
~/.config/czdscli/
└── config.json          # credentials and settings

~/.local/share/czdscli/  # (or working.directory from config)
├── com.zone             # downloaded zone files
├── net.zone
├── org.zone
└── ...

~/.cache/czdscli/
├── com.cooldown         # per-TLD download timestamps
├── net.cooldown
└── ...
```

---

## Caveats & Terms of Service

- **CZDS access requires approval** — you must apply for access to each TLD's zone file via [czds.icann.org](https://czds.icann.org).
- ⚠️ **Zone files are licensed data** — usage is subject to [ICANN's CZDS Terms and Conditions](https://czds.icann.org/help/tac). Do not redistribute zone file contents.
- ⚠️ **`--ignore-cooldown` is a ToS violation** — bypassing the 24-hour cooldown violates CZDS terms of service and may result in access revocation or account suspension. Use at your own risk.
- **Zone files update daily** — ICANN begins collecting zone files from registry operators at **00:00 UTC**, and the process takes up to 6 hours, meaning fresh files are available for download after **06:00 UTC**.  Schedule your downloads after that window to ensure you always get the latest data. The built-in 24-hour cooldown aligns with this cadence automatically.
---

## License

MIT — see [LICENSE](LICENSE) for details.
