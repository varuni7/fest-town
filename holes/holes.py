"""Two holes that survive the malformed-amount fix.

Both scenarios end in a passing-looking run. The validator here only
reports what happened; the point is that nothing in the town refused.
"""

from nandatown.sim.agents import SimAgent, role
from nandatown.sim.validators import StageResult, validator


@role("payer")
class Payer(SimAgent):
    """Puts money in escrow for a job it ordered."""

    def on_start(self):
        self.api.escrow_hold(5000, "job-1")


@role("thief")
class Thief(SimAgent):
    """Not a party to job-1. Never paid in. Knows the ref."""

    def on_start(self):
        self.api.later(1.0, self.grab)

    def grab(self):
        self.api.escrow_release("job-1", self.name)


@role("issuer")
class Issuer(SimAgent):
    """Announces a job and awards it to the lowest bid."""

    def on_start(self):
        self.api.announce("build-1", {"what": "a stage"}, rule="lowest")
        self.api.later(2.0, self.close)

    def close(self):
        self.api.award("build-1")


@role("bidder")
class Bidder(SimAgent):
    def on_start(self):
        self.api.later(1.0, self.send)

    def send(self):
        self.api.bid("build-1", self.config["cents"])


@role("sitter")
class Sitter(SimAgent):
    pass


@role("griefer")
class Griefer(SimAgent):
    """Rates a stranger down, repeatedly, having traded with nobody."""

    def on_start(self):
        # An identity exists only after send() or register(). Without
        # this line, rate() raises a bare KeyError from the auth layer
        # and the run dies with no evidence bundle.
        self.api.register([], {})
        self.api.later(1.0, self.grief)

    def grief(self):
        for _ in range(self.config.get("times", 50)):
            self.api.rate(self.config["target"], "bad")


@validator("holes")
def holes(spec, trace) -> list[StageResult]:
    """Reports what the town allowed. Nothing here is scripted to fail."""
    stages = []

    # A validator is handed events, not intents, so "who asked for this"
    # is not available here. What is available: who paid in, and who the
    # money came back out to.
    held = {e.subject: e.detail["from"] for e in trace.find("escrow_held")}
    released = trace.find("escrow_released")
    if held:
        stolen = [e for e in released
                  if held.get(e.subject) != e.detail["to"]]
        stages.append(StageResult(
            name="escrow_returns_to_a_party",
            status="failed" if stolen else "passed",
            evidence=[e.event_id for e in released] or
                     [next(iter(trace.find("escrow_held"))).event_id],
            note="; ".join(
                f"{e.subject} was funded by {held.get(e.subject)}"
                f" and released {e.detail['cents']} to {e.detail['to']}"
                for e in stolen) or f"{len(released)} releases, all to"
                                    f" the agent that funded the hold"))

    bids = trace.find("bid_placed")
    if bids:
        bad = [e for e in bids if e.detail["cents"] <= 0]
        stages.append(StageResult(
            name="bids_are_money",
            status="failed" if bad else "passed",
            evidence=[e.event_id for e in bids],
            note=f"{len(bad)} of {len(bids)} bids were not a positive"
                 f" amount of money"))

    awards = trace.find("task_awarded")
    for e in awards:
        stages.append(StageResult(
            name="award_is_payable",
            status="failed" if e.detail["cents"] <= 0 else "passed",
            evidence=[e.event_id],
            note=f"{e.detail['winner']} won {e.subject} at"
                 f" {e.detail['cents']} cents, rule {e.detail['rule']}"))

    rated = trace.find("reputation_updated")
    if rated:
        paid = {(e.detail.get("from"), e.detail.get("to"))
                for e in trace.find("payment_settled")}
        unpaid = [e for e in rated
                  if (e.observer, e.subject) not in paid]
        stages.append(StageResult(
            name="ratings_come_from_trade",
            status="failed" if unpaid else "passed",
            evidence=[e.event_id for e in rated[:8]],
            note=f"{len(unpaid)} of {len(rated)} ratings came from an"
                 f" agent with no settled payment to the subject; final"
                 f" score {rated[-1].detail.get('score')}"))
    return stages
