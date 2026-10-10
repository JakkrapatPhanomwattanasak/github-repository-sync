# GitHub Repository Sync

[คู่มือภาษาไทย: เรียนตั้งแต่ศูนย์ พร้อม What/Why/How และขั้นตอนลงมือทำ](docs/GUIDE_TH.md)

A command-line automation that retrieves a user's public GitHub repositories, validates the response, and saves a repeatable snapshot to SQLite, CSV, and JSON. It handles pagination, request timeouts, bounded retries, and failure logging without embedding credentials.

## Project preview

[Open the public interactive demo](https://jakkrapat-project-lab.happy-bud-2264.chatgpt.site/#sync)

![Public GitHub repository snapshot retrieved and saved by the Python CLI](docs/images/repository-snapshot.png)

The hosted preview fetches public GitHub repositories live and downloads CSV/JSON. The Python CLI adds validated SQLite snapshots and atomic export replacement. The figure below comes from an actual Python API run, not invented repository activity.

## Run locally

Python 3.11+ (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
# Offline example: no token or network required
.\.venv\Scripts\python.exe -m api_automation.cli --username demo --input examples/github_response.json --output output
# Live public API
.\.venv\Scripts\python.exe -m api_automation.cli --username JakkrapatPhanomwattanasak --output output
```

After activating the environment, `api-sync` is the equivalent command. Add `--dry-run` to fetch and validate without creating output files. An optional `GITHUB_TOKEN` environment variable supplies authentication; it is never printed or written to exports. Do not put tokens in source files or command arguments.

## Behavior

- GET /users/{username}/repos, 100 repositories per page, fixed GitHub host and explicit connect/read timeouts of 5/15 seconds.
- Up to three retries after network failures or HTTP 429/500/502/503/504; exponential backoff, honoring numeric Retry-After up to 30 seconds. Longer waits or exhausted primary limits fail promptly for a later run.
- Invalid JSON/schema, permanent HTTP errors, conflicting IDs, or exceeding `--max-pages` abort **before saving**. Default page limit is 20; configurable up to 100.
- Normalize and deduplicate by repository ID. A transaction replaces only the requested user's snapshot, including removal of repositories no longer returned.
- Repeated runs do not append duplicates. JSON/CSV files are replaced atomically one file at a time; SQLite commits before export. A disk error during export can leave a newer database than an export—rerun to reconcile.
- Exit code 0 means success; 1 means failure. Logs report outcome and counts.

| Output | Contents |
|---|---|
| repositories.db | Latest snapshot per owner, indexed by repository ID |
| repositories.json | Username, fetch timestamp, count, normalized repositories |
| repositories.csv | Flat table for analysis |

Each record contains ID, name, full name, language, star/fork counts, last push timestamp, and GitHub URL. A single output directory is intended for serial runs; simultaneous writers and consistent snapshots during remote repository changes are not guaranteed. Use separate output directories per user if retaining exports for several users.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
```

Tests mock the network and cover pagination, retries, rate limits, malformed responses, schema validation, idempotency, stale-record removal, dry-run, and preservation of earlier output on validation failure. The test suite runs offline.

For periodic use, invoke the CLI from Windows Task Scheduler with an absolute Python path, working directory, and output path. This repo does not install a scheduled task automatically.

[GitHub REST endpoint reference](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user), [API best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api). Study notes: [docs/learning.md](docs/learning.md).

## Optional GitHub Actions CI

[docs/ci.yml](docs/ci.yml) contains a ready-to-use workflow for Python 3.11–3.13. It is a template, not an active workflow. To enable it, copy it to `.github/workflows/ci.yml` using a GitHub credential with workflow write permission. The current publishing credential lacks that permission; local checks were run successfully.
