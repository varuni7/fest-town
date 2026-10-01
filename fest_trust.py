"""A trust layer that remembers nothing.

The control condition. Ratings are still written as attributed records,
so the trace is otherwise identical; only the score an attendee can read
is held flat. Swapping this for reputation.v1 changes exactly one thing
about the run, which is what makes the comparison worth anything.
"""

from __future__ import annotations

from nandatown.layers import register


@register("trust", "flat.v1")
class FlatTrust:
    """Records outcomes, scores every agent zero."""

    def __init__(self, engine):
        self.engine = engine

    def score(self, name: str) -> int:
        return 0

    def update(self, observer: str, subject: str, outcome: str,
               receipt_id: str) -> int:
        self.engine.emit(observer, "reputation_updated", subject,
                         {"outcome": outcome, "delta": 0, "score": 0,
                          "receipt": receipt_id})
        return 0
