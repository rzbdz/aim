# 12 — Architecture review, after one day of using it

Author: codex (PM / reviewer). Date: 2026-09-22. Measured at `d20a67b`.

This is not a critique written from reading the tree. It is what broke while the
fabric was used to build the fabric, in the order it hurt. Every claim carries a
number and a `file:line`, because a review that cannot say which revision it
measured is the failure mode this project was built to catch.

The one-line answer to "does the architecture need updating": **yes, in the data
model, not in the transport.** The file-first transport, the append-only record
and the barrier all held up under real use today. What did not hold up is that
the record has two authorities, the gate has phases that do not own their rules,
and the dashboard renders the record's *files* instead of the leader's *objects*.
Those three are the whole of it; the rest below is evidence.

---

## 0. The example that opens the case

The store contains a seed task, `T-0070`:

    title: "Record every work item of this project as a task in the fabric, not in a chat window"
    owner: codex   status: doing   provenance: "seed only (not yet in the store)"

The task that says *work must live in the record* is itself not in the record.
That is not irony; it is the structural defect (§1.1) making a small joke.

Concretely: 43 open items were assigned to me in `plan/plan.json`. The task store
held 4 of them. The dashboard's "Work needing you now", filtered to `codex`,
correctly showed nothing — and the leader found it before I did. An intention
that is not in the record does not exist, and the fabric had been exempting its
own PM queue from its own thesis.

Fixed today: 13 open codex items were recorded as `T-0197`…`T-0209`, tagged
`recorded-from-plan`. The rest of §1 is the fix for the cause.

---

## 1. Findings

### 1.1 Two authorities, one key — the deepest defect

**Measured.** `/api/state.tasks` is a dict of **141** entries. **87** carry
`provenance: "seed only (not yet in the store)"`, **54** carry `store only`, and
`/api/state.drift` carries **87** entries, every one of them
`{"field": "status", "plan": "…", "store": null}`. The two id spaces are disjoint
by construction (seeds `T-0001…T-0155`, store `T-0156…`).

**Cause.** `plan/plan.json` and `channels/<ch>/tasks.jsonl` are both authored by
hand, both authoritative, and merged at read time (`aimboard/fold.py`,
`merge_plan`). The merge is presented to the reader as one list plus a drift
list. Nothing can ever clear the drift, because there is no importer: only a
human retyping a task by hand can make the two agree.

**Why it matters more than it looks.** Every downstream confusion traces here.
The landing page counted 87 promises as work (T-0180). Gantt painted 42 of them
green as "done" (T-0188). "The store wins" was asserted about 87 rows whose store
value is `null` (T-0190). The leader cannot tell what is real because *two things
are real at once*.

**What the reader sees.** Re-measured today on the served bundle
(`assets/index-kt71uWBo.js`, viewer `human`): the drift card is **969px tall**,
draws **20 of the 87** rows, and ends "67 more, not drawn here." The receipts
tile says **7** while only **2** of those are addressed to the viewer. A promise
row reading `T-0004 … planned decision for you` carries exactly one control —
`open it` — and the drawer behind it offers `["Start doing", "Record this work
item"]`, which is a seed that cannot be approved because it is not in the store.
That is the shape of the leader's complaint, in numbers: two authorities produce
a card he cannot empty, a count that is not his, and a sentence advertising a
decision with no control to make it.

**Change.** `plan/plan.json` becomes an **importer**, not a co-author:
`aim task import --plan plan/plan.json` creates the missing items once, records
`imported_from`, and after that the store is the only authority. The drift
concept survives but changes meaning: it becomes a *reconciliation queue* whose
entries are actions ("import", "retire the plan entry"), and it must be possible
to empty it. Acceptance: after import, `provenance` is single-valued, and a test
asserts no task is reachable under two provenances.

### 1.2 The gate has phases, but the phase does not own the rules

**Measured, today.** The leader advanced `hello` to `COMMIT` with the stated
intent that "the recorded cross-examination can proceed". `aim status` then
reported:

    phase     COMMIT   round 0
    rules     {'read_others': False, 'channel_say': False, 'private_say': True}
    log       1 public messages      claude-session1  public=0

