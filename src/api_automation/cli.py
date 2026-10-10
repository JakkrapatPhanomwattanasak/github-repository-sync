import argparse
import json
import logging
import os
import sqlite3
from pathlib import Path

from .client import GitHubClient, SyncError, validate_username
from .storage import normalize, save_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sync public GitHub repositories into SQLite, CSV, and JSON"
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--input", type=Path, help="Use an offline GitHub-response JSON fixture")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch and validate without writing files"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        validate_username(args.username)
        if args.input:
            payload = json.loads(args.input.read_text(encoding="utf-8"))
        else:
            client = GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
            try:
                payload = client.fetch_repositories(args.username, args.max_pages)
            finally:
                client.close()
        records = normalize(payload, args.username)
        if not args.dry_run:
            save_snapshot(records, args.username, args.output)
        logging.info(
            "%s %s repositories for %s",
            "Validated" if args.dry_run else "Saved",
            len(records),
            args.username,
        )
    except (SyncError, OSError, ValueError, sqlite3.Error) as error:
        logging.error("Sync failed: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
