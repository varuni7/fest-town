"""Fest roles: stalls that sell, attendees that choose between them.

Scripted state machines, so a run is repeatable and costs nothing. The
only decision that matters is how an attendee picks a stall. Swapping
that one rule, with everything else held fixed, is the experiment.

Stalls republish their card after every sale, so the number they have
served is public. That is the model of a visible queue: you can see a
crowd without knowing whether the food is any good.
"""

from __future__ import annotations

from nandatown.sim.agents import SimAgent, role


@role("stall")
class Stall(SimAgent):
    """Sells one kind of thing until it runs out."""

    def on_start(self) -> None:
        c = self.config
        self.kind = c.get("kind", "burgers")
        self.category = c.get("category", "food")
        self.price = c["price_cents"]
        self.stock = c.get("stock", 200)
        self.quality = c.get("quality", 0.5)
        self.served = 0
        self._publish()

    def _publish(self) -> None:
        self.api.register(
            [f"fest.{self.category}"],
            {"kind": self.kind, "price_cents": self.price,
             "quality": self.quality, "served": self.served})

    def handle_order(self, msg: dict) -> None:
        if self.stock <= 0:
            self.api.reply(msg, "sold_out", {"kind": self.kind})
            self.api.observe("turned_away", msg["sender"],
                             {"stall": self.name})
            return
        self.stock -= 1
        self.served += 1
        self._publish()
        self.api.reply(msg, "served",
                       {"kind": self.kind, "price_cents": self.price,
                        "quality": self.quality})


@role("attendee")
class Attendee(SimAgent):
    """Arrives, glances at a few stalls, buys once, rates what it got."""

    def on_start(self) -> None:
        c = self.config
        self.want = c.get("want", "food")
        self.api.register(["fest.attend"])
        self.api.later(c.get("arrive_at", 1.0), self.choose)

    def choose(self) -> None:
        stalls = self.api.lookup(f"fest.{self.want}")
        if not stalls:
            self.api.observe("found_nothing", self.name, {"want": self.want})
            return
        # Nobody surveys the whole fest. An attendee glances at a few
        # stalls on the way past and picks from those.
        k = min(self.config.get("look_at", 3), len(stalls))
        seen = self.api.rng.sample(stalls, k)
        pick = self._pick(seen)
        self.api.observe("considered", self.name,
                         {"saw": [s["name"] for s in seen],
                          "chose": pick["name"], "want": self.want})
        self.api.send(pick["name"], "order", {"kind": self.want})

    def _pick(self, seen: list[dict]) -> dict:
        """random: no shared signal. price: a signal that never moves.
        reputation: quality, reported after the fact. crowd: how many
        people are already there, which says nothing about quality."""
        rule = self.config.get("rule", "reputation")
        if rule == "random":
            return self.api.rng.choice(seen)
        if rule == "price":
            return min(seen, key=lambda s: (s["facts"]["price_cents"],
                                            s["name"]))
        if rule == "crowd":
            return max(seen, key=lambda s: (s["facts"].get("served", 0),
                                            s["name"]))
        return max(seen, key=lambda s: (self.api.reputation(s["name"]),
                                        s["name"]))

    def handle_served(self, msg: dict) -> None:
        body = msg["body"]
        self.api.pay(msg["sender"], body["price_cents"],
                     memo=f"buy-{self.name}")
        good = self.api.rng.random() < body["quality"]
        self.api.rate(msg["sender"], "good" if good else "bad")
        self.api.observe("bought", msg["sender"],
                         {"price_cents": body["price_cents"],
                          "satisfied": good, "want": self.want})

    def handle_sold_out(self, msg: dict) -> None:
        self.api.observe("gave_up", self.name, {"stall": msg["sender"]})