`bin/aim:55-62` is the cause: `COMMIT` and `SYNTHESIS` keep
`read_others=False, channel_say=False`. Only `CROSS_EXAMINE` opens reading. The
leader's `advance` therefore moved a label and changed nothing about what any
participant can do — and nothing on the board said so.

**Change.** The phase *is* the rules (one table, already nearly true) and the
tool must say what a phase change opened and closed, in those words, at the
moment it happens: "advanced to COMMIT — reading is still closed; the next phase
that opens reading is CROSS_EXAMINE." Acceptance: `aim advance` prints the diff
of the five rules it just applied; a test asserts that an advance which changes
no rule is labelled as such rather than reported as progress. This also answers
the leader's standing question on T-0178.

### 1.3 The payload is file-shaped, so the UI can only be a dump

**Measured.** `/api/state` keys: `generated_at, digest, as_of, statuses, terminal,
root, viewer, viewer_kind, write, phase, withheld_tasks, unplaced_events,
channels, tasks, milestones, reports, conversation, mail, unacked, drift,
register, agents`. That is the shape of the directory tree, not of a decision.

**Consequence.** The dashboard renders artifacts — drift rows, seal rows, ledger
events, refusals "0 of 0" over 497px, 5400px of Audit under one heading (T-0192)
— and the leader, opening it, says "I see a lot and I don't know what to look
at." He is not describing a styling problem. He is describing a surface that
never decided which objects it is about.

**Change — the object model.** Four objects, computed server-side, and every
pane is a view over them:

| object | is | carries | panes |
|---|---|---|---|
| `WorkItem` | a unit of work | id, title, owner, status, `estimate_hours`, milestone, blockers, provenance | Kanban, Gantt, Items, Plan |
| `Decision` | something only a human can settle | question, `because` (evidence), options, `actions[]` | Attention, the drawer, phase gates |
| `Conversation` | a thread between actors | participants, messages, unread cursor, receipts | Conversations, Overview |
| `Evidence` | what makes a claim checkable | hash-chained records, runs, refusals, digests | Audit, Help |

The load-bearing part is `actions[]`: every `Decision` and every `WorkItem`
carries the exact argv that resolves it, with the viewer's identity already
applied. **A control with no argv is a dead end and must not render.** That one
rule turns the leader's standing complaint ("I see T-004, I don't know how to
act on it") from a per-page fix into a schema requirement.

### 1.4 Invalidation has no scope

**Measured.** `aimboard/fabric.py:7` hashes the size and mtime of *every* file
under `registry.json`, `channels/`, `outbox/` and `plan/`. One write by any
actor — including my own task writes and mail bodies the board never renders —
changes the digest, so every open page is told the record moved, including pages
where nothing visible changed. That is the root cause of "the record has moved
since this page was drawn" appearing nearly everywhere, and of the click-to-
refresh the leader correctly rejected as the fix.

**Change.** Scope the fingerprint to what a view actually reads: derive a
per-query digest (view + filter set) instead of one global digest, so a change
that cannot affect the current view is not an event. Standard technique; nothing
here needs inventing. Acceptance: writing to `outbox/` changes no open page's
digest; writing a task that does not match the active filter changes nothing on
screen and produces no update line.

### 1.5 The vocabulary exists, but only in the browser

`web/src/concepts.js` (378 lines) already holds `PHASES`, `GLOSSARY`, `CONCEPTS`,
`ID_PREFIXES`, `PHASE_ACCESS`, `TRANSITIONS` — with a header stating exactly the
right rule: a concept must say what it *does to you*, and the raw protocol value
stays canonical but stops being the primary label. That work is good.

**Measured gap.** It is a front-end constant. `/api/state` has no `concepts` key,
so the API keeps emitting raw tokens and every surface re-decides what to call
them. `SEALED_DIVERGENT` still reached the leader as a primary label, `M`/`D`/`R`
have no way in (T-0185), and Help's identifier rows carry no `id` attribute, so
nothing could deep-link to them even if the registry were right.

**Change.** Serve the registry from the API and make it binding: any token the
API emits must resolve to a concept, asserted by a test that walks the payload
for unprefixed/unknown identifiers. `help#concept-<id>` anchors for all of them.

### 1.6 Delivery: one mutable bundle, no revision in the payload

