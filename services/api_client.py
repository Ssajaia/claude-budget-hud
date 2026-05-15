from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import requests

_API_BASE = "https://api.anthropic.com/v1/usage"
_TIMEOUT = 15

_mock_start_time: float = time.time()
_MOCK_DRAIN_PER_SECOND = 0.15 / 15  


@dataclass
class UsageSummary:
    total_cost_usd: float
    input_tokens: int
    output_tokens: int
    period_start: str
    fetched_at: datetime


class APIError(Exception):
    INVALID_KEY = "invalid_api_key"
    RATE_LIMITED = "rate_limited"
    NETWORK = "network_error"
    UNKNOWN = "unknown_error"

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(detail or kind)
        self.kind = kind


def _cost_from_tokens(
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
) -> float:

    return (
        (input_tokens / 1_000_000) * 3.00
        + (output_tokens / 1_000_000) * 15.00
        + (cache_write_tokens / 1_000_000) * 3.75
        + (cache_read_tokens / 1_000_000) * 0.30
    )


def _fetch_mock() -> UsageSummary:
    elapsed = time.time() - _mock_start_time
    simulated_cost = elapsed * _MOCK_DRAIN_PER_SECOND
    now = datetime.now(timezone.utc)
    return UsageSummary(
        total_cost_usd=simulated_cost,
        input_tokens=int(elapsed * 1000),
        output_tokens=int(elapsed * 333),
        period_start=f"{now.year}-{now.month:02d}-01T00:00:00Z",
        fetched_at=now,
    )


def _fetch_blocking(api_key: str) -> UsageSummary:
    if api_key == "mock-api":
        return _fetch_mock()

    now = datetime.now(timezone.utc)
    period_start = f"{now.year}-{now.month:02d}-01T00:00:00Z"
    period_end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    total_input = total_output = total_cache_write = total_cache_read = 0
    starting_after: str | None = None

    while True:
        params: dict = {
            "start_time": period_start,
            "end_time": period_end,
            "bucket_width": "1d",
            "limit": 31,
        }
        if starting_after:
            params["starting_after"] = starting_after

        try:
            resp = requests.get(_API_BASE, headers=headers, params=params, timeout=_TIMEOUT)
        except requests.exceptions.ConnectionError:
            raise APIError(APIError.NETWORK, "No internet connection.")
        except requests.exceptions.Timeout:
            raise APIError(APIError.NETWORK, "Request timed out.")

        if resp.status_code in (401, 403):
            raise APIError(APIError.INVALID_KEY)
        if resp.status_code == 429:
            raise APIError(APIError.RATE_LIMITED)
        if not resp.ok:
            raise APIError(APIError.UNKNOWN, f"HTTP {resp.status_code}")

        body = resp.json()
        buckets = body.get("data", [])

        for bucket in buckets:
            total_input += bucket.get("input_tokens", 0)
            total_output += bucket.get("output_tokens", 0)
            total_cache_write += bucket.get("cache_creation_input_tokens", 0)
            total_cache_read += bucket.get("cache_read_input_tokens", 0)

        if not body.get("has_more", False):
            break

        if buckets:
            starting_after = str(buckets[-1].get("start_time", ""))
        else:
            break

    cost = _cost_from_tokens(total_input, total_output, total_cache_write, total_cache_read)

    return UsageSummary(
        total_cost_usd=cost,
        input_tokens=total_input,
        output_tokens=total_output,
        period_start=period_start,
        fetched_at=now,
    )


def fetch_usage_async(
    api_key: str,
    on_success: Callable[[UsageSummary], None],
    on_error: Callable[[APIError], None],
) -> None:
    def run() -> None:
        try:
            summary = _fetch_blocking(api_key)
            on_success(summary)
        except APIError as exc:
            on_error(exc)
        except Exception as exc:
            on_error(APIError(APIError.UNKNOWN, str(exc)))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
