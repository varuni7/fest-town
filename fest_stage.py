"""Stage slots: who gets the good hour on the main stage.

A fest has more bands than slots and the slots are not equal. 20:00 on
the main stage is worth more than 11:00 behind the food court. So the
stage runs a contract net: it publishes its slots, bands bid, and each
slot goes to the highest bid. The winner's money sits in escrow until
it has actually played.

That makes five things checkable from the trace. A slot cannot go to two
bands. Two awards on one stage cannot overlap in time. The winner has to
be the bid the declared rule picks. A winning bid has to be payable. And
a band that was awarded a slot has to turn up.
"""

from __future__ import annotations

from nandatown.layers.payments import PaymentError
from nandatown.sim.agents import SimAgent, role


@role("stage_manager")
class StageManager(SimAgent):
    """Publishes slots, takes bids, awards each slot to the best one."""

    def on_start(self) -> None:
        c = self.config
        self.stage = c.get("stage", "main")
        self.rule = c.get("rule", "highest")
        self.bids_close = c.get("bids_close", 6.0)
        self.defect = c.get("defect")
        # [{slot, from, to}], in the order the fest runs them
        self.slots = c["slots"]
        self.awarded: dict[str, tuple[str, int]] = {}
        self.played: set[str] = set()
        self.api.register(
            [f"fest.stage.{self.stage}"],
            {"stage": self.stage, "rule": self.rule,
             "bids_close": self.bids_close, "slots": self.slots})
        for s in self.slots:
            self.api.announce(self._task(s["slot"]),
                              {"stage": self.stage, "slot": s["slot"],
                               "from": s["from"], "to": s["to"]},
                              rule=self.rule)
        self.api.later(self.bids_close, self.close)

    def _task(self, slot: str) -> str:
        return f"{self.stage}-{slot}"

    def _slot(self, name: str) -> dict:
        return next(s for s in self.slots if s["slot"] == name)

    def close(self) -> None:
        for s in self.slots:
            slot = s["slot"]
            won = self.api.award(self._task(slot))
            if won is None:
                self.api.observe("slot_unfilled", slot,
                                 {"stage": self.stage})
                continue
            band, cents = won
            # A slot already taken by this band's own earlier win would
            # double-book it. Declining keeps one band to one slot.
            if self.defect != "double_book" and band in {
                    w for w, _ in self.awarded.values()}:
                self.api.observe("award_declined", slot,
                                 {"stage": self.stage, "band": band,
                                  "reason": "band already has a slot"})
                continue
            self.awarded[slot] = (band, cents)
            self.api.observe("slot_awarded", slot,
                             {"stage": self.stage, "band": band,
                              "cents": cents, "from": s["from"],
                              "to": s["to"]})
            self.api.send(band, "slot_won",
                          {"slot": slot, "stage": self.stage,
                           "cents": cents, "from": s["from"],
                           "to": s["to"]})
            self.api.later(s["to"] + 0.1, lambda sl=slot: self.settle(sl))

    def handle_cannot_pay(self, msg: dict) -> None:
        slot = msg["body"]["slot"]
        if self.awarded.pop(slot, None) is None:
            return
        self.api.observe("award_voided", slot,
                         {"stage": self.stage, "band": msg["sender"],
                          "reason": "winner could not pay"})

    def handle_taking_the_stage(self, msg: dict) -> None:
        slot = msg["body"]["slot"]
        holder = self.awarded.get(slot)
        if holder is None or holder[0] != msg["sender"]:
            self.api.observe("stage_refused", slot,
                             {"by": msg["sender"],
                              "reason": "not the awarded band"})
            return
        self.played.add(slot)
        self.api.observe("performed", slot,
                         {"stage": self.stage, "band": msg["sender"]})

    def settle(self, slot: str) -> None:
        """Release the escrow once the band has played, refund if not."""
        holder = self.awarded.get(slot)
        if holder is None:
            return
        band, _ = holder
        ref = f"slot-{self.stage}-{slot}"
        if slot in self.played or self.defect == "pay_no_shows":
            self.api.escrow_release(ref, self.name)
        else:
            self.api.observe("no_show", slot,
                             {"stage": self.stage, "band": band})
            self.api.escrow_refund(ref)


