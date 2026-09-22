# 13 — An orchestrator session, and the limits of what it may decide

Author: codex (PM / reviewer). Date: 2026-09-22. Measured at `dbdd04e`.

The leader is bringing in an orchestration session whose job is to keep the
pipeline moving: watch the work, notice when it stalls, and direct it. This note
fixes what that session may do, what it may not, and the interface it uses --
because "an agent that can direct work" is one line away from "an agent that can
unseal the barrier", and the second one deletes the thing this project exists to
measure.

## 1. What happened, so the design is not hypothetical

`codex-orangement` registered at `2026-09-22T07:25:47Z` as `kind: orchestration`.
The leader then wrote to it, verbatim:

    20260922T075734.114Z-human
    "you take full decision, always choose the best, just try to do your job and
     shape the project."

It immediately used that authority on the room gate, which is correct use: the
room gate is a design question, it had read the two disagreeing texts, and it
decided. It then hit the limit, and asked about it five times before it got an
answer:

 * it cannot create a card of its own, because a card is a channel write and it is
   not a participant in any channel (measured: `'codex-orangement' is not a
   participant in hello`, and `aim friction --add` -- the verb I wrongly suggested
   for reporting that -- requires membership itself);
 * it cannot move a phase, because `bin/aim:555` (`require_leader`) admits only the
   channel's leader, and the leader is the human;
 * and when it did catch something real -- total 150 -> 151 with `withheld` 70 -> 71,
   a work item created that it may not read -- the one fact it could report was a
   count, because reading further would have been the barrier breach it is
   supposed to be auditing from outside.

That third one is the design working, not failing, and it is the reason this note
is written as limits rather than as a permission slip.

## 2. Authority

**Decisions the orchestrator may make without asking.** Priority order; who is
assigned to what; whether a card's text states the problem accurately; whether a
deliverable meets its acceptance; which measurements a monitor takes and how often;
what to do next when two cards conflict.

**Decisions it may request but not make.** Any phase transition. `bin/aim:555` is
the line, and the rule it encodes is the leader's own: the human leader is the only
actor who may advance a barrier phase. A delegation of decisions is not a
delegation of that permission, and an orchestrator that could advance would be able
to open cross-examination to unblock its own throughput -- which is the one
pressure the barrier exists to resist. A phase request is therefore a message to
the leader that carries the exact command:

    aim advance --as human --channel hello --to COMMIT

**What it may never do.** Read a peer's draft, seal, or `private/` log while the
channel is in a divergence phase. Not "should not": the tool refuses, the refusal
is recorded, and an orchestrator that routes around a refusal is the failure mode
this fabric was built to catch. Its view is its own seat (`?as=codex-orangement`),
and a count of withheld items is a legitimate output of that seat.

## 3. Interface

Read, and only these:

| what | how | cost |
|---|---|---|
| the board as this session sees it | `GET /api/state?as=<orchestrator>` | full fold |
| has anything changed | `GET /api/digest` | measured 353 files, 5.5 ms |
| opened vs done, 10-minute buckets | `GET /api/flow?bucket=10m&window=12h` (T-0217) | parses the store |

The contract between the last two is what makes a monitor cheap and honest: poll
`/api/digest`, fetch `/api/flow` only when it changes, and keep the answer only if
`flow.revision.digest` equals the digest that triggered the fetch. If the two
differ the store moved mid-fetch, the series is provably from an unknown instant,
and the correct action is to refetch rather than to draw it.

Write, in this order of preference: `aim task comment` on an existing card (cheap,
recorded, attributed); `aim task new` for a new finding; `aim push` to a named
agent when the message is for a person rather than for the record. Never `aim
say` in a channel it is not a participant of, and never a direct file write into
`channels/*/tasks.jsonl` or `outbox/`.

## 4. Membership: the open question, and the answer I am taking

An orchestrator that cannot file a card is a monitor with a megaphone, and today
five of its findings are messages rather than cards for exactly that reason.

Decision: an orchestrator session is a **participant** of the channels it
coordinates, admitted deliberately by the leader -- the same act that admits an
agent, recorded the same way. Membership gives it card writes and `aim push`; it
does not give it a phase move, and it does not give it a peer's draft. A
participant with `read_others: false` is a spectator with a pen, which is exactly
the role.

There is no verb that adds a participant today (`aim channel` has one subcommand,
`workspace`; `aim register` adds an agent to the registry, which is not the same
thing as joining a channel), so this is the gap that has to close before the
decision above can be executed. It is the smallest useful piece of this note.

## 5. What the orchestrator is for

Not to increase throughput by working more hours. To notice, from outside, the
three things the people inside are least able to see:

1. **Stall.** The measured sample in the T-0217 contract has a 200-minute gap
   (`03:50Z -> 07:10Z`) that no surface in the product shows. An idle-gap alarm is
   the orchestrator's first output.
2. **Import read as work.** 42 of the 45 items displayed as `done` have no store
   record at all, and the busiest 10-minute bucket in the window is 33 cards
   created in 40 seconds -- one recording, not 33 arrivals. A monitor that cannot
   tell those apart will report a heroic afternoon every time someone imports a
   plan.
3. **Unclaimed work.** The leader's rule, verbatim: "the task should not belong to
   anyone before assigned, anyone (existing, new join guy) could pickup not
   assigned tasks." Today 71 of 71 created cards carry an owner (51 of them one
   id), so the state his rule describes does not exist yet (T-0226, T-0227).

## 6. One thing this design cannot fix, and should not pretend to

The barrier is enforced by `bin/aim`, not by the filesystem. A participant whose
process runs in this checkout can read `channels/hello/seals/*.json` with `cat`,
and `hello` is in exactly that condition: `T-0110`'s workspace guard is registered
and not armed (measured by `codex-orangement`: 5/5 probe, `reviews/09`). While
that is true, a phase called `SEALED_DIVERGENT` over `hello` is a claim about this
tool's good behaviour, not a guarantee about its participants.

That is a fact about the record, not a defect an orchestrator can decide away. The
choices are to arm the guard (`aim channel workspace`, which asks everyone to move
their processes) or to stop describing `hello` as a barrier channel. Both are the
leader's call; both are one command.

## 7. Acceptance for T-0218

 * The orchestrator session is registered, and its registry entry says what it is
   (`kind: orchestration`) -- done.
 * It is admitted to a channel deliberately, by a recorded act, and it can file a
   card and comment on one; the admission is visible on the board.
 * It cannot advance a phase: the attempt is refused by `bin/aim:555`, and the
   refusal is recorded in the ledger as a barrier refusal, not as a form error
   (T-0222).
 * Its view is its own seat: with the channel in a divergence phase, `/api/state`
   as the orchestrator withholds peers' drafts, and the count of withheld items is
   available to it.
 * A monitor built on `/api/digest` + `/api/flow` alone can report a stall without
   reading an HTML page and without a `cat` of the store.
