import csv
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .client import SyncError, validate_username

FIELDS = ["id", "name", "full_name", "language", "stars", "forks", "pushed_at", "url"]


def normalize(payload, username):
    validate_username(username)
    if not isinstance(payload, list):
        raise SyncError("Input must be a JSON list")
    records = {}
    for item in payload:
        if not isinstance(item, dict):
            raise SyncError("Each repository must be an object")
        for field in ("id", "stargazers_count", "forks_count"):
            value = item.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < (1 if field == "id" else 0)
            ):
                raise SyncError(f"Repository {field} must be a valid non-negative integer")
        name = item.get("name")
        full_name = item.get("full_name")
        if not isinstance(name, str) or not name or not isinstance(full_name, str):
            raise SyncError("Repository name and full_name are required")
        if full_name.lower() != f"{username}/{name}".lower():
            raise SyncError("Repository owner does not match the requested username")
        language = item.get("language")
        pushed_at = item.get("pushed_at")
        url = item.get("html_url")
        if language is not None and not isinstance(language, str):
            raise SyncError("language must be a string or null")
        if pushed_at is not None:
            try:
                datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError, TypeError):
                raise SyncError("pushed_at must be an ISO timestamp or null") from None
        if not isinstance(url, str) or url.lower() != f"https://github.com/{full_name}".lower():
            raise SyncError("Repository URL must match its GitHub full_name")
        record = {
            "id": item["id"],
            "name": name,
            "full_name": full_name,
            "language": language,
            "stars": item["stargazers_count"],
            "forks": item["forks_count"],
            "pushed_at": pushed_at,
            "url": url,
        }
        if record["id"] in records and records[record["id"]] != record:
            raise SyncError("Conflicting duplicate repository ID; retry the snapshot")
        records[record["id"]] = record
    return sorted(records.values(), key=lambda row: row["full_name"].lower())


def _atomic_write(path, write):
    """Write a complete export before replacing the previous one, including on Windows."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            write(handle)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_snapshot(records, username, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(output / "repositories.db")
    try:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    id INTEGER PRIMARY KEY, owner TEXT NOT NULL,
                    name TEXT NOT NULL, full_name TEXT NOT NULL, language TEXT,
                    stars INTEGER NOT NULL, forks INTEGER NOT NULL,
                    pushed_at TEXT, url TEXT NOT NULL, fetched_at TEXT NOT NULL
                )
            """)
            # Replace only this user's complete snapshot, removing repositories no longer public.
            connection.execute("DELETE FROM repositories WHERE owner = ?", (username.lower(),))
            connection.executemany(
                "INSERT INTO repositories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        row["id"],
                        username.lower(),
                        row["name"],
                        row["full_name"],
                        row["language"],
                        row["stars"],
                        row["forks"],
                        row["pushed_at"],
                        row["url"],
                        fetched_at,
                    )
                    for row in records
                ],
            )
    finally:
        connection.close()
    snapshot = {
        "username": username,
        "fetched_at": fetched_at,
        "count": len(records),
        "repositories": records,
    }
    _atomic_write(
        output / "repositories.json", lambda handle: json.dump(snapshot, handle, indent=2)
    )

    def write_csv(handle):
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)

    _atomic_write(output / "repositories.csv", write_csv)
    return snapshot
