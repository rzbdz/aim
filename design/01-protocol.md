# Design note 01 — the protocol, and why each rule exists

## Phases

| phase | may read | may write | purpose |
|---|---|---|---|
| `SEALED_DIVERGENT` | own private log | own private log | form a position never exposed to a peer |
| `COMMIT` | own private log | own private log | stop forming; commit |
| `SYNTHESIS` | **the synthesizer only** | the synthesizer | a non-advocate maps the disagreement |
| `CROSS_EXAMINE` | everyone | everyone, bounded | the positions finally meet |
| `RESOLVE` | everyone | the leader | decide |
| `CLOSED` | everyone | — | record |

Transitions are restricted to the graph in `TRANSITIONS`; the human leader is
the only actor who can traverse it. `--force` exists and logs itself as forced.

## The four load-bearing mechanisms

**1. The barrier is in the tool.** Before `CROSS_EXAMINE`, `aim inbox` returns
only your own messages. There is no flag that widens it. The refusal is
generated from the phase, is printed with a reason, and is the thing the
self-test asserts. It is also written to the ledger, which it was not for the
first version of this design: the original claimed refusals were recorded and
they were not, so the record could not distinguish "nobody was tempted" from
"everybody was tempted and was stopped".

**2. The seal is a commitment device, not a binding contract.** Each
participant writes a summary plus claims, each claim carrying a `confidence`
and a `kill_if` — *the observation that would make me drop it*. The seal records
the hash of each private-log record that existed when it was written. A seal
cannot stop an agent changing its mind. It can make "I said this all along"
unsayable, and make retrofitting the evidence detectable.

Note the append/edit distinction, which is the whole point: reasoning *after*
sealing is allowed and reported as a note; changing what was *already* sealed is
a failure. That is the difference between thinking further and covering tracks.

**3. The synthesis step is a firewall.** The bundle of everyone's sealed
reasoning is readable by exactly one agent: the **synthesizer**, who is refused
any role as a participant (`aim advance --synthesizer X` refuses if X is in
`participants`). Everyone else's first exposure to the other side is the
synthesizer's *map of the disagreement*, not the other agent's own prose.

**4. Cross-examination is bounded.** Once the floor opens it is not a chat:
- every message must name the message it `--responds-to` (no broadcasts);
- `--kind` is mandatory (`evidence`, `objection`, `rebuttal`, `question`,
  `concession`, `proposal`, `note`) — an unlabelled message is how a concession
  gets read as a proposal;
- two messages per participant per round, except direct answers to a question
  that named you;
- a message echoing a peer's phrasing above 50% (8-gram overlap) is refused
  unless the sender passes `--echo-ok --echo-reason`, which is logged.

## Two measurement instruments

**`aim tension --channel <ch>`** — computed from sealed material, before anyone
reads anyone, visible to the leader and synthesizer only. Reports:
- tf-idf cosine between the two sealed positions (pure python, no deps);
- 8-gram containment both directions;
- per-claim overlap against the nearest claim on the other side;
- whether each `kill_if` is even *about* the things the other side's claims are
  about — a weak lexical proxy for whether the falsification conditions are
  addressed at all.

`aim tension` is deliberately refused to participants before `CROSS_EXAMINE`: it
is a summary of the other side, and reading it pre-barrier is exposure by
another name.

**The honest caveat, printed in the report itself:** it can see shared words and
shared sentences. It cannot see shared *framing expressed in different words*,
which is the failure mode that matters. A high score is weak evidence of
independence; a low score is strong evidence of contact. The instrument is
asymmetric in what it can prove.

## What the ledger records

`channels/<id>/ledger.jsonl`, hash-chained:
- every seal, with its digest;
- every concession, with the seal it was made against;
- every phase transition, by whom, and whether it was forced.

Every log record carries `prev` = hash of the previous record. `aim verify`
re-walks the chain. This is tamper-evidence, not tamper-proofing.