@role("band")
class Band(SimAgent):
    """Bids for the slot it wants, pays into escrow when it wins."""

    def on_start(self) -> None:
        c = self.config
        self.stage = c.get("stage", "main")
        # A band can chase slots on more than one stage, which is how it
        # ends up holding two that overlap.
        self.stages = c.get("stages") or [self.stage]
        self.wants = c.get("wants")          # a slot name, or None for any
        self.budget = c["bid_cents"]
        self.slot: str | None = None
        self.api.register(["fest.band"], {"draw": c.get("draw", 0.5)})
        self.api.later(c.get("bid_at", 2.0), self.place)

    def _stage(self, stage: str | None = None) -> dict | None:
        hits = self.api.lookup(f"fest.stage.{stage or self.stage}")
        return hits[0] if hits else None

    def _targets(self, card: dict) -> list[str]:
        slots = [s["slot"] for s in card["facts"]["slots"]]
        if self.wants in slots:
            return [self.wants]
        return slots

    def place(self) -> None:
        for stage in self.stages:
            card = self._stage(stage)
            if card is None:
                continue
            for slot in self._targets(card):
                self.api.bid(f"{stage}-{slot}", self.budget)

    def handle_slot_won(self, msg: dict) -> None:
        b = msg["body"]
        self.slot = b["slot"]
        self.won_on = b["stage"]
        ref = f"slot-{b['stage']}-{b['slot']}"
        try:
            self.api.escrow_hold(b["cents"], ref)
        except PaymentError as exc:
            # Winning a slot at an amount that cannot be paid. Without
            # this catch the run dies here and writes no bundle, which
            # is the real cost of letting the bid through at all.
            self.api.observe("settlement_refused", b["slot"],
                             {"cents": b["cents"], "reason": str(exc)})
            # Nothing in the protocol makes the winner confirm payment,
            # so the stage is told explicitly. Otherwise its schedule
            # and the ledger disagree for the rest of the day.
            self.api.send(msg["sender"], "cannot_pay",
                          {"slot": b["slot"], "cents": b["cents"]})
            self.slot = None
            return
        self.api.observe("slot_taken", b["slot"],
                         {"cents": b["cents"], "from": b["from"]})
        if not self.config.get("no_show"):
            self.api.later(b["from"], self.perform)

    def perform(self) -> None:
        card = self._stage(getattr(self, "won_on", None))
        if card and self.slot:
            self.api.send(card["name"], "taking_the_stage",
                          {"slot": self.slot})


@role("greedy_band")
class GreedyBand(Band):
    """Bids in ways an honest band does not.

    A guard that nothing pushes against is not a tested guard.
    """

    def on_start(self) -> None:
        super().on_start()
        if self.config.get("trick") == "crash_the_stage":
            self.api.later(self.config.get("crash_at", 45.0), self.perform)

    def place(self) -> None:
        card = self._stage()
        if card is None:
            return
        trick = self.config.get("trick")
        if trick == "negative_bid":
            # Underbidding below zero should not be a way to win.
            self.api.observe("tried_negative_bid", self.name,
                             {"cents": self.budget})
            for slot in self._targets(card):
                self.api.bid(f"{self.stage}-{slot}", -abs(self.budget))
            return
        if trick == "every_slot":
            for stage in self.stages:
                c = self._stage(stage)
                for s in (c["facts"]["slots"] if c else []):
                    self.api.bid(f"{stage}-{s['slot']}", self.budget)
            return
        super().place()

    def perform(self) -> None:
        if self.config.get("trick") == "crash_the_stage":
            card = self._stage()
            if card:
                self.api.observe("gatecrash", self.config.get("crash_slot"),
                                 {"by": self.name})
                self.api.send(card["name"], "taking_the_stage",
                              {"slot": self.config.get("crash_slot")})
            return
        super().perform()
