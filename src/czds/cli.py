#!usr/bin/env python3
# Command Line Interface

from __future__ import annotations

import click
import sys


@click.group(name="cli")
def cli(**kwargs) -> None:

    ...


@cli.command(
    name="download",
    epilog=(
        """
        The USERNAME and PASSWORD arguments are optional if they are already defined in the
        configuration file.\n
        The ZONE argument, if missing or empty, means downloading all APPROVED tlds. You can
        also specify the default tlds at the config file. For more than one zone at a time
        use comma separated values. --zone='.com, .org, .net'\n
        The IGNORE COOLDOWN flag allows the user to download zone files even if the 24-hour
        cooldown period has not elapsed. Using this option violates the Centralized Zone Data
        Service (CZDS) terms and conditions. Misuse may result in revocation of access to
        specific zones or suspension of the associated account. Use at your own risk.\n
        """
        )
    )
@click.option("--username", "-u", required=False, help="ICANN.org username.")
@click.option("--password", "-p", required=False, help="ICANN.org password.")
@click.option("--zone", "-z", help="Specify wanted zone. More info below.")
@click.option("--output-dir", "-o", type=click.Path(), help="Specify output directory.")
@click.option("--no-gunzip", "-G", is_flag=True, help="Skip .txt.gz unziping.")
@click.option("--ignore-cooldown", is_flag=True, help="[!] Ignore 24h cooldown. More info below.")
@click.option("--aria2c", is_flag=True, help="Use aria2c for downloading.")
def download(**kwargs) -> None:
    """
    Download Zone Files.
    """
    from .main import download
    download(**kwargs)


@cli.command(
    name="search",
    epilog=(
        """
        Non EXACT searches are slow, and the output might be huge. It is
        recomended to run it with tee: czds search <QUERY> | tee -a out.txt\n
        The ZONE argument, if missing or empty, means search in all zone files.
        For more than one zone at a time use comma separated values.
        --zone='.com, .org, .net'\n
        """
        )
    )
@click.argument("query", required=False) # supports stdin
@click.option("--zone", "-z", help="Specify wanted zone. More info below.")
@click.option("--exact", "-x", is_flag=True, help="Exact match only.")
@click.option("--line", "-l", is_flag=True, help="Out whole line.")
@click.option("--flagged", "-f", is_flag=True, help="Flag results [available|unavailable]")
@click.option("--available", "-A", is_flag=True, help="Out only available domains.")
@click.option("--unavailable", "-U", is_flag=True, help="Out only unavailable domains.")
@click.option("--zones-dir", type=click.Path(), help="Specify zones directory.")
def search(**kwargs) -> None:
    """Search for <QUERY> in <ZONE>"""

    from .main import Searcher

    query = kwargs.get("query")
    only_available   = kwargs.get("available", False)
    only_unavailable = kwargs.get("unavailable", False)

    flagged = kwargs.get("flagged", False) or only_available or only_unavailable

    if not query:
        if not sys.stdin.isatty():
            queries = [line.strip() for line in sys.stdin if line.strip()]
        else:
            raise click.UsageError(
                "Missing argument 'QUERY' and no stdin detected."
            )
    else:
        queries = [query]

    with Searcher(kwargs.get("zones_dir")) as searcher:
        for q in queries:
            results: list = searcher.search(
                query=q,
                zone=kwargs.get("zone", None),
                exact=kwargs.get("exact", False),
                line=kwargs.get("line", False),
                flagged=flagged,
            )
            for r in results:
                if only_available and not r.endswith(",available"): continue
                if only_unavailable and not r.endswith(",unavailable"): continue
                if not kwargs.get("flagged", False): r = r.rsplit(",", 1)[0]
                click.echo(r)


@cli.command(name="getpath", hidden=True)
@click.option(
    "-x", show_choices=True,
    type=click.Choice(["data", "cache", "config", "all"]),
    default="all",
    help="Path to display. Defaults to 'all'."
    )
def getpath(**kwargs) -> None:
    """Get default paths."""
    from .main import DATA_DIR, CACHE_DIR, CONFIG_DIR

    x: str = kwargs.get("x")

    if x == "data": print(f"{DATA_DIR._raw_path}")
    if x == "cache": print(f"{CACHE_DIR._raw_path}")
    if x == "config": print(f"{CONFIG_DIR._raw_path}")

    if x == "all":
        print(f"Config dir:  {CONFIG_DIR._raw_path}")
        print(f"Data dir:    {DATA_DIR._raw_path}")
        print(f"Cache dir:   {CACHE_DIR._raw_path}")