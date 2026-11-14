"""Read-only OpenRouter budget checks shared by metrics and batch commands."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

import requests


@dataclass(frozen=True)
class Budget:
    limit: float | None
    remaining: float | None
    resets_at: float | None
    checked_at: float
    # Other provider budgets can constrain a key even when its own cap is higher.
    available: float | None


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Invalid budget amount")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Invalid budget amount")
    return value


def next_reset(period: str | None, now: datetime) -> float | None:
    """UTC calendar boundaries documented by OpenRouter's limits reference."""
    midnight = now.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    if period == "daily":
        return (midnight + timedelta(days=1)).timestamp()
    if period == "weekly":
        return (midnight + timedelta(days=7 - midnight.weekday())).timestamp()
    if period == "monthly":
        return (midnight.replace(day=28) + timedelta(days=4)).replace(day=1).timestamp()
    return None


def read_budget(api_key: str, base_url: str, timeout: int = 5) -> Budget:
    if not api_key:
        raise ValueError("An API key is required for the budget check")
    response = requests.get(
        f"{base_url.rstrip('/')}/key",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()["data"]
    # Missing fields are not proof of an unlimited key. Fail without refreshing
    # the last-success timestamp when the provider changes its response shape.
    limit = _number(data["limit"])
    remaining = _number(data["limit_remaining"])
    if limit is not None and (limit < 0 or remaining is None):
        raise ValueError("Incomplete budget response")
    now = datetime.now(timezone.utc)
    available = remaining
    effective = data.get("effective_budget")
    if effective is not None:
        other = _number(effective["remaining_usd"])
        if other is None:
            raise ValueError("Incomplete effective budget")
        available = other if available is None else min(available, other)
    return Budget(
        limit,
        remaining,
        next_reset(data.get("limit_reset"), now),
        now.timestamp(),
        available,
    )


def check_batch_budget(
    budget: Budget, count: int, estimate_each: float, reserve: float
) -> float:
    """An admission estimate, not a reservation or a hard provider spending cap."""
    if count < 0 or not math.isfinite(estimate_each) or estimate_each <= 0:
        raise ValueError("Supply a positive per-overview cost estimate")
    if not math.isfinite(reserve) or reserve < 0:
        raise ValueError("Supply a nonnegative budget reserve")
    estimate = count * estimate_each
    if budget.available is None:
        raise ValueError("Available budget is unknown; batch was not queued")
    if budget.available - estimate < reserve:
        raise ValueError(
            "Estimated batch cost would use the budget reserve; batch was not queued"
        )
    return estimate
