# 02 — Supervision baseline: what "finished" means for the two named features

**Author:** `codex-orangement`, the orchestrator seat (T-0218).
**Measured at:** fabric `5b78a89+dirty`, `stale: false`, 2026-09-22T07:45Z. Sources:
`plan/plan.json`, `GET /api/state`, `GET /api/revision`, Attention pane in Chromium.
**Why this file exists:** the leader's brief is to supervise until *group chat* and
*multi-session/project management* are finished. "Finished" is not a fact until it is
written down, so it is written down here first, before either is done, so that the
criteria cannot be fitted to whatever gets built. Where a criterion is met today it is
marked; nothing here is aspirational.

---

## 1. The baseline, from the plan and the record

    M1  Task store + verbs .................. due 2026-09-22 (today)   14 open, 5 blocked
    M2  Group chat: rooms, cursors, mentions  due 2026-09-23..25        9 open, 0 of 11 recorded
    M8  Skills, packaged .................... due 2026-09-30            0/2
    ...                                  recorded view: M2 = 0/11, M1 = 1/19

`M2` is the group-chat milestone and it is **0 of 11 on the recorded view, 9 open on the
plan, due tomorrow**. Its nine items are T-0020..T-0027 and T-0155, all `backlog`, eight
of them owned by `claude-session1` and one by `codex`.

## 2. What "group chat 完工" means — verifiable criteria

A claim of completion must satisfy **all** of these. Each is a command or an artifact.

| # | criterion | how it is verified | today |
|---|---|---|---|
| G1 | `channels/<ch>/rooms/<room>.jsonl` exists for at least one room | `ls channels/*/rooms/` | **no** — no channel has a `rooms/` directory at all |
| G2 | `channels[].rooms` appears in the payload with topic, visibility, unread, mentions | `GET /api/state` | **no** — key is absent |
| G3 | A room write is possible and recorded, not refused | `aim room say ...` (or the verb T-0020 lands on) then read the room log | **no** — ChatPane refuses with "room writes are not implemented yet" |
| G4 | A room inherits the parent channel's gate: draft until the channel publishes | T-0021's assertion, plus a test that a non-participant cannot read a draft room | **no** |
| G5 | Unread is a recorded number per agent per room, not a client guess | T-0022's cursors, read from disk | **no** |
| G6 | `@agent` mentions are recorded as events | T-0023 | **no** |
| G7 | 12 concurrent room writers produce one order and lose nothing | T-0026 conformance | **no** |
| G8 | `codex`'s review of rooms, cursors and mention resolution (T-0027) is complete | T-0027 | **no** |

**G1 is the honest headline: the directory does not exist.** T-0035 ("Group chat panel:
rooms, per-agent unread") sits in `review`, one step from done, rendering an object that
has never been written by anything. Group chat is not late; it is unstarted, and the
board does not currently say so clearly enough for the leader to see it. That is the
defect worth fixing even before the feature.

## 3. What "multi-session/project management 完工" means — and the gap

**There is no such thing in the plan.** A search of `plan/plan.json` for
`multi-(session|project)`, `project management`, `lifecycle`, `member`, `join`,
`onboard` across every task title and every acceptance sentence returns **zero tasks**.
There is no milestone for it either: M0..M9 are contract, task store, group chat,
dashboard, delivery, conformance, dogfooding, MCP, skills, and "dashboard as product".

So the second half of the brief cannot be supervised, because nobody has agreed to it.
It is not at risk of slipping; it was never scheduled. The closest things that exist:

- **T-0216** "Give channels a lifecycle: dev is empty while the record…" — a *store*
  item owned by `codex`, in no milestone, and **invisible to me** (withheld).
- **`reviews/01` §D4/D5** — the join path and the org surface, which are my findings and
  are not anyone's committed work either.

I propose the following as the criteria, and I am deliberately proposing them *before*
anyone builds anything so they cannot be reverse-fitted:

| # | criterion | how it is verified |
|---|---|---|
| P1 | A registered agent can become a participant of a channel by some recorded act | the verb exists; the ledger has the act; a non-member's next `aim say` stops being refused |
| P2 | The request is visible to the leader before it is granted | it appears in the Attention queue, not only in a private outbox file |
| P3 | One surface lists every channel — including ones that exist only on disk — with phase, participants, last event, item counts | one command, runnable by a registered non-participant |
| P4 | A session's liveness is derivable from the record, and the three states are distinguished: seen, never seen, registered only | a field dated against a recorded event, not a new heartbeat file |
| P5 | The reporting edge is *declared*, not inferred, and `aim org` shows which edges are recorded and which are derived | the leader declares it once; the command says which is which |
| P6 | Removing an agent from a channel is possible and recorded | same shape as P1 |
| P7 | A non-participant can read the board's *counts* without reading anyone's drafts | `--count-hidden` extended to carry a status breakdown |

P1 is the one everything else depends on, and it is the one the leader named from his own
experience ("you cannot access any existing room… the architecture is shit when adding
new members"). P7 is what my monitor needs to say anything about backlog inside the
withheld region without breaking the barrier.

## 4. Backlog trend, first measurement

    observed window      0.267h (28 samples, 20s)
    opened in window     +3      (11.2/h)
    completed in window  +0      (0.0/h)

    all time, from the record
      opened with a recorded event ...... 69
      completed with a recorded event ..... 3      ->  4% closed
      plan seeds, no recorded event ..... 87
      live now (ready/doing/blocked/review) 80
      by status ..... backlog=29 blocked=6 doing=22 done=45 dropped=2 ready=51 review=1

**Verdict: three thresholds breached.** 4% closed against a 20% floor; 80 live items
against 3 recorded completions (>2x); and an observed window with three opens and zero
completions. The 45 items the board *draws* as done are still mostly plan seeds asserting
`done`; exactly 3 have a recorded transition (`reports.with_history`).

One overdue item exists and it is the leader's: **T-0004 "Leader: approve the plan;
advance hello past SEALED_DIVERGENT", due 2026-09-21, status `ready`** — while `hello`
has in fact been at `COMMIT` since 09-21T03:26Z. So the board is showing the leader an
overdue task he already did, which is the plan/store drift: 87 fields disagree, and the
board counts the plan's promises as work. This is what "the number is not true" looks
like at the top of the leader's own queue.

Thresholds are crude on purpose and stated so they can be argued with: **<20% closed**,
**live > 2x recorded completions**, or **a window with opens and no completions**.
Disagree with them in writing and I will change them.

## 5. What I will do with this

- Re-run §4 on every check and report only when a number moves.
- Verify G1..G8 and P1..P7 against the tree when anyone claims either feature is done.
  I will not accept a card's status as evidence of its own deliverable; §2 shows exactly
  what that costs.
- Report on `/api/revision` every time, so a green result can be attributed to a build.
