#!usr/bin/env python3

from __future__ import annotations

import os
import json
import sys
import typing
import requests
import re
import time
import gzip
import mmap
import shutil

import email.message as emsg
import datetime      as dt

from platformdirs import user_config_dir, user_data_dir, user_cache_dir
from pathlib      import Path
from typing       import NoReturn

TOKEN: str | None = None  # access token

CONFIG_DIR: Path = Path(user_config_dir("czdscli"))
DATA_DIR:   Path = Path(user_data_dir  ("czdscli"))
CACHE_DIR:  Path = Path(user_cache_dir ("czdscli"))

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR  .mkdir(parents=True, exist_ok=True)
CACHE_DIR .mkdir(parents=True, exist_ok=True)

CONFIG_FILE: Path = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: dict = {
  "icann.account.username": "username@example.com",
  "icann.account.password": "Abcdef#12345678",
  "authentication.base.url": "https://account-api.icann.org",
  "czds.base.url": "https://czds-api.icann.org",
  "working.directory": "/where/zonefiles/will/be/saved",
  "tlds": []
}

# loads default config
if not CONFIG_FILE.exists() or CONFIG_FILE.stat().st_size == 0:
    f = CONFIG_FILE.open("w", encoding="utf-8")
    json.dump(DEFAULT_CONFIG, f, indent=2); f.close()


try:  # load config file
    if "CZDS_CONFIG" in os.environ:
        CONFIG: dict = json.loads(os.environ["CZDS_CONFIG"])
    
    else:
        f = CONFIG_FILE.open("r", encoding="utf-8")
        CONFIG: dict = json.load(f); f.close()

except Exception as e:
    sys.stderr.write(f"Error loading config.json file: {e}\n")
    sys.exit(1)


USERNAME: str        = CONFIG.get("icann.account.username")
PASSWORD: str        = CONFIG.get("icann.account.password")
AUTHEN_BASE_URL: str = CONFIG.get("authentication.base.url")
CZDS_BASE_URL: str   = CONFIG.get("czds.base.url")
TLDS: list           = CONFIG.get("tlds", [])

WORKING_DIR: Path = Path(
    CONFIG.get("working.directory", DATA_DIR)
)
DATA_DIR = WORKING_DIR if WORKING_DIR.exists() else DATA_DIR


if not AUTHEN_BASE_URL:
    sys.stderr.write(
        "'authentication.base.url' parameter not found in the config.json file\n"
    ); exit(1)

if not CZDS_BASE_URL:
    sys.stderr.write(
        "'czds.base.url' parameter not found in the config.json file\n"
    ); exit(1)


def _get_token(username: str, password: str) -> str | NoReturn:
    url: str = f"{AUTHEN_BASE_URL}/api/authenticate"

    r: requests.Response = requests.post(url, json={
        "username": username, "password": password
    })

    r.raise_for_status()

    token: str = r.json().get("accessToken")
    if token: return token
    
    raise RuntimeError(
        f"[{r.status_code}] Authentication failed."
    )


def _get_zone_links(token: str) -> list[str] | NoReturn:
    url: str = f"{CZDS_BASE_URL}/czds/downloads/links"

    r: requests.Response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"}
    )

    r.raise_for_status()
    return r.json()


def _cooldown_file(tld: str) -> Path:
    return CACHE_DIR / f"{tld}.cooldown"


def _cooldown_ok(tld: str) -> bool:
    f: Path = _cooldown_file(tld)

    if not f.exists(): return True

    ts: float = float(f.read_text())
    return (time.time() - ts) >= 86400  # 24h


def _set_cooldown(tld: str) -> None:
    f: Path = _cooldown_file(tld)
    f.write_text(str(time.time()))


def _download_file(url: str, token: str, output_dir: Path) -> Path:

    r: requests.Response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        stream=True
    )

    r.raise_for_status()

    cd = r.headers.get("Content-Disposition", "")
    msg = emsg.Message()
    msg["Content-Disposition"] = cd
    filename = msg.get_param("filename", header="Content-Disposition")

    if not filename:
        filename = url.split("/")[-1]

    path: Path = output_dir / filename

    total: int = int(r.headers.get("Content-Length", 0))
    downloaded: int = 0

    chunk_size: int = 1024 * 1024  # 1 MB

    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size):
            if not chunk: continue

            f.write(chunk)
            downloaded += len(chunk)

            if total > 0:
                percent: float = downloaded / total * 100
                mb_done: float = downloaded / (1024 * 1024)
                mb_total: float = total / (1024 * 1024)

                sys.stdout.write(
                    f"\r{percent:6.2f}%  {mb_done:,.1f}/{mb_total:,.1f} MB"
                )
                sys.stdout.flush()

    sys.stdout.write("\n")
    return path