**Measured.** One `python3 bin/aimboard.py serve` process serves one `web/dist/`
of hashed chunks. Consequences seen today: the leader hit a stale bundle; I
probed a stale bundle twice and nearly filed a finding against the wrong build;
Claude built and served *uncommitted* code, which produced a render error in
`TaskDecisionDrawer.vue` that stranded a full-screen overlay and bricked every
navigation until I fixed it (T-0184); the board on 8777 died twice. The payload's
`digest` says the record changed but nothing says **which revision of the
program** is answering.

**Change.** Build into a fresh temporary directory and swap atomically (standard
atomic-symlink deploy, a few lines); put the build's commit and dirty flag in the
payload and in the footer. Acceptance (T-0196): the served page states the commit
it was built from, and there is never a window in which `index.html` names chunks
that do not exist. A measurement that cannot say which revision it measured is
not a measurement — and that applies to the board itself.

### 1.7 The time model is a day wide, and the estimate unit is undeclared

**Measured.** The store field is `estimate_pts` (`bin/aim:1397`, `bin/aim:2842`).
It is rendered as **days** in Kanban (`web/src/panes/KanbanPane.vue:125`,
`{{ t.estimate }}d`) and in Gantt (`web/src/panes/GanttPane.vue:84`,
`(${t.estimate}d estimate)`), and as a **bare number with no unit** in Items
(`web/src/panes/ItemsPane.vue:79`, label `est`). Plan seeds use `1…5`
(33×2, 24×3, 18×1, 6×5, 1×4). `start`/`due` are `YYYY-MM-DD`.

The leader's correction is right and it is a model change, not a label change: an
LLM's unit of work is tens of minutes, and it does not work in parallel days. A
one-day granularity cannot express "this is 40 minutes" or "this is three hours
of my turns", and a `d` suffix on a number nobody agreed on is exactly the kind
of unverifiable unit this project exists to remove.

**Change.** One declared unit: `estimate_hours` (integer). Kanban/Gantt/Items
render `h`. Gantt bar width derives from hours, not from a date span. The 87
seeds are converted by one stated rule (`1 pt = 1 h`, printed in the migration
note) rather than by inventing per-task numbers, and `due` keeps day granularity
only for calendar-shaped commitments. Acceptance: no surface renders an estimate
without a unit, and the conversion rule is in the record.

---

## 2. What held up — do not "fix" these

- The barrier's refusals are the most valuable thing in the repo: a refusal is
  recorded, named and attributable. Keep it, even though the pane currently
  mis-instruments it (`refusals: 0 of 0`, and it counts my own transport probe as
  if the leader tried it — T-0192).
- One write path from the browser: the server's viewer is applied and any `--as`
  in the argv is dropped (`bin/aim:946` region, T-0141). Correct and load-bearing.
- The store as the authority, with events rather than mutations.
- Dogfooding produced every finding above. The architecture is being improved by
  using it, and that loop works.

## 3. Ranked queue

| # | Change | Owner | Card |
|---|---|---|---|
| 1 | Importer: one authority; emptyable drift | claude-session1 | T-0210 |
| 2 | `actions[]`: no control without an argv | claude-session1 | T-0211 |
| 3 | `estimate_hours`, unit on every surface | claude-session1 | T-0212 |
| 4 | Phase owns the rules; advance prints the rule diff | claude-session1 | T-0213 |
| 5 | Concepts served from the API; Help anchors | claude-session1 | T-0214 |
| 6 | Scoped invalidation (per-query digest) | claude-session1 | T-0215 |
| 7 | Atomic deploy + revision in the payload/footer | codex | T-0196 |
| 8 | Channel lifecycle: `dev` is empty and the real work is in `hello` | codex | T-0216 |

§3's ordering is deliberate: 1–3 are the data model, and doing 4–6 first would be
polishing a surface whose objects are still wrong.

## 4. What I need from the leader

1. **T-0191** — nothing exists above a task. Say either "promote milestones to a
   project/cycle object" or "there is no cycle model", and I will hold the board
   to it.
2. **T-0178** — may a phase transition that unlocks nothing be executed without
   approval? §1.2 makes this visible rather than silent either way.
3. Sign off on §1.3's four objects before Claude builds against them.
