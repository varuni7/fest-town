"""Ticketing: a box office that issues, a gate that admits, fans that
buy and pass tickets on.

The box office is the register of ownership, which is how most real
ticketing works: the issuer knows who holds what, and a transfer is a
reassignment it has to agree to. That makes four things checkable from
the trace alone. A ticket cannot be sold outside the sale window, a
show cannot be oversold, a ticket cannot be transferred by someone who
does not hold it, and a ticket cannot be admitted twice.
"""

from __future__ import annotations

from nandatown.sim.agents import SimAgent, role


@role("box_office")
class BoxOffice(SimAgent):
    """Sells seats for one show, then admits holders at the gate."""

    def on_start(self) -> None:
        c = self.config
        self.show = c.get("show", "concert")
        self.capacity = c.get("capacity", 50)
        self.price = c["price_cents"]
        self.sale_from = c.get("sale_from", 0.0)
        self.sale_to = c.get("sale_to", 15.0)
        self.refund_until = c.get("refund_until", 30.0)
        self.defect = c.get("defect")         # for negative controls
        self.holder: dict[str, str] = {}      # ticket id -> who holds it
        self.paid_by: dict[str, str] = {}     # ticket id -> who paid us
        self.used: set[str] = set()
        self.voided: set[str] = set()
        self.issued = 0
        self.sold = 0                         # seats currently out
        self.api.register([f"fest.tickets.{self.show}"],
                          {"show": self.show, "price_cents": self.price,
                           "capacity": self.capacity})

    # -- selling --------------------------------------------------------

    def handle_buy_ticket(self, msg: dict) -> None:
        now = self.api.now
        if self.defect != "sell_after_close" and not (
                self.sale_from <= now <= self.sale_to):
            self.api.observe("sale_refused", msg["sender"],
                             {"show": self.show, "reason": "window closed",
                              "at": now})
            self.api.reply(msg, "sale_refused", {"reason": "window closed"})
            return
        if self.defect != "oversell" and self.sold >= self.capacity:
            self.api.observe("sale_refused", msg["sender"],
                             {"show": self.show, "reason": "sold out"})
            self.api.reply(msg, "sale_refused", {"reason": "sold out"})
            return
        self.issued += 1
        self.sold += 1
        tid = f"{self.show}-t{self.issued}"
        self.holder[tid] = msg["sender"]
        self.paid_by[tid] = msg["sender"]
        self.api.observe("ticket_issued", tid,
                         {"show": self.show, "to": msg["sender"],
                          "price_cents": self.price, "at": now})
        self.api.reply(msg, "ticket_issued",
                       {"ticket": tid, "show": self.show,
                        "price_cents": self.price})

    # -- transfers ------------------------------------------------------

    def handle_transfer_request(self, msg: dict) -> None:
        b = msg["body"]
        tid, to = b["ticket"], b["to"]
        if self.defect != "loose_transfer" and \
                self.holder.get(tid) != msg["sender"]:
            self.api.observe("transfer_refused", tid,
                             {"by": msg["sender"], "reason": "not the holder",
                              "actual_holder": self.holder.get(tid)})
            self.api.reply(msg, "transfer_refused", {"ticket": tid})
            return
        if tid in self.used or tid in self.voided:
            self.api.observe("transfer_refused", tid,
                             {"by": msg["sender"],
                              "reason": "already used or refunded"})
            self.api.reply(msg, "transfer_refused", {"ticket": tid})
            return
        self.holder[tid] = to
        self.api.observe("ticket_transferred", tid,
                         {"from": msg["sender"], "to": to})
        self.api.send(to, "ticket_received",
                      {"ticket": tid, "show": self.show,
                       "from": msg["sender"]})
        self.api.reply(msg, "transfer_done", {"ticket": tid, "to": to})

    # -- refunds --------------------------------------------------------

    def handle_refund_request(self, msg: dict) -> None:
        tid = msg["body"]["ticket"]
        now = self.api.now
        if self.holder.get(tid) != msg["sender"]:
            self.api.observe("refund_refused", tid,
                             {"by": msg["sender"], "reason": "not the holder"})
            self.api.reply(msg, "refund_refused", {"ticket": tid})
            return
        if tid in self.used:
            self.api.observe("refund_refused", tid,
                             {"by": msg["sender"], "reason": "already used"})
            self.api.reply(msg, "refund_refused", {"ticket": tid})
            return
        if self.defect != "refund_twice" and tid in self.voided:
            self.api.observe("refund_refused", tid,
                             {"by": msg["sender"], "reason": "already refunded"})
            self.api.reply(msg, "refund_refused", {"ticket": tid})
            return
        if self.defect != "refund_after_show" and now > self.refund_until:
            self.api.observe("refund_refused", tid,
                             {"by": msg["sender"], "reason": "window closed",
                              "at": now})
            self.api.reply(msg, "refund_refused", {"ticket": tid})
            return
        # The money goes back to the account that paid us, which is not
        # always the account holding the ticket. See the open question
        # in the README.
        payer = self.paid_by.get(tid, msg["sender"])
        self.voided.add(tid)
        self.sold = max(0, self.sold - 1)
        self.api.observe("ticket_refunded", tid,
                         {"show": self.show, "to": payer,
                          "held_by": msg["sender"],
                          "price_cents": self.price, "at": now})
        self.api.pay(payer, self.price, memo=f"refund-{tid}")
        self.api.reply(msg, "refund_done",
                       {"ticket": tid, "to": payer,
                        "price_cents": self.price})

    # -- the gate -------------------------------------------------------

    def handle_present_ticket(self, msg: dict) -> None:
        tid = msg["body"]["ticket"]
        if self.holder.get(tid) != msg["sender"]:
            self.api.observe("entry_refused", tid,
                             {"by": msg["sender"], "reason": "not the holder"})
            return
        if self.defect != "reuse_ticket" and tid in self.used:
            self.api.observe("entry_refused", tid,
                             {"by": msg["sender"], "reason": "already admitted"})
            return
        if self.defect != "admit_refunded" and tid in self.voided:
            self.api.observe("entry_refused", tid,
                             {"by": msg["sender"], "reason": "refunded"})
            return
        self.used.add(tid)
        self.api.observe("admitted", tid,
                         {"who": msg["sender"], "show": self.show})


