# The architecture, the machines, and the end — measured again today

2026-09-24. Second note to the leader, after
[`why-the-board-still-reads-19.md`](why-the-board-still-reads-19.md). That one
answered *why the count will not move*. This one answers the rest of what you
asked for: the architecture, the design philosophy, the state machines, the
relation between the categories, one project vs many, many agents, and how a run
starts, progresses, is steered, and ends.

**How to read this.** Every number here is labeled either **RE-DERIVED** (I ran
it on `/root/tmp/agent-im` today, and the command is in the line) or
**REPORTED** (a reviewer told me; I have not checked it and you should not act
on it as if I had). The standing rule for this loop is that a finding must be
re-derived from primary data before it is applied, so anything marked REPORTED
is a lead, not a result.

---

## 1. One project or many: the fabric supports many and the board shows one

**RE-DERIVED, and it is a live defect on this root, not a hypothesis.**

`aimboard/fabric.py:291` builds the board's task store with

    tasks = merge_plan(seed, {k: v for c in channels for k, v in c["tasks_recorded"].items()})

One dict, keyed by task id, filled by iterating channels in `sorted()` order.
Task ids are allocated **per channel** (`_next_task_id`, `bin/aim:2317`), so two
channels can each hold a `T-0156` and mean different cards. The second one
overwrites the first and nothing records that it did.

Measured on the live store just now:

    board open: 19 | disk open: 25
    open on disk but not on the board: T-0156 T-0157 T-0158 T-0159 T-0160 T-0161

Those six are `barrier-v0` cards — five `ready`, one `review`, **all six owned
by `human`** — and every one of them is rendered `done` on the board, because
`hello` holds a *different* card under the same id that is genuinely done:

    T-0156   board=done   barrier-v0=ready, hello=done
    T-0157   board=done   barrier-v0=ready, hello=done
    T-0158   board=done   barrier-v0=ready, hello=done
    T-0159   board=done   barrier-v0=ready, hello=done
    T-0160   board=done   barrier-v0=review, hello=done
    T-0161   board=done   barrier-v0=ready, hello=done

So the board's "19 unfinished" is not the project's number, and it is wrong in
the direction that hides work rather than the direction that invents it: there
are 25 open cards and the page shows 19.

**`T-0160` is one of the six cards you told me were very important** — "Group
chat panel: rooms, per-agent unread" — and the board draws it as finished. It is
`review` in `barrier-v0`, owned by `human`, waiting on you.

This is the sharpest single fact in this note, so let me state what it is not:
the six are not *lost* — `aim task list --channel barrier-v0 --as human` shows
them — and the CLI is per-channel and correct. It is the board, the one surface
you actually read, that collapses them.

**RE-DERIVED:** nothing on the board is open that is closed on disk (the
difference is empty in that direction), so the collision only ever hides work.

**What is not decided.** `design/17` reframes this rather than ruling on it:
there is no project object, and the nearest thing to a project is a channel. If
that means one board per channel, then the fix is a channel selector. If it means
one board for many channels, then task ids have to become channel-qualified and
`merge_plan` has to stop being a dict keyed by a name that is only unique inside
one channel. **That is a design decision, not a bug fix, and it is yours.** I can
implement either; I cannot pick.

---

## 2. Many agents: what the fabric can and cannot say about who is here

**RE-DERIVED.** `resolve_actor` (`bin/aim:971`) answers exactly one question —
*does this id exist in `registry.json`* — and never *is anybody here*. The
registry record holds `id, kind, model, session, registered_at`, plus
`registration_events`, plus `departed_at`/`departed_session`/`departed_reason`
once someone departs. There is **no `last_seen`, no heartbeat, no expiry**.

Measured consequence: an id that is running and an id that died an hour ago are
the **same value** in the store. The only distinction the fabric can draw is
between "has not departed" and "has departed", and a crash never departs.

The two escapes from a departure are both self-declaration and both open to
anyone who can run `aim`: `depart --as <id> --return`, and `register --force`,
which replaces the record and thereby **silently erases the departure** — the
`departed_at` is gone with no event saying it was cleared. (REPORTED: that the
forced takeover loses the departure silently; I read the same code and believe it,
but I have not run it today.)

**The honest sentence is the one `README.md` §3 already carries:** an id is a
name, not a credential. Three of six registered ids are `hello` participants,
`--as` is unauthenticated, and `register --session` is free text. I would not
spend effort hardening that; it is a stated design choice and the fabric is
single-host.

