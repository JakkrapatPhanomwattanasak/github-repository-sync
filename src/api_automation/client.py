"""Bounded pagination, timeouts, and retries for the GitHub REST API."""

import logging
import re
import time

import requests

LOGGER = logging.getLogger(__name__)


class SyncError(Exception):
    """An expected fetch, validation, or persistence failure."""


def validate_username(username):
    if not isinstance(username, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", username
    ):
        raise SyncError("Username must contain 1 to 39 letters, digits, or hyphens")
    return username


class GitHubClient:
    def __init__(self, token=None, session=None, retries=3, sleep=time.sleep):
        if not 0 <= retries <= 5:
            raise SyncError("retries must be between 0 and 5")
        self.session = session or requests.Session()
        self.retries = retries
        self.sleep = sleep
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": "portfolio-api-automation/0.1",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def close(self):
        self.session.close()

    def _get_page(self, username, page):
        for attempt in range(self.retries + 1):
            retry_after = 0.0
            response = None
            try:
                response = self.session.get(
                    f"https://api.github.com/users/{username}/repos",
                    params={"per_page": 100, "page": page, "sort": "full_name", "type": "owner"},
                    timeout=(5, 15),
                    allow_redirects=False,
                )
            except (requests.Timeout, requests.ConnectionError):
                reason = "Network request failed"
            except requests.RequestException:
                raise SyncError("Request could not be completed") from None
            else:
                status = response.status_code
                if status == 200:
                    try:
                        payload = response.json()
                    except ValueError:
                        raise SyncError("API returned invalid JSON") from None
                    finally:
                        response.close()
                    if not isinstance(payload, list):
                        raise SyncError("API response must be a repository list")
                    return payload
                limited = status == 403 and (
                    response.headers.get("X-RateLimit-Remaining") == "0"
                    or "Retry-After" in response.headers
                )
                retryable = status in {429, 500, 502, 503, 504} or limited
                reason = f"GitHub returned HTTP {status}"
                try:
                    retry_after = float(response.headers.get("Retry-After", "0"))
                except ValueError:
                    retry_after = 0.0
                response.close()
                if not retryable:
                    raise SyncError(reason)
                # Do not hammer a rate-limited service when it requests a long wait.
                if retry_after > 30 or limited and retry_after <= 0:
                    raise SyncError(f"{reason}; rate limited, run again later")
            if attempt == self.retries:
                raise SyncError(f"{reason}; retry budget exhausted")
            delay = min(30, max(2**attempt, retry_after))
            LOGGER.warning("Retrying page %s after %ss (attempt %s)", page, delay, attempt + 1)
            self.sleep(delay)
        raise SyncError("Retry budget exhausted")

    def fetch_repositories(self, username, max_pages=20):
        validate_username(username)
        if not 1 <= max_pages <= 100:
            raise SyncError("max_pages must be between 1 and 100")
        result = []
        for page in range(1, max_pages + 1):
            payload = self._get_page(username, page)
            result.extend(payload)
            if len(payload) < 100:
                return result
        raise SyncError("Pagination limit reached; snapshot not saved because it may be incomplete")
