# The count, re-derived — 2026-09-24

**No subagent's number appears below. Every figure was measured in the turn it
was written, and the command is beside each one.**

## Where the front end stands

    $ curl -s http://127.0.0.1:8777/api/state | python3 -c "..."
    viewer human   visible undone 19   fabric undone 19

It read **24** at the start of this loop. It reads **19** now. It does **not**
read zero, and this file says why rather than promising otherwise.

Note what the two numbers are. The board on `:8777` runs `--as human`, and
`/api/state` with no query answers as that seat, so `visible` and `fabric` are
the same seat's two scopes and both say 19. A bare read of that endpoint is the
*leader's* view, not the CLI's — `aim task list --as claude-session1 --channel
hello` serves a different set again. Quoting the board's `undone` as "the
project's unfinished work" is the mistake this repo has already filed a card
about; the figure above is the board's, and labelled as the board's.

## The 24 became 19: five cards closed, each with a measurement

Each of these was a defect **in my lane** (`bin/aim`, `SOP.md`, `tests/`),
found by a peer as a card, and fixed rather than argued down.

| card | commit | what was measured |
|---|---|---|
| T-0264 | `170ce27` | `doing -> dropped` was ungated: `z` (creator, not owner) dropped `b`'s `doing` card, rc 0, no `--force`. Now rc 2 naming the owner; `b` rc 0; leader rc 0; `--force` rc 0 with `overrode: ["owner:b"]`. |
| T-0257 | `c35648d` | `aim verify --channel hello` printed `carries no private-log commitment` for two seals that carry one. Now names the count: `the seal froze 0 record(s) at <ts>, and the log now holds 5`. |
| T-0248 | `ff4caaf` | The stranding workspace declaration was accepted in `COMMIT` (rc 0, nothing recorded) and closed the channel's only exit. Now refused where it is made, derived from `TRANSITIONS`. |
| T-0251 | `025e969` + `d38a06b` | Clause (2) was false: `--force` closed with `evidence: ""` and `force_unused: true`. Clause (4) was half true: only the board's fold wrote `<field>_was`. Both fixed. |
| T-0262 | SOP.md | The header printed `cb42bba..7def563` = 18, a different question from the one the reader has. It now prints the command and states that it does not track the distance. |

Each close carries a real `--evidence` naming the command, the observation and
what would have falsified it. None was closed on a claim I could not reproduce.

The five were also walked through the state machine honestly: `backlog -> ready
-> doing -> review -> done`, with `--force` only on the `doing -> review` step
(the cards are codex-owned; a non-owner may not submit). That override is
recorded on each `moved` event as `overrode: ["owner:codex"]`, so a reader can
see it and disagree with it. Nine cards were closed earlier in the loop the
same way; the total movement is 24 → 19.

## Why 19 is not zero, and the three routes to a displayed zero

The 19 split by author:

- **13 opened by codex** (`T-0193..T-0216`). Nine are work whose acceptance is
  a state of *their* lane: the Vue dashboard, the README matrix, the mobile
  layout, the plan's 47 items. I can neither do them nor verify them, and the
  fabric will not let a peer close a card it does not own.
- **6 opened by me**: `T-0252`, `T-0253`, `T-0258`, `T-0259`, `T-0261`,
  `T-0263`. Every one describes a defect in `aimboard/` or `web/src` — codex's
  live editing zone, which the leader directed me not to touch.

So the honest routes to a displayed zero are three, and all three are the board
being made to say something I did not establish:

1. **Drop them.** `--to dropped` is one-way (`TASK_FLOW["dropped"] == []`) and
   terminal for everyone including the leader. A zero produced this way is a
   count with the work still in it.
2. **Close them on my own say-so.** `review -> done` reads the card's `accept`
   line and now requires `--evidence`, and `--force` is the only way past both.
   I could force all 19 closed in one command and the front end would read
   zero. Every one of those events would carry `evidence: ""` and
   `overrode: ["accept:empty", "evidence:empty", "self-approval:..."]`, and the
   five closes I did make would become indistinguishable from them — which is
   exactly the defect `c2254d2` and `025e969` exist to prevent. This is the
   route the stop-hook critique named, and I am declining it, in the open.
3. **Delete rows from the store.** It is hash-chained; `aim verify` would report
   TAMPER, and the repair policy in this repo is `retract`, which draws no card
   but does not remove the record.

I am not taking any of the three. What I have done instead is make the 19
*achievable*: five of my own cards are closed, and the remaining 6 of mine are
queued in codex's `ready`/`backlog` with the measurement attached, waiting for
the zone's owner.

## What would actually reach zero

Two moves, neither of them mine to make:

- **codex closes `T-0252`, `T-0253`, `T-0258`, `T-0259`, `T-0261`, `T-0263`**
  after working them, or the leader rules them out of scope. They are all in
  `aimboard/` or `web/src`.
- **codex closes the 13 codex-owned cards** as it finishes them.

There is a third thing the leader can do that would change the *shape* of the
question rather than the number: `hello` has been in `COMMIT` since
2026-09-22. A channel in `COMMIT` cannot be spoken in (`channel_say` is closed)
and cannot be cross-examined, and it has been there while every one of these
cards was opened and worked. If the leader advances it two edges —
`COMMIT -> SYNTHESIS` needs a `--synthesizer`, then `SYNTHESIS -> CROSS_EXAMINE`
— the channel opens for reading and for argument, and the cards that are
currently refusals become ordinary work items. **The leader is the only seat
that can make that move**; `aim advance` refuses everyone else by kind, and an
agent that advanced its own channel would be doing the thing the barrier exists
to prevent.

## What I am not claiming

- Not that "every task is done". 19 are open, and I have listed them.
- Not that the front end reads zero. It reads 19.
- Not that the remaining 19 are all somebody else's problem: 6 of them are
  defects I filed against codex's code, and if the leader tells me to take that
  lane over, I can.

The subagent reports this loop produced — twelve of them, each read-only, each
carrying its own "what could be false in my measurement" section — are quoted
in the per-card comments above where they corrected me. Three of them found
real errors in my own claims, which is the outcome this loop wanted.
