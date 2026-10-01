"""A stall that sets its own price.

The attendees stay scripted, so the crowd is still a distribution we
can reason about. Only the nine stalls think, and they think on a clock
rather than per customer: nine stalls repricing every five units across
a seventy unit day is about 126 calls, not one per transaction.

That buys the one thing a rule cannot give you, which is a decision
nobody wrote. It costs determinism: the same seed no longer reproduces
the same run. Every prompt and reply is recorded as an event so the
trace still says what happened, but a model is a mutable dependency and
the run is reproducible only in the weaker sense of being replayable
from its own record.
"""

from __future__ import annotations

import json
import os
import re
import time

import httpx

from nandatown.sim.agents import ROLES, role

# Plugin files are loaded by path, not placed on sys.path, so the base
# class comes from the role registry. fest_roles.py is listed first in
# plugin_files, so "stall" is already registered by the time this runs.
Stall = ROLES["stall"]

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODEL = "gemini-3.5-flash"
RETRIES = 3

SYSTEM = (
    "You run a stall at a college fest. You will be told your stall,"
    " your current price in cents, how many customers you have served,"
    " and what nearby stalls charge. Reply with ONLY the price in cents"
    " you want to charge next, as a bare integer. No words, no symbols,"
    " no explanation."
)


class _Brain:
    """One HTTP client shared by every stall in the run."""

    _client: httpx.Client | None = None
    calls = 0
    BACKOFF = 2.0

    @classmethod
    def ask(cls, model: str, prompt: str) -> tuple[str | None, str]:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            return None, "no key"
        if cls._client is None:
            cls._client = httpx.Client(
                base_url=GEMINI_BASE,
                headers={"Authorization": f"Bearer {key}"}, timeout=60.0)
        for attempt in range(RETRIES):
            try:
                r = cls._client.post("/chat/completions", json={
                    "model": model,
                    "messages": [{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": prompt}]})
                r.raise_for_status()
                cls.calls += 1
                return (r.json()["choices"][0]["message"]["content"]
                        or "").strip(), "ok"
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                resp = getattr(exc, "response", None)
                status = getattr(resp, "status_code", None)
                # 429 is a 4xx but it means "later", not "never".
                if status is not None and status < 500 and status != 429:
                    return None, f"http {status}"
                wait = cls.BACKOFF * (2 ** attempt)
                if status == 429 and resp is not None:
                    hdr = resp.headers.get("retry-after")
                    if hdr and hdr.isdigit():
                        wait = max(wait, float(hdr))
                last = f"http {status}" if status else type(exc).__name__
                time.sleep(wait)
        return None, f"gave up after {RETRIES}: {last}"


@role("llm_stall")
class LLMStall(Stall):
    """A stall whose price comes from a model instead of a config file."""

    def on_start(self) -> None:
        super().on_start()
        c = self.config
        self.model = c.get("model", DEFAULT_MODEL)
        self.every = c.get("reprice_every", 5.0)
        self.floor = c.get("floor_cents", 30)
        self.ceiling = c.get("ceiling_cents", 1000)
        self.last_served = 0
        # Spread the first call across the interval. Nine stalls asking
        # at the same logical instant is what tripped the rate limit.
        self.api.later(self.every + c.get("reprice_offset", 0.0),
                       self.reprice)

    def _neighbours(self) -> list[tuple[str, int]]:
        return [(s["name"], s["facts"]["price_cents"])
                for s in self.api.lookup(f"fest.{self.category}")
                if s["name"] != self.name]

    def reprice(self) -> None:
        since = self.served - self.last_served
        self.last_served = self.served
        nearby = self._neighbours()
        prompt = (
            f"Your stall: {self.name}, selling {self.kind}.\n"
            f"Your price now: {self.price} cents.\n"
            f"Customers served since you last set a price: {since}.\n"
            f"Customers served in total: {self.served}.\n"
            f"Nearby stalls: "
            + (", ".join(f"{n} at {p}" for n, p in nearby) or "none")
            + f"\nStay between {self.floor} and {self.ceiling} cents."
        )
        reply, why = _Brain.ask(self.model, prompt)
        new = self._parse(reply)
        if new is None:
            self.api.observe("reprice_failed", self.name,
                             {"kept": self.price, "why": why,
                              "reply": (reply or "")[:60]})
        else:
            old, self.price = self.price, new
            self._publish()
            self.api.observe("repriced", self.name,
                             {"from": old, "to": new, "served_since": since,
                              "nearby": dict(nearby)})
        if self.api.now + self.every <= self.api._engine.spec.max_time:
            self.api.later(self.every, self.reprice)

    def _parse(self, reply: str | None) -> int | None:
        if not reply:
            return None
        m = re.search(r"-?\d+", reply.replace(",", ""))
        if not m:
            return None
        return max(self.floor, min(self.ceiling, int(m.group())))