def gunzip(path: pathlib.Path) -> pathlib.Path:
    print("Unpacking .txt.gz file...")

    if path.suffix != ".gz":
        raise ValueError("File must end with .gz")

    outpath: pathlib.Path = path.with_suffix("")  # removes .gz

    with gzip.open(path, "rb") as f_in, open(outpath, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out, length=16 * 1024 * 1024)

    path.unlink()  # remove original .gz

    return outpath


def download(**kwargs) -> None | NoReturn:
    username: str = kwargs.get("username") or USERNAME
    password: str = kwargs.get("password") or PASSWORD

    zone_arg:  str = kwargs.get("zone")
    ignore_cd: str = kwargs.get("ignore_cooldown")

    output_dir: Path = Path(kwargs.get("output_dir") or DATA_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not username or not password:
        sys.stderr.write("Username/password required\n")
        sys.exit(1)

    token: str = _get_token(username, password)
    links: list[str] = _get_zone_links(token)

    wanted_zones: list | None = None
    if zone_arg:
        wanted_zones = [
            z.strip().lstrip(".") for z in zone_arg.split(",")
        ]
    elif TLDS:
        wanted_zones = [
            z.strip().lstrip(".") for z in TLDS
        ]

    for url in links:

        _match: re.Match = re.search(
            r"/downloads/([a-z0-9-]+)\.zone", url
        )
        if not _match: continue

        tld: str = _match.group(1)

        if wanted_zones and tld not in wanted_zones:
            continue

        if not ignore_cd and not _cooldown_ok(tld):
            print(f"{tld}: cooldown active (24h)")
            continue

        print(f"Downloading .{tld.upper()} zone files...")

        gz_path: Path = _download_file(url, token, output_dir)
        _set_cooldown(tld)

        if not kwargs.get("no_gunzip"):
            txt_path: Path = gunzip(gz_path)
            print(f".{tld.upper()}: extracted -> {txt_path.name}")

        print(f"DONE!")


class Searcher(object):

    def __init__(self, zones_dir: Path | None = None) -> None:
        self.zones_dir: Path = zones_dir if zones_dir else DATA_DIR
        self._handles: dict[str, tuple] = {}

    def _open_zone(self, zone: str) -> tuple:
        if zone in self._handles: return self._handles[zone]

        candidates = [
            self.zones_dir / f"{zone}.zone",
            self.zones_dir / f"{zone}",
            self.zones_dir / f"{zone}.txt",
        ]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            raise FileNotFoundError(f"Zone file for '{zone}' not found in {self.zones_dir}")

        f = path.open("rb")
        try:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        except Exception:
            f.close()
            raise

        size = mm.size()
        self._handles[zone] = (f, mm, size)
        return self._handles[zone]

    def _available_zones(self) -> list[str]:
        zones: list = []
        valid_suffixes = (".zone", ".txt")
        for p in self.zones_dir.iterdir():
            if not p.is_file(): continue

            if not any(
                p.name.endswith(s) for s in valid_suffixes
            ) and "." in p.name:
                continue 

            name: str = p.name
            for suffix in valid_suffixes:
                if name.endswith(suffix):
                    name = name[: -len(suffix)]; break
            zones.append(name)
        return zones

    def _extract_domain_from_line(self, line: bytes) -> bytes:
        tab = line.find(b"\t")
        return line[:tab] if tab != -1 else line.split(b" ")[0]

    def _read_line_at(self, mm: mmap.mmap, size: int, mid: int) -> tuple[bytes, int, int]:
        """Return (line, start, end) for the line containing position mid."""
        start: int = mm.rfind(b"\n", 0, mid) + 1
        end: int = mm.find(b"\n", mid)
        if end == -1: end = size
        return mm[start:end], start, end

    def _collect_all_domain_lines(
        self, mm: mmap.mmap, size: int, target: bytes, anchor_start: int, anchor_end: int
    ) -> list[bytes]:
        """Given a confirmed match at anchor, collect all lines with the same domain."""
        results: list[bytes] = [mm[anchor_start:anchor_end]]

        # Scan backward
        pos: int = anchor_start - 1
        while pos > 0:
            line, start, end = self._read_line_at(mm, size, pos)
            if self._extract_domain_from_line(line) == target:
                results.insert(0, line)
                pos = start - 1
            else:
                break

        # Scan forward
        pos = anchor_end + 1
        while pos < size:
            end: int = mm.find(b"\n", pos)
            if end == -1: end = size
            line = mm[pos:end]
            if self._extract_domain_from_line(line) == target:
                results.append(line)
                pos = end + 1
            else:
                break

        return results

    def _exact_binary_search(
        self, mm: mmap.mmap, size: int, target: bytes
    ) -> list[bytes]:
        left, right = 0, size

        while left < right:
            mid: int = (left + right) // 2
            line, start, end = self._read_line_at(mm, size, mid)
            domain: bytes = self._extract_domain_from_line(line)

            if domain == target:
                return self._collect_all_domain_lines(mm, size, target, start, end)
            elif domain < target:
                left = end + 1
            else:
                right = start

        return []  # no match

    def _substring_search(
        self, mm: mmap.mmap, size: int, target: bytes
    ) -> list[bytes]:
        """
        Binary search to find the first line whose domain >= target,
        then linear scan forward collecting all lines whose domain contains target.
        No full file reads — scans only until domains sort past any possible match.
        """
        results: list[bytes] = []

        # Find insertion point
        left, right = 0, size
        while left < right:
            mid: int = (left + right) // 2
            line, start, end = self._read_line_at(mm, size, mid)
            domain: bytes = self._extract_domain_from_line(line)
            if domain < target:
                left = end + 1
            else:
                right = start

        # Scan backward a bit — target could be a suffix match before the insertion point
        # e.g. searching "google" could match "1google.com." which sorts before "google.com."
        # Walk back up to 500 lines to catch prefix-of-insertion-point suffix matches
        scan_start: int = left
        pos: int = left - 1
        steps: int = 0
        while pos > 0 and steps < 500:
            line, start, end = self._read_line_at(mm, size, pos)
            domain: bytes = self._extract_domain_from_line(line)
            if target in domain:
                scan_start = start
            pos = start - 1
            steps += 1

        # Full forward scan from scan_start
        seen: set[bytes] = set()
        pos = scan_start
        while pos < size:
            end: int = mm.find(b"\n", pos)
            if end == -1: end = size
            line: bytes = mm[pos:end]
            domain: bytes = self._extract_domain_from_line(line)

            if target in domain:
                if line not in seen:
                    results.append(line)
                    seen.add(line)
            pos = end + 1

        return results

    def _binary_search(
        self, mm: mmap.mmap, size: int, target: bytes, exact: bool
    ) -> list[bytes]:
        if exact:
            return self._exact_binary_search(mm, size, target)
        else:
            return self._substring_search(mm, size, target)

    def search(self, query: str, **kwargs) -> list[str]:
        target: bytes    = query.lower().encode("ascii")
        exact: bool      = kwargs.get("exact", False)
        whole_line: bool = kwargs.get("line", False)
        flagged: bool    = kwargs.get("flagged", False)
        zone: str | None = kwargs.get("zone", None)

        if exact and not target.endswith(b"."):
            target = target + b"."

        zones_to_search: list = (
            [z.strip().lstrip(".") for z in zone.split(",")]
            if zone else
            self._available_zones()
        )
        results: list = []
        found_any: bool = False  # track if ANY zone returned a match

        for z in zones_to_search:
            try:
                file_handle, mm, size = self._open_zone(z)
            except FileNotFoundError as e:
                sys.stderr.write(f"{e}\n")
                continue

            matches: list = self._binary_search(mm, size, target, exact)

            if matches:
                found_any = True

            for line in matches:
                try:
                    decoded: str = line.decode("ascii").strip()
                except UnicodeDecodeError:
                    decoded: str = line.decode("latin-1").strip()

                text: str = decoded if whole_line else decoded.split("\t")[0].split(" ")[0].rstrip(".")

                if flagged:
                    text = f"{text},unavailable"

                results.append(text)

        seen: set = set()
        deduped: list = []
        for r in results:
            if r not in seen:
                seen.add(r); deduped.append(r)

        # Only emit available ONCE, after checking all zones
        if flagged and not found_any:
            deduped.append(f"{query},available")

        return deduped

    def close(self) -> None:
        for f, mm, _ in self._handles.values():
            mm.close(); f.close()
        self._handles.clear()

    def __enter__(self) -> Searcher:
        return self

    def __exit__(self, *args) -> None:
        self.close()