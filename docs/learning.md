# Understanding GitHub Repository Sync

- Entry point: `api_automation.cli.main`; HTTP behavior lives in `client.py`, validation/persistence in `storage.py`.
- Explain pagination, bounded retries, connect/read timeouts, exponential backoff, and HTTP status classification.
- Why stop at the pagination limit? Saving a partial response could remove valid data from the previous snapshot.
- Why validate all records before persistence? Network success is not sufficient to guarantee valid input.
- Explain idempotency: repeated complete snapshots replace records without accumulating duplicates.
- Explain the distinction between a database transaction and atomic per-file export replacement.
- Explain dry-run, exit codes, logs, environment-based secrets, and scheduling a CLI externally.

Practice: run the offline fixture twice, inspect SQLite row counts, use dry-run, run the live public API, then read the mocked retry test.

Resume wording after you can reproduce and explain the implementation:
"Built a Python GitHub API synchronization CLI with pagination, bounded retries, response validation, idempotent SQLite snapshots, and CSV/JSON exports."

There is no automatically installed scheduler or continuous monitoring service.
