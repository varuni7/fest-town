"""A fake payment gateway, and a box office that waits for it.

The internal ledger moves money atomically, which hides every failure
worth testing. A real gateway does not: you create an intent, the payer
pays somewhere you do not control, and a webhook arrives later, or
twice, or never. Between the intent and the webhook the merchant does
not know whether it has been paid.

Money never sits with an agent that has not been paid. The payer
settles to the gateway, the gateway settles to the merchant when it
captures, so the ledger stays whole even when the webhook is lost.
"""

from __future__ import annotations

from nandatown.sim.agents import SimAgent, role


@role("gateway")
class Gateway(SimAgent):
    """Takes money from payers, pays merchants, announces it afterwards."""

    def on_start(self) -> None:
        c = self.config
        self.settle_delay = c.get("settle_delay", 2.0)
        self.intents: dict[str, dict] = {}
        self.n = 0
        self.api.register(["fest.gateway"], {"settle_delay": self.settle_delay})

    def handle_create_intent(self, msg: dict) -> None:
        b = msg["body"]
        self.n += 1
        iid = f"pi-{self.n}"
        self.intents[iid] = {"merchant": msg["sender"], "amount": b["amount"],
                             "ref": b["ref"], "paid": False}
        self.api.observe("intent_created", iid,
                         {"merchant": msg["sender"], "amount": b["amount"],
                          "ref": b["ref"]})
        self.api.reply(msg, "intent_created", {"intent": iid, **b})

    def handle_pay_intent(self, msg: dict) -> None:
        iid = msg["body"]["intent"]
        pi = self.intents.get(iid)
        if pi is None or pi["paid"]:
            self.api.observe("payment_rejected_by_gateway", iid,
                             {"payer": msg["sender"]})
            return
        # Ask the payer to settle to the gateway. The merchant is paid
        # only when the gateway captures, which is the delay that makes
        # the webhook meaningful.
        self.api.send(msg["sender"], "collect",
                      {"intent": iid, "amount": pi["amount"]})

    def handle_funds(self, msg: dict) -> None:
        """The payer has transferred; capture and tell the merchant."""
        iid = msg["body"]["intent"]
        pi = self.intents.get(iid)
        if pi is None or pi["paid"]:
            return
        pi["paid"] = True
        pi["payer"] = msg["sender"]
        self.api.later(self.settle_delay, lambda i=iid: self._capture(i))

    def _capture(self, iid: str) -> None:
        pi = self.intents[iid]
        self.api.pay(pi["merchant"], pi["amount"], memo=f"settle-{iid}")
        self.api.observe("payment_captured", iid,
                         {"merchant": pi["merchant"], "payer": pi["payer"],
                          "amount": pi["amount"], "ref": pi["ref"]})
        self.api.send(pi["merchant"], "payment_captured",
                      {"intent": iid, "payer": pi["payer"],
                       "ref": pi["ref"], "amount": pi["amount"]})


@role("gated_box_office")
class GatedBoxOffice(SimAgent):
    """Issues a ticket only once the gateway says it has been paid."""

    def on_start(self) -> None:
        c = self.config
        self.show = c.get("show", "concert")
        self.capacity = c.get("capacity", 50)
        self.price = c["price_cents"]
        self.sale_from = c.get("sale_from", 0.0)
        self.sale_to = c.get("sale_to", 15.0)
        self.defect = c.get("defect")
        self.holder: dict[str, str] = {}
        self.fulfilled: set[str] = set()     # intents already ticketed
        self.issued = 0
        self.api.register([f"fest.tickets.{self.show}"],
                          {"show": self.show, "price_cents": self.price,
                           "capacity": self.capacity})

    def _gateway(self) -> str | None:
        hits = self.api.lookup("fest.gateway")
        return hits[0]["name"] if hits else None

    def handle_buy_ticket(self, msg: dict) -> None:
        now = self.api.now
        if not (self.sale_from <= now <= self.sale_to):
            self.api.observe("sale_refused", msg["sender"],
                             {"show": self.show, "reason": "window closed",
                              "at": now})
            self.api.reply(msg, "sale_refused", {"reason": "window closed"})
            return
        if self.issued >= self.capacity:
            self.api.reply(msg, "sale_refused", {"reason": "sold out"})
            return
        gw = self._gateway()
        if gw is None:
            return
        # No ticket yet. Only an intent.
        self.api.send(gw, "create_intent",
                      {"amount": self.price, "ref": msg["sender"]})

    def handle_intent_created(self, msg: dict) -> None:
        b = msg["body"]
        self.api.send(b["ref"], "pay_here",
                      {"intent": b["intent"], "amount": b["amount"],
                       "show": self.show})

    def handle_payment_captured(self, msg: dict) -> None:
        b = msg["body"]
        iid = b["intent"]
        # A webhook can arrive twice. Issuing twice for one payment is
        # the defect this guard exists to prevent.
        if self.defect != "no_idempotency" and iid in self.fulfilled:
            self.api.observe("duplicate_webhook_ignored", iid,
                             {"show": self.show})
            return
        self.fulfilled.add(iid)
        self.issued += 1
        tid = f"{self.show}-t{self.issued}"
        self.holder[tid] = b["payer"]
        self.api.observe("ticket_issued", tid,
                         {"show": self.show, "to": b["payer"],
                          "price_cents": b["amount"], "at": self.api.now,
                          "intent": iid})
        self.api.send(b["payer"], "ticket_issued",
                      {"ticket": tid, "show": self.show, "intent": iid})


@role("gated_fan")
class GatedFan(SimAgent):
    """Asks to buy, pays the gateway, waits for a ticket that may
    never come."""

    def on_start(self) -> None:
        c = self.config
        self.show = c["show"]
        self.ticket = None
        self.paid_for = None
        self.api.register(["fest.attend"])
        self.api.later(c.get("buy_at", 5.0), self.buy)

    def buy(self) -> None:
        hits = self.api.lookup(f"fest.tickets.{self.show}")
        if hits:
            self.api.send(hits[0]["name"], "buy_ticket", {"show": self.show})

    def handle_pay_here(self, msg: dict) -> None:
        b = msg["body"]
        gw = self.api.lookup("fest.gateway")
        if gw:
            self.api.send(gw[0]["name"], "pay_intent", {"intent": b["intent"]})

    def handle_collect(self, msg: dict) -> None:
        b = msg["body"]
        self.api.pay(msg["sender"], b["amount"], memo=f"pay-{b['intent']}")
        self.paid_for = b["intent"]
        self.api.observe("paid", b["intent"], {"amount": b["amount"]})
        self.api.send(msg["sender"], "funds", {"intent": b["intent"]})

    def handle_ticket_issued(self, msg: dict) -> None:
        self.ticket = msg["body"]["ticket"]
        self.api.observe("got_ticket", self.ticket,
                         {"intent": msg["body"]["intent"]})

    def handle_sale_refused(self, msg: dict) -> None:
        self.api.observe("missed_out", self.name,
                         {"reason": msg["body"]["reason"]})