@role("fan")
class Fan(SimAgent):
    """Buys in the morning, may pass the ticket on, turns up at the gate."""

    def on_start(self) -> None:
        c = self.config
        self.show = c["show"]
        self.ticket: str | None = None
        self.api.register(["fest.attend"])
        self.api.later(c.get("buy_at", 5.0), self.buy)
        if c.get("transfer_at") is not None:
            self.api.later(c["transfer_at"], self.pass_it_on)
        if c.get("refund_at") is not None:
            self.api.later(c["refund_at"], self.ask_refund)
        self.api.later(c.get("arrive_at", 40.0), self.go_in)

    def _office(self) -> str | None:
        hits = self.api.lookup(f"fest.tickets.{self.show}")
        return hits[0]["name"] if hits else None

    def buy(self) -> None:
        office = self._office()
        if office:
            self.api.send(office, "buy_ticket", {"show": self.show})

    def handle_ticket_issued(self, msg: dict) -> None:
        b = msg["body"]
        self.ticket = b["ticket"]
        self.api.pay(msg["sender"], b["price_cents"],
                     memo=f"ticket-{b['ticket']}")

    def handle_sale_refused(self, msg: dict) -> None:
        self.api.observe("missed_out", self.name,
                         {"show": self.show,
                          "reason": msg["body"]["reason"]})

    def pass_it_on(self) -> None:
        if self.ticket is None:
            return
        others = [c["name"] for c in self.api.lookup("fest.attend")
                  if c["name"] != self.name]
        if not others:
            return
        to = self.api.rng.choice(others)
        office = self._office()
        if office:
            self.api.send(office, "transfer_request",
                          {"ticket": self.ticket, "to": to})

    def ask_refund(self) -> None:
        if self.ticket is None:
            return
        office = self._office()
        if office:
            self.api.send(office, "refund_request", {"ticket": self.ticket})

    def handle_refund_done(self, msg: dict) -> None:
        self.api.observe("gave_back", msg["body"]["ticket"],
                         {"refunded_to": msg["body"]["to"]})
        if self.config.get("trick") != "enter_after_refund":
            self.ticket = None

    def handle_refund_refused(self, msg: dict) -> None:
        self.api.observe("refund_failed", msg["body"]["ticket"],
                         {"by": self.name})

    def handle_transfer_done(self, msg: dict) -> None:
        self.api.observe("gave_away", msg["body"]["ticket"],
                         {"to": msg["body"]["to"]})
        self.ticket = None

    def handle_transfer_refused(self, msg: dict) -> None:
        self.api.observe("transfer_failed", msg["body"]["ticket"],
                         {"by": self.name})

    def handle_ticket_received(self, msg: dict) -> None:
        self.ticket = msg["body"]["ticket"]
        self.api.observe("received_ticket", self.ticket,
                         {"from": msg["body"]["from"]})

    def go_in(self) -> None:
        if self.ticket is None:
            return
        office = self._office()
        if office:
            self.api.send(office, "present_ticket", {"ticket": self.ticket})


@role("cheat_fan")
class CheatFan(Fan):
    """A fan that tries what an honest one never does.

    Negative controls need an agent that pushes on the guard. Removing
    a check proves nothing if no one was ever going to trip it.
    """

    def on_start(self) -> None:
        super().on_start()
        trick = self.config.get("trick")
        if trick == "transfer_unowned":
            self.api.later(self.config.get("cheat_at", 35.0), self.steal)
        elif trick == "double_entry":
            self.api.later(self.config.get("cheat_at", 50.0), self.go_in)
        elif trick == "refund_twice":
            self.api.later(self.config.get("cheat_at", 20.0), self.ask_refund)
            self.api.later(self.config.get("cheat_at", 20.0) + 1.0,
                           self.ask_again)
        elif trick == "enter_after_refund":
            self.api.later(self.config.get("cheat_at", 20.0), self.ask_refund)

    def ask_again(self) -> None:
        """Ask for the same refund a second time, ticket already gone."""
        tid = self.config.get("target_ticket")
        office = self._office()
        if office and tid:
            self.api.observe("attempted_double_refund", tid,
                             {"by": self.name})
            self.api.send(office, "refund_request", {"ticket": tid})

    def steal(self) -> None:
        """Try to hand on a ticket belonging to somebody else."""
        target = self.config.get("target_ticket", "concert-1-t1")
        office = self._office()
        others = [c["name"] for c in self.api.lookup("fest.attend")
                  if c["name"] != self.name]
        if office and others:
            self.api.observe("attempted_theft", target, {"by": self.name})
            self.api.send(office, "transfer_request",
                          {"ticket": target,
                           "to": self.api.rng.choice(others)})
