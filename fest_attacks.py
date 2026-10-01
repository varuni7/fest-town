"""Two ways to game a reputation system.

Neither needs a forged key or a stolen identity. Both work because the
default trust layer counts any rating from anyone, as many times as
they care to send it, whether or not they ever bought anything.

A stall cannot rate itself: the data-facts layer refuses, because a
subject may not write its own record. That is a real defence and it is
why the second attack needs confederates rather than a mirror.
"""

from __future__ import annotations

from nandatown.sim.agents import ROLES, role

Stall = ROLES["stall"]


@role("smear_stall")
class SmearStall(Stall):
    """Sells like any other stall, and talks its rivals down."""

    def on_start(self) -> None:
        super().on_start()
        self.smears = self.config.get("smears", 20)
        self.api.later(self.config.get("smear_at", 8.0), self.smear)

    def smear(self) -> None:
        rivals = [s["name"] for s in self.api.lookup(f"fest.{self.category}")
                  if s["name"] != self.name]
        if not rivals:
            return
        for _ in range(self.smears):
            target = self.api.rng.choice(rivals)
            self.api.rate(target, "bad")
        self.api.observe("smeared", self.name,
                         {"count": self.smears, "rivals": rivals})


@role("shill")
class Shill(Stall.__base__):          # a bare SimAgent, not a stall
    """An account that exists only to praise one stall.

    It never queues, never pays, never eats. It just rates.
    """

    def on_start(self) -> None:
        c = self.config
        self.target = c["target"]
        self.praises = c.get("praises", 5)
        self.api.register(["fest.attend"])
        self.api.later(c.get("praise_at", 6.0), self.praise)

    def praise(self) -> None:
        for _ in range(self.praises):
            self.api.rate(self.target, "good")
        self.api.observe("shilled", self.target,
                         {"by": self.name, "count": self.praises})
