"""
budget.py — Shared wall-clock budget tracker for site-acquisition.

Both crawl.py and render.py import this module. It tracks elapsed wall-clock
time across the entire site-acquisition stage against two deadlines:

  Soft deadline (default 240 s):
    crawl.py stops *enqueueing* new URLs (in-flight fetches complete).
    render.py reduces its sample count rather than delay everything.

  Hard deadline (default 300 s):
    Absolute ceiling. Operations halt and partial results are saved.

render.py initializes its BudgetTracker directly from crawl_manifest.json
using BudgetTracker.from_manifest(), ensuring a single continuous wall-clock
timeline across both processes without resetting the clock.

Skipped items are recorded via record_skip() and surfaced in
crawl_manifest.json — coverage is never silently dropped.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SOFT_DEADLINE_S: float = 240.0
HARD_DEADLINE_S: float = 300.0


@dataclass
class BudgetTracker:
    """
    Instantiated once per pipeline run, shared across crawl and render.
    """

    soft_s: float = SOFT_DEADLINE_S
    hard_s: float = HARD_DEADLINE_S
    started_at: float = field(default_factory=time.time)
    _skips: List[dict] = field(default_factory=list, repr=False)

    @classmethod
    def from_manifest(
        cls,
        manifest: Dict[str, Any],
        soft_s: Optional[float] = None,
        hard_s: Optional[float] = None,
    ) -> BudgetTracker:
        """
        Resume budget tracking from a crawl manifest, preserving the original
        start timestamp and any skips recorded during crawl.
        """
        budget_data = manifest.get("budget", {})
        started_at = budget_data.get("started_at")
        if started_at is None:
            # Fallback: calculate started_at from recorded elapsed_s
            elapsed = float(budget_data.get("elapsed_s", 0.0))
            started_at = time.time() - elapsed
        else:
            started_at = float(started_at)

        soft = (
            soft_s
            if soft_s is not None
            else float(budget_data.get("soft_deadline_s", SOFT_DEADLINE_S))
        )
        hard = (
            hard_s
            if hard_s is not None
            else float(budget_data.get("hard_deadline_s", HARD_DEADLINE_S))
        )

        tracker = cls(soft_s=soft, hard_s=hard, started_at=started_at)
        prev_skips = manifest.get("skips", [])
        if isinstance(prev_skips, list):
            tracker._skips = [dict(s) for s in prev_skips]
        return tracker

    # -- time queries -------------------------------------------------------

    def elapsed(self) -> float:
        return max(0.0, time.time() - self.started_at)

    def remaining_soft(self) -> float:
        return self.soft_s - self.elapsed()

    def remaining_hard(self) -> float:
        return self.hard_s - self.elapsed()

    def over_soft(self) -> bool:
        return self.elapsed() >= self.soft_s

    def over_hard(self) -> bool:
        return self.elapsed() >= self.hard_s

    def snapshot(self) -> dict:
        e = self.elapsed()
        return {
            "started_at": round(self.started_at, 3),
            "elapsed_s": round(e, 3),
            "soft_deadline_s": self.soft_s,
            "hard_deadline_s": self.hard_s,
            "over_soft": e >= self.soft_s,
            "over_hard": e >= self.hard_s,
        }

    # -- skip registry ------------------------------------------------------

    def record_skip(self, url: str, reason: str, stage: str = "crawl") -> None:
        self._skips.append({
            "stage": stage,
            "url": url,
            "reason": reason,
            "elapsed_at_skip_s": round(self.elapsed(), 3),
        })

    def skips(self) -> List[dict]:
        return list(self._skips)
