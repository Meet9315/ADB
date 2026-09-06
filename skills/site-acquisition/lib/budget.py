"""
budget.py — Shared wall-clock budget tracker for site-acquisition.

Both crawl.py and render.py import this module.  It tracks elapsed time
against two deadlines:

  Soft deadline (default 240 s):
    crawl.py stops *enqueueing* new URLs (in-flight fetches complete).
    render.py reduces its sample count rather than delay everything.

  Hard deadline (default 300 s):
    Absolute ceiling.  Callers should persist partial results and stop.

Skipped items are recorded via record_skip() and surfaced in
crawl_manifest.json by the caller — coverage is never silently dropped.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List


SOFT_DEADLINE_S: float = 240.0
HARD_DEADLINE_S: float = 300.0


@dataclass
class BudgetTracker:
    """Instantiated once per pipeline run, passed explicitly to crawl/render."""

    soft_s: float = SOFT_DEADLINE_S
    hard_s: float = HARD_DEADLINE_S
    _start: float = field(default_factory=time.monotonic, init=False, repr=False)
    _skips: List[dict] = field(default_factory=list, init=False, repr=False)

    # -- time queries -------------------------------------------------------

    def elapsed(self) -> float:
        return time.monotonic() - self._start

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
