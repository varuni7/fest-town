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
0.021. It is unstable rather than milder. Early ratings are noisy, and whichever
stall gets a lucky first few reviews compounds. That is a feedback loop producing
variance rather than bias, and it is the open question here.

```
python sweep.py          # reproduces the table
```

## Reputation gaming

Ratings are cheap to send and nobody checks whether the sender ever bought
anything. One stall smears its rivals twenty five times. Four shill accounts
praise it eight times each. Nothing else about the fest changes.

| run | r (quality vs reputation) | ratings from non-buyers | ignored |
|---|---|---|---|
| `scenarios/rep_clean.yaml` | 0.85 | 0 | n/a |
| `scenarios/rep_attacked_naive.yaml` | 0.57 | 57 | 0 |
| `scenarios/rep_attacked_earned.yaml` | 0.67 | 57 | 57 |

`earned.v1` counts a rating only if the rater has a settled payment to that
stall, and only once per pair. Both facts are already in the trace, so the
check costs nothing extra.

Recovery is partial. The attack ran early, trade had already moved, and the
stalls that lost those sales never got them back. Filtering the ratings stops
the damage spreading. It does not undo it.

## Midway

One fest day, everything at once. Six stalls, three ticketed shows, a box
office that sells only in the morning, four shills, seventy fans and a hundred
and twenty attendees who each glance at three stalls before deciding.

Same seed, same crowd, same attack. The only difference is the trust layer.

| | `midway_naive` | `midway_earned` |
|---|---|---|
| r (quality vs reputation) | -0.48 | 0.86 |
| top seller | burger-3, quality 0.45 | burger-1, quality 0.85 |
| its share of trade | 49.2% | 39.2% |
| burger-1, the best stall | sold nothing | 47 sales |
| HHI | 0.336 | 0.251 |
| ratings ignored | 0 of 57 | 57 of 57 |

The naive run is the interesting one. Correlation is not merely weak, it is
negative: a buyer who read the scores and picked the top stall would do worse
than one who picked at random. The worst food at the fest took half the trade
and the best stall never sold a burger. Every money invariant passed the whole
time. No ticket was oversold, no transfer was unauthorised, the ledger balanced
to the cent. The fest was running correctly and producing the wrong outcome.

```
nandatown run scenarios/midway_naive.yaml
nandatown run scenarios/midway_earned.yaml
python fest_viz.py runs/<bundle> out.html    # time-lapse of the day
```

`fest_viz.py` reads a bundle and writes a standalone page: pixel stalls along
the midway, stages upstage, people walking to whatever they picked, the whole
day replayed in three minutes. It reads the evidence bundle only, so anyone
handed a bundle can watch the run without rerunning it.

## Stalls that set their own prices

`llm_stall` asks Gemini for a new price every five units, given its own sales,
its stock, and what it can see on the public cards. The floor and ceiling are
enforced in code, not by the prompt.

Across two runs, 14 of 16 price moves responded to demand in the right
direction: busy stalls raised prices 7 times out of 9, idle ones cut 7 out of
7. The spread between the cheapest and dearest food narrowed from 150 to 120
cents. Scripted stalls in the same scenario are the control.

```
GEMINI_API_KEY=... nandatown run scenarios/fest_pricing.yaml
```

## Invariants

Every stage is computed from the event trace, so a bundle can be replayed and
checked by someone who did not run it. They describe shapes rather than expected
traces, so the same checks hold at fifty attendees or five hundred.

**Ticketing.** No sale outside the advertised window. No show oversold. A settled
payment for every ticket. Every transfer made by whoever actually held the
ticket. One ticket, one entry.

**Gateway.** One payment buys one ticket. No ticket without a capture behind it.
No capture without a ticket, the one that matters to whoever paid.

Ownership is rebuilt independently from `ticket_issued` and `ticket_transferred`
events, so a box office that skips its own authorisation check is still caught.

## Negative controls

A validator that has never failed is not evidence that anything holds. Each
invariant is tested against a planted defect, and against an intact run facing
the same attack.

| scenario | what fails |
|---|---|
| `scenarios/gw_clean.yaml` | nothing |
| `scenarios/gw_lost.yaml` | `no_payment_without_ticket`, a fan paid and got nothing |
| `scenarios/gw_duplicate.yaml` | nothing; the idempotency guard holds |
| `scenarios/gw_duplicate_nodefence.yaml` | `one_payment_one_ticket`, two tickets, one payment |
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

- Midway, ticketing and gateway results are single-seed. Only the herding table
  is swept. The `-0.48` is one run of one fest, not an effect size.
- The gateway is still a separate scenario. Midway settles through the internal
  ledger, so it never sees a lost or duplicated webhook.
- The lunch rush is modelled in `gen.py` but not measured, and the hand-built
  midway crowd arrives at a flat rate. No stage asks whether a rush breaks
  anything.
- `every_stall_traded` counts only agents with role `stall`, so a `smear_stall`
  or an `llm_stall` is invisible to it.
- A webhook arriving four hours after the box office closed still issues a valid
  ticket. Nothing says a capture should expire. That is a policy decision nobody
  has made.
- `llm_stall` pricing is 16 moves across two runs. Whether adaptive stalls out
  earn fixed ones is not settled: the one mixed run that looked like evidence
  had no reprices land in it.
