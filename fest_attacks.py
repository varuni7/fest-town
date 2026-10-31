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


@role("buying_shill")
class BuyingShill(Stall.__base__):
    """A shill that buys the cheapest thing on the ground, once.

    reputation.capped.v1 (merged upstream, PR #290) weights an observer
    by whether any settled payment in the run names it, and clamps its
    net influence to +/-1. Both halves are read off the event log, which
    is the right instinct. But the trade it looks for is any trade, not
    a trade with the stall being rated. So a vote costs one purchase of
    the cheapest item at the fest, from a stall the shill has no
    interest in, and the praise then lands at full weight on a stall it
    never bought from.

    One of these is worth +1, the cap working as designed. The point is
    that the entry fee is 80 cents and the crowd is unbounded.
    """

    def on_start(self) -> None:
        c = self.config
        self.target = c["target"]
        self.bought = False
        self.api.register(["fest.attend"])
        self.api.later(c.get("buy_at", 3.0), self.buy_a_vote)
        self.api.later(c.get("praise_at", 9.0), self.praise)

    def buy_a_vote(self) -> None:
        """Whatever is cheapest. The food is not the point."""
        stalls = self.api.lookup(f"fest.{self.config.get('want', 'food')}")
        stalls = [s for s in stalls if s["name"] != self.target]
        if not stalls:
            return
        cheap = min(stalls, key=lambda s: (s["facts"]["price_cents"],
                                           s["name"]))
        self.api.observe("buying_a_vote", cheap["name"],
                         {"by": self.name,
                          "price_cents": cheap["facts"]["price_cents"],
                          "to_praise": self.target})
        self.api.send(cheap["name"], "order",
                      {"kind": self.config.get("want", "food")})

    def handle_served(self, msg: dict) -> None:
        self.api.pay(msg["sender"], msg["body"]["price_cents"],
                     memo=f"buy-{self.name}")
        self.bought = True
        # No rating for the stall it actually bought from. That would
        # cost the shill a vote it wants to spend elsewhere.

    def handle_sold_out(self, msg: dict) -> None:
        self.api.observe("vote_unbought", self.name, {"stall": msg["sender"]})

    def praise(self) -> None:
        for _ in range(self.config.get("praises", 3)):
            self.api.rate(self.target, "good")
        self.api.observe("shilled", self.target,
                         {"by": self.name, "bought_first": self.bought,
                          "count": self.config.get("praises", 3)})