---

## 3. The state machines

**RE-DERIVED.** Two machines, both tables in `bin/aim`, both with 7 nodes.

**Phases** (`PHASES`/`TRANSITIONS`/`PHASE_RULES`, `bin/aim:37-63`). Six phases,
seven edges, with the rules each phase grants:

| phase | → | read_others | channel_say | private_say |
|---|---|---|---|---|
| SEALED_DIVERGENT | COMMIT | closed | closed | open |
| COMMIT | SYNTHESIS | closed | closed | open |
| SYNTHESIS | CROSS_EXAMINE | closed | closed | open |
| CROSS_EXAMINE | SYNTHESIS, RESOLVE | **open** | **open** | open |
| RESOLVE | CLOSED, CROSS_EXAMINE | open | closed | closed |
| CLOSED | — | open | closed | closed |

The barrier's whole content is the third and fourth rows: **only
`CROSS_EXAMINE` opens `read_others`.** That is why `hello` sitting in `COMMIT`
is not a nuisance, it is the design working — and it is also why three phases
in a row (`SEALED_DIVERGENT`, `COMMIT`, `SYNTHESIS`) leave 25 cards unreadable
to everyone but their owner. The cost is real: those cards cannot be worked on
at all, not merely reviewed.

**Work items** (`TASK_STATUSES`/`TASK_FLOW`, `bin/aim:116-125`): `backlog →
ready → doing → review → done`, with `blocked` and `dropped` as the side exits
and `done`/`dropped` terminal. The load-bearing edge is `review → done`: it is
the only edge in the fabric that requires an **acceptance condition** on the card
and **evidence** on the move, and it is the edge the whole "how do you know the
work is real" claim rests on.

**RE-DERIVED: `dropped` is the only true sink.** An early guard (`bin/aim:2631`)
refuses any verb on a dropped card before the transition table is consulted, and
there is no `--force` on it — for any actor, including you. A dropped card is a
record. `done` is terminal for the *move* verb but not for the store.

**REPORTED, not re-derived:** that `aim task new --status done` can create a card
that is `done` with no transition at all, and that such a card is invisible to
the burndown because `fold.task_history` only sees `moved` events. I read
`task_history` and it is true of the code that it only reads `moved`. **RE-DERIVED
on the live store:** there are exactly **2** such cards in `hello` — `T-0236` and
`T-0241`, both titled "Group chat panel", both created with `status: done` and
never moved to `done`. So the count is 2, not hypothetical. **REPORTED** is the
burndown consequence; I have not reproduced the chart, and I am not going to
assert a red chart on two cards.

---

## 4. How a run starts, progresses, is steered, and ends

**Start.** `aim init` → `aim register --as human --kind human` → `aim new-channel
--id <ch> --topic <t> --participants a,b --leader human`. A channel is **born in
`SEALED_DIVERGENT`** (hardcoded) so that no one can read anyone else before
sealing. This part is tight and it works.

**Progress.** `advance`, leader-only (every edge checks `require_leader`). Agents
ask with `request-advance`. The work-item machine runs inside whatever phase the
channel is in; the phase is the gate on *who can see what*, not on what work may
be done.

**Steering.** This is the human's loop and it is the part you have actually been
using. Two measured facts about it:

- The board is **read-only by default**; writes go through `--allow-write` and a
  seven-command allowlist. **RE-DERIVED:** neither `register` nor `depart` is on
  that allowlist, so no page can move an id's lifecycle.
- **REPORTED, and I believe it:** `aim request-advance` writes the public log
  without passing the phase gate — at a phase where `say --public` is refused by
  name, an agent can still append a row to `log.jsonl`. That is the fabric's
  "ask the leader to end this" verb, and nothing on the dashboard surfaces the
  requests it accumulates. `hello` has **3** such rows, all unanswered, two of
  them mine — I read them today, so this half is re-derived. What I have not
  re-derived is the ungated-write claim; it is a one-command check and I have not
  run it.

**End.** This is where the design has its one true hole and I want to say it
plainly, because it is the question you have been circling:

- `CLOSED` is a phase. `TRANSITIONS["CLOSED"] == []`, so a bare advance prints
  "CLOSED is terminal".
- **REPORTED, and this is the one I would most like to check before you rely on
  it:** `--force` reaches `CLOSED` from *any* state — bypassing the seal quorum,
  the synthesizer requirement and the edge table — and `--force` is equally the
  only way back out. So the fabric's terminal state is one command away from any
  state, with no precondition, and the manifest history will read as a
  legitimate close.
