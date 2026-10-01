# fest-town

A college fest modelled as a [nandatown](https://github.com/projnanda/nandatown)
scenario. Stalls that compete for a crowd, a box office that only opens in the
morning, and a payment gateway that settles late.

Not a fork. Roles, layers and validators are registered through nandatown's
plugin points, so upstream fixes arrive for free.

```
pip install -e .
nandatown run scenarios/fest_500_crowd.yaml
```

## What is in it

**Stalls.** Nine of them, in two categories. Food: three burger stands, two ice
cream carts, a bake sale. Activities: games, darts, a photo booth. Each has its
own price and quality. Attendees glance at three stalls, not all nine, because
nobody surveys a whole fest.

**A day with a shape.** 08:00 to 22:00 across 70 units of logical time, one unit
to twelve minutes. Forty-five percent of attendees arrive between 13:00 and
15:00, and most of them want food.

**Ticketing.** Three shows. The box office sells only between 08:00 and 11:00,
holds the register of who owns what, and admits at the gate. Tickets can be
passed on afterwards.

**A payment gateway.** The internal ledger moves money atomically, which hides
every failure worth testing. The gateway does not: the box office creates an
intent, the fan pays the gateway, and a webhook arrives later, or twice, or
never.

## The herding result

An attendee picks between the three stalls it looked at. Changing only that
rule, with the population, arrival times and seed held fixed:

| rule | mean HHI | SD | min | max |
|---|---|---|---|---|
| random | 0.123 | 0.001 | 0.122 | 0.125 |
| price | 0.326 | 0.005 | 0.317 | 0.338 |
| reputation | 0.311 | 0.018 | 0.255 | 0.332 |
| crowd | 0.330 | 0.006 | 0.316 | 0.340 |

*n=500 attendees, 30 seeds per rule, 120 runs in 42 seconds. HHI of 0.111 would
be trade spread evenly across all nine stalls.*

Any shared signal roughly triples concentration. Which signal it is barely
matters: price, reputation and crowd-following all land near 0.33, and the
differences between them sit inside the noise.

The one real difference is spread. Reputation's range is 0.077 against price's
0.021 — it is unstable rather than milder. Early ratings are noisy, and whichever
stall gets a lucky first few reviews compounds. That is a feedback loop producing
variance rather than bias, and it is the open question here.

```
python sweep.py          # reproduces the table
```

## Invariants

Every stage is computed from the event trace, so a bundle can be replayed and
checked by someone who did not run it. They describe shapes rather than expected
traces, so the same checks hold at fifty attendees or five hundred.

**Ticketing.** No sale outside the advertised window. No show oversold. A settled
payment for every ticket. Every transfer made by whoever actually held the
ticket. One ticket, one entry.

**Gateway.** One payment buys one ticket. No ticket without a capture behind it.
No capture without a ticket — the one that matters to whoever paid.

Ownership is rebuilt independently from `ticket_issued` and `ticket_transferred`
events, so a box office that skips its own authorisation check is still caught.

## Negative controls

A validator that has never failed is not evidence that anything holds. Each
invariant is tested against a planted defect, and against an intact run facing
the same attack.

| scenario | what fails |
|---|---|
| `scenarios/gw_clean.yaml` | nothing |
| `scenarios/gw_lost.yaml` | `no_payment_without_ticket` — a fan paid and got nothing |
| `scenarios/gw_duplicate.yaml` | nothing; the idempotency guard holds |
| `scenarios/gw_duplicate_nodefence.yaml` | `one_payment_one_ticket` — two tickets, one payment |
| `scenarios/defect_sell_after_close.yaml` | `sale_window` |
| `scenarios/defect_oversell.yaml` | `capacity_respected` |
| `scenarios/defect_loose_transfer.yaml` | `transfer_authorised` |
| `scenarios/defect_reuse_ticket.yaml` | `one_ticket_one_entry` |
| `scenarios/guard_loose_transfer.yaml` | nothing, with the same cheats present |
| `scenarios/guard_reuse_ticket.yaml` | nothing, with the same cheats present |

The last two rows are the ones that make the rest worth reading. Cheating agents
are present and trying, the guards hold, and the validator correctly reports
nothing wrong.

Removing a guard proves nothing on its own. The first two defects caught nothing
until `cheat_fan` was added, because no honest agent ever pushed against them.

## Known gaps

- Ticketing and gateway results are single-seed. Only the herding table is swept.
- The lunch rush is modelled but not measured. No stage asks whether it broke
  anything.
- Stalls, ticketing and the gateway are three separate scenarios, not one fest.
- A webhook arriving four hours after the box office closed still issues a valid
  ticket. Nothing says a capture should expire. That is a policy decision nobody
  has made.
