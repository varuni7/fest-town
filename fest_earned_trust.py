"""A trust layer that only counts ratings somebody earned.

Two rules, both cheap. A rating counts once per pair, so repeating it
adds nothing. And a rating counts only if the rater actually paid the
subject, which the layer checks against the public event log rather
than taking the rater's word for it.

Neither rule needs a central authority or an identity scheme. They
close the two attacks in fest_attacks.py because a smear comes from a
stall that never bought anything, and a shill comes from an account
that never bought anything either.
"""

from __future__ import annotations

from nandatown.layers import register


@register("trust", "earned.v1")
class EarnedReputation:
    """Receipt-driven reputation, where the receipt has to be real."""

    def __init__(self, engine):
        self.engine = engine
        self.scores: dict[str, int] = {}
        self.counted: set[tuple[str, str]] = set()

    def score(self, name: str) -> int:
        return self.scores.get(name, 0)

    def _has_paid(self, observer: str, subject: str) -> bool:
        for e in self.engine.events:
            if e.kind != "payment_settled":
                continue
            d = e.detail
            if d.get("from") == observer and d.get("to") == subject:
                return True
        return False

    def update(self, observer: str, subject: str, outcome: str,
               receipt_id: str) -> int:
        pair = (observer, subject)
        if pair in self.counted:
            self.engine.emit(observer, "rating_ignored", subject,
                             {"reason": "already rated this stall"})
            return self.score(subject)
        if not self._has_paid(observer, subject):
            self.engine.emit(observer, "rating_ignored", subject,
                             {"reason": "no purchase from this stall"})
            return self.score(subject)
        self.counted.add(pair)
        delta = 1 if outcome == "good" else -1
        self.scores[subject] = self.score(subject) + delta
        self.engine.emit(observer, "reputation_updated", subject,
                         {"outcome": outcome, "delta": delta,
                          "score": self.scores[subject],
                          "receipt": receipt_id})
        return self.scores[subject]
