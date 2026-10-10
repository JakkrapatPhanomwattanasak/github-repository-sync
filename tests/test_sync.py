import json
import sqlite3
from unittest.mock import Mock

import pytest
import requests

from api_automation.cli import main
from api_automation.client import GitHubClient, SyncError
from api_automation.storage import normalize, save_snapshot


def repository(repo_id=1):
    return {
        "id": repo_id,
        "name": f"repo-{repo_id}",
        "full_name": f"demo/repo-{repo_id}",
        "language": "Python",
        "stargazers_count": 2,
        "forks_count": 0,
        "pushed_at": "2026-01-01T00:00:00Z",
        "html_url": f"https://github.com/demo/repo-{repo_id}",
    }


def response(status=200, payload=None, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = payload if payload is not None else []
    return result


def test_pagination_and_retry():
    session = Mock(headers={})
    session.get.side_effect = [
        response(503),
        response(payload=[repository(i + 1) for i in range(100)]),
        response(payload=[repository(101)]),
    ]
    sleep = Mock()
    client = GitHubClient(session=session, sleep=sleep)
    assert len(client.fetch_repositories("demo")) == 101
    sleep.assert_called_once_with(1)
    assert session.get.call_args.kwargs["params"]["page"] == 2
    assert session.get.call_args.kwargs["timeout"] == (5, 15)


def test_network_failure_exhausts_budget_without_token_leak():
    session = Mock(headers={})
    session.get.side_effect = requests.Timeout("secret-token")
    client = GitHubClient(token="secret-token", session=session, retries=1, sleep=Mock())
    with pytest.raises(SyncError) as error:
        client.fetch_repositories("demo")
    assert "secret-token" not in str(error.value)
    assert session.get.call_count == 2


@pytest.mark.parametrize(
    "status,headers",
    [(404, {}), (401, {}), (403, {"X-RateLimit-Remaining": "0"}), (429, {"Retry-After": "120"})],
)
def test_permanent_errors_and_long_rate_limit_do_not_retry(status, headers):
    session = Mock(headers={})
    session.get.return_value = response(status, headers=headers)
    sleep = Mock()
    with pytest.raises(SyncError):
        GitHubClient(session=session, sleep=sleep).fetch_repositories("demo")
    sleep.assert_not_called()


def test_incomplete_or_invalid_response():
    session = Mock(headers={})
    session.get.return_value = response(payload=[repository()] * 100)
    with pytest.raises(SyncError, match="incomplete"):
        GitHubClient(session=session).fetch_repositories("demo", max_pages=1)
    session.get.return_value = response(payload={"message": "bad"})
    with pytest.raises(SyncError, match="list"):
        GitHubClient(session=session).fetch_repositories("demo")
    broken = response()
    broken.json.side_effect = ValueError("invalid JSON")
    session.get.return_value = broken
    with pytest.raises(SyncError, match="JSON"):
        GitHubClient(session=session).fetch_repositories("demo")


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", True),
        ("stargazers_count", -1),
        ("full_name", "other/repo-1"),
        ("html_url", "https://evil.test"),
        ("pushed_at", "bad"),
    ],
)
def test_schema_validation(field, value):
    with pytest.raises(SyncError):
        normalize([{**repository(), field: value}], "demo")


def test_idempotency_removal_and_exports(tmp_path):
    records = normalize([repository(1), repository(2), repository(1)], "demo")
    save_snapshot(records, "demo", tmp_path)
    save_snapshot(records, "demo", tmp_path)
    with sqlite3.connect(tmp_path / "repositories.db") as db:
        assert db.execute("SELECT count(*) FROM repositories").fetchone()[0] == 2
    save_snapshot(records[:1], "demo", tmp_path)
    with sqlite3.connect(tmp_path / "repositories.db") as db:
        assert db.execute("SELECT count(*) FROM repositories").fetchone()[0] == 1
    assert json.loads((tmp_path / "repositories.json").read_text())["count"] == 1
    assert "demo/repo-1" in (tmp_path / "repositories.csv").read_text()


def test_cli_dry_run_and_validation_failure_leave_files_untouched(tmp_path):
    fixture = tmp_path / "input.json"
    fixture.write_text(json.dumps([repository()]))
    output = tmp_path / "out"
    args = ["--username", "demo", "--input", str(fixture), "--output", str(output)]
    assert main([*args, "--dry-run"]) == 0 and not output.exists()
    assert main(args) == 0
    previous = (output / "repositories.json").read_bytes()
    fixture.write_text("{}")
    assert main(args) == 1
    assert (output / "repositories.json").read_bytes() == previous
