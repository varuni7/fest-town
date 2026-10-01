# holes

Six things the fest ran into that are nandatown's, not the fest's. Each one
is a scenario you can run. None of them is fixed by
[PR #1](https://github.com/dhve/nandatown-local/pull/1), which only covers
malformed amounts.

```
nandatown run holes/escrow_theft.yaml
nandatown run holes/negative_bid.yaml
nandatown run holes/grief.yaml
```

### 1. Escrow does not bind the caller

`escrow_release(ref, to)` and `escrow_refund(ref)` take a ref and nothing
else. Any agent that knows the ref can release the hold to any account,
including its own. The hold records who funded it and never consults that
field.

    job-1 was funded by buyer and released 5000 to stranger

`ledger_conserved` passes in the same run. Conservation catches money being
created, not money going to the wrong party.

### 2. Bids are not money

`bid(task_id, cents)` skips the amount validation that `pay` and
`escrow_hold` now have. A negative bid wins a lowest-bid auction.

    cheat won build-1 at -100000 cents, rule lowest

The award is then unpayable: escrow refuses the amount, so the run dies at
settlement after the auction has already been decided.

### 3. Ratings need no trade

`rate(subject, outcome)` requires only an attestation. One agent moved a
stranger's score to -50 in a single burst, having bought nothing and sold
nothing.

    50 of 50 ratings came from an agent with no settled payment to the
    subject; final score -50

The fest ships `earned.v1` as one answer, in `fest_earned_trust.py`: count a
rating only from an account with a settled payment to that subject, and only
once per pair. Both facts are already in the trace.

### 4. Validators cannot see intents

`Trace` wraps events only, and `evaluate_scenario(spec, run_id, events)` is
never handed the intents. So a validator cannot ask who requested an action,
which is exactly the check hole 1 needs. The intents are in the bundle as
`intents.jsonl`, so the data exists and only the evaluator is blind to it.

### 5. `rate` and `attest` crash on an agent that has not spoken

An identity is created lazily by `send()` or `register()`. An agent whose
first act is `rate()` gets `KeyError: no identity for <name>` out of the auth
layer. That kills the run and no evidence bundle is written, so the failure
leaves nothing behind to read. See the first lines of `Griefer.on_start`.

### 6. Pinned card digests are printed truncated

In Path mode, `agent_card_retrieval` prints `observed card
sha256:<16 hex chars>` of a 64 character digest
([path_runner.py:264](../../nandatown-local/src/nandatown/path_runner.py)).
Feed that printed value back as `--pin-card-digest` and
`descriptor_consistency` fails with a note that shows the two digests as
identical, because that note truncates as well (lines 289 to 290). The
comparison itself is correct. The loop of read a value, pass it back, get an
unreadable contradiction is not.