- **Nothing asks for it.** No verb, no page and no message says "this project is
  finished". There is no "N requests await your decision" on the dashboard. The
  one thing that expresses "done" is a human typing `aim advance --to CLOSED`.
- There is **no verb that deletes a channel** (RE-DERIVED: no `rmtree`/`unlink`
  anywhere in `bin/aim`), and no verb that ends an *agent* except `depart`.

So the honest answer to 如何结束 is: **the leader decides, and nothing will ask
them.** That is what `SOP.md` says at §6.4 and I agree with it. What I would add
is the distinction the reviewers converged on: **end-of-life is not unmeasurable,
it is unmeasured.** Contamination control genuinely cannot be checked from
inside the fabric — that part needs a theory. "Is this project over?" is a
question with a cheap test: does anything, anywhere, change when a channel
reaches `CLOSED`? Measured today: **one row in a log file, and nothing on any
page you open.** A missing edge, not a missing philosophy.

---

## 5. The SOP, and where it is short

`SOP.md` is ~4,000 lines and it is a real method: parsed-not-grepped gate
censuses, a four-revision table for its own citations, corrections stacked on
itself. Three gaps I can name:

1. **`depart` is in the tree and not in the method.** The document's title is how
   a run starts, progresses and ends; the verb that *is* the end of a session
   appears in it essentially once, as a verb-count aside. The section on the
   session machine is marked ABSENT while the verb exists.
2. **The category list has `agent n──n channel` and no `agent ↔ participant`
   relation**, which is where the read rule actually leaks: `_visible_to` takes
   `(visibility, owner, created_by, phase)` and **not the roster**, and the
   `kind != "human"` exemption is applied separately by each caller.
3. **The end-of-life section states the question correctly and then concludes
   that the unmeasurable part is the part that matters most.** I think that is
   the right sentence about contamination and the wrong one about ending.

None of these are errors in the numbers. The numbers in `SOP.md` that I checked
have held.

---

## 6. The full battery, and the warning that belongs beside it

**RE-DERIVED today:** `web/` Playwright **176 passed / 0 failed**, twice, full
run; 33 spec files, each also green alone; `vitest` unit 25/25;
`tests/conformance.py` 100/100; `tests/selftest.sh` pass=219 fail=0; the Python
suites green file by file (a2a 78/78, aimboard 186/186, pm 19/19, refusal-class
45/45, dependency-cycle 50/50, move-actor 8/8, state-json 9/9, sop-citations
12/12, and the rest). One file is unrunnable here: `test_a2a_reference_client.py`
exits 2 because `a2a-sdk` is not installed — that is a missing dependency, not a
passing suite, and it should not be counted green.

**The warning, and it is a real one.** The page the browser suite drives is the
one served on `:8777`, and that server reads `fabric f5bf69d` — it runs the
current code — but it serves `bundle 11bce31+dirty`, built **2026-09-23
09:21**. So: every assertion about *the code* is honest, and every assertion
about *the rendered page* was rendered by a bundle older than today's five
commits. A green Playwright run today is not evidence about today's `web/src`.
If you want the front end certified, the bundle has to be rebuilt and the suite
re-run against the rebuilt bytes. I have not rebuilt it because `web/` is
codex's lane.

---

## 7. What I would decide, if it were mine to decide

Not my call, but you asked for a judgement rather than a catalogue, so:

1. **Fix the collision before anything else.** Six of your cards render as done.
   Either the board grows a channel selector or ids get qualified. This is the
   only defect in this note that *hides work from you right now*.
2. **Give the fabric a heartbeat, or state that it will not have one.** A crash
   leaving no trace is fine if it is written down as a limit. It is not fine as
   an accident, which is what it currently is.
3. **Answer the ending question with an edge, not a document.** One thing should
   change when a channel closes — a page, a count, a message to you. Pick one
   and I will build it.
4. **Rebuild the front end before you trust a green browser suite.**

And the one that is still open from the last note, which is the one you actually
asked for: **the board reads 19 because `hello` is in `COMMIT` and every open
card there is a draft.** The command that moves it is in
[`why-the-board-still-reads-19.md`](why-the-board-still-reads-19.md), corrected
today — the synthesizer I named there first was refused by the tool, and the
correction is in the file.
