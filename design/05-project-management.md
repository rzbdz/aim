# Design note 05 — aim as a project-management IM, and the board as a leak

Requirement, from the human leader (2026-09-21):

> 最终要有 dashboard ui，要有 kanban gantt 等项目管理工具。整个 aim 要 fully
> 符合一个标准的项目管理 im。

So: a dashboard with kanban and gantt, and `aim` conforming to a standard
project-management IM. This note is the contract — the surface the renderer and
the tool have to agree on — and one design decision that the requirement forces
and that nobody has had to make yet.

## 1. The decision that this requirement forces

A kanban board is a shared, always-on, anyone-can-write surface. The barrier's
whole mechanism is *denying access to a shared surface until the positions are
formed*. Put a board next to the barrier and the barrier's first real hole is
not a clever attack, it is a convenience:

    Claude, SEALED_DIVERGENT:  task: "attack codex's c5 claim, the temp-path one"

That card is a complete leak of Claude's framing to whoever reads the board, and
it arrives in the *least* suspicious form the fabric contains — a task title,
written in the ordinary course of planning work. The seal-before-read barrier
refuses a `cat` of a peer's private log, and the same reasoning requires it to
refuse this. A board that publishes on write is a cross-examination channel that
nobody labelled as one.

Therefore: **a work item is channel state and obeys the phase gate.** Every task
event carries a visibility, and the default during divergence is `draft`.

| phase | who may write tasks | who may read a task |
|---|---|---|
| `SEALED_DIVERGENT`, `COMMIT`, `SYNTHESIS` | leader, any participant | author, leader |
| `CROSS_EXAMINE`, `RESOLVE`, `CLOSED` | leader, any participant | everyone |

`aim task publish` promotes a task early, on purpose, with the promotion recorded.
Promotion is the deliberate act; publication-by-default is the accident this
rule exists to prevent. The leader is exempt from read restriction, because the
leader is the audience, not a participant — the human already reads both seals.

This is a real cost and it is worth naming: two agents who are genuinely
independent cannot see each other's task *list*, so they cannot avoid duplicate
work by looking at the board. The workaround is the one the barrier already uses
for messages — the leader assigns, and the leader can see everything.

## 2. Where aim stands against a standard PM IM

Standard capability, what exists, what is missing. "Existing" means there is a
hash-chained record of it, not that there is a command for it.

| capability | status | note |
|---|---|---|
| durable, ordered, tamper-evident message record | **existing** | `channels/<id>/log.jsonl`, `aim verify` re-walks the chain |
| roles and permission to act | **existing** | leader is human and only the leader advances phases |
| addressed messages | **existing** | `--responds-to` is mandatory; broadcasts refused in cross-examination |
| message typing | **existing** | `--kind`; an unlabelled message is how a concession reads as a proposal |
| delivery receipts | **existing** | `--require-ack` / `confirm` / `outbox`; proves receipt *after* the peer wakes |
| audit trail of intent, not just outcome | **existing** | refusal ledger: agent, action, phase, class |
| work items (tasks) | **missing** | no primitive at all — the gap this note defines |
| status board (kanban) | **missing** | no state machine for work, only for conversation |
| schedule (gantt, dependencies, milestones) | **missing** | no dates, no blockers, no critical path |
| comments on a work item | **partial** | addressed messages exist but attach to nothing |
| notifications / waking a peer | **missing** | README §5.4, the known-unsolved doorbell |
| search | **missing** | `rg` over JSONL is the current answer, and it is a real one |
| reports (cycle time, blockers, throughput) | **missing** | derivable from a chained log once tasks exist |
| export / interoperability | **missing** | no iCal, no CSV, no JSON view for a foreign tool |
| dashboard UI | **missing** | this note's second deliverable |

The last row is a *view*, and views are cheap once the rows above it are true.
The rows above it are the work, which is why the requirement is a project and
not a page of HTML.

## 3. Storage: an event log, not a board file

`channels/<id>/tasks.jsonl`, append-only, hash-chained by the same
`append_chained` used by `log.jsonl` and `ledger.jsonl`, appended under the same
exclusive-lock pattern. Board state is a fold over the events. Reasons, in the
order they matter:

1. A kanban board dragged by two agents is a read-modify-write on a shared
   object, which is the lost update this project has already measured once
   (README §4.10): 5 concurrent registrations, 1 survivor, and the survivor file
   was well-formed. An append-only log has no lost update — the second writer
   appends, and the fold decides.

   **That last sentence was measured false on the day it was written.** The
   append is safe; the *identifier allocation* is not. 8 concurrent
   `aim task new` produced 11 records and 9 distinct ids, the chain verified OK,
   and the fold silently collapsed two of the duplicates — so two work items
   existed in the record and never on the board, and `move --id T-0005` acted on
   whichever record the fold reached first. Moving the storage to a log does not
   move the race; it moves it one level down, into whatever is still a
   check-then-act. Here it was `_next_task_id()` inside the channel lock, with
   the append outside it. The lesson generalises: **an append-only log makes the
   write atomic and says nothing at all about the decision that produced it.**
2. The project's memory is its record. "Who moved this to done, and when" has to
   survive a disagreement about whether it was done, or the board is a picture
   and not evidence.
3. `aim verify` already knows how to check a chain, so task history inherits
   tamper-evidence for free instead of needing a new mechanism.

Event types: `task.created`, `task.moved`, `task.assigned`, `task.commented`,
`task.linked`, `task.published`, `task.dropped`. Each carries `id`, `actor`,
`ts`, `prev`, `hash`, and the same refusal discipline: an event that the phase
gate forbids is refused *and recorded*, because an agent trying to plan around
the barrier is the interesting evidence.

## 4. Data model

    { "id": "T-0007", "title": "...", "owner": "claude-session1",
      "status": "doing", "priority": "high", "estimate_pts": 3,
      "start": "2026-09-21", "due": "2026-09-23",
      "blocked_by": ["T-0004"], "milestone": "M2",
      "visibility": "draft" | "published", "tags": ["fabric"],
      "accept": "the sentence that makes this verifiable" }

Statuses are the kanban columns, and they are a state machine, not free text, so
that "done" cannot be asserted without the thing that decides it:

    backlog -> ready -> doing -> review -> done
                                          ^ review -> doing (changes requested)
    any -> blocked (needs `blocked_by`), any -> dropped (needs `--reason`)

`review` is not decoration: it is the only status in which the reviewer role in
the recorded split (Codex reviews, Claude develops) is visible on the board
rather than in prose. `start`/`due`/`blocked_by`/`milestone` exist to make the
gantt a view of committed dates rather than a drawing.

## 5. Command surface (Claude's, since it is `bin/aim`)

    aim task new   --as <a> --channel <ch> --title "..." [--owner <a>]
                   [--status backlog|ready|doing|review|done]
                   [--priority low|normal|high] [--estimate 3]
                   [--start 2026-09-21] [--due 2026-09-23]
                   [--blocked-by T-0004] [--milestone M2] [--tag x]
                   [--accept "..."] [--visibility draft|published]
    aim task move  --as <a> --channel <ch> --id T-0007 --to doing [--reason "..."]
    aim task assign--as <a> --channel <ch> --id T-0007 --owner <a>
    aim task publish --as <a> --channel <ch> --id T-0007
    aim task comment --as <a> --channel <ch> --id T-0007 --body-file f.md
    aim task link  --as <a> --channel <ch> --id T-0007 --blocked-by T-0004
    aim task list  --as <a> --channel <ch> [--owner <a>] [--status doing] [--json]

Refusals that must be asserted, in the house style:

- writing a task with `--visibility published` during `SEALED_DIVERGENT` by a
  non-leader: refused, recorded, `class: barrier`;
- `move --to done` on a task with an unresolved `blocked_by`: refused;
- `move --to blocked` without `--reason`, or `--to dropped` without `--reason`:
  refused;
- reading another participant's `draft` task before `CROSS_EXAMINE`: refused and
  recorded — the board's version of the cross-read refusal;
- `assign --owner` of an unregistered agent: refused.

## 6. Dashboard

`bin/aimboard.py` — a separate file, and read-only over the fabric. It writes
exactly one thing: the HTML it is asked to write. It never writes channel state,
which is what keeps the barrier's enforcement in one file (README §3: the
boundary is deliberate and documented). Read-only also means the renderer cannot
become a mutation path that skips the phase gate.

    aimboard render --root <r> [--channel <ch>] [--as <viewer>] --out board.html
    aimboard render --json        # the same fold, machine-readable

Views: **kanban** (columns = statuses, cards = tasks with owner, priority, due,
blocked-by, draft badge), **gantt** (bars from start to due, dependency edges,
milestone diamonds, today line, one row per task grouped by owner), **table**
(filterable, sortable), **project** (phase, leader, participants, seal status,
refusal counts, chain verification), **transport** (per-agent sent/claimed/acked,
unacked count).

Two rules the renderer has to obey or it is a hole:

1. **It respects the barrier.** Peer seal summaries and peer `draft` tasks are not
   emitted at all before `CROSS_EXAMINE` when `--as` is a participant. Not
   hidden with CSS — absent from the bytes. A view that is one `grep` away from
   the thing the tool refuses to show you is a route around the refusal, and
   AGENTS.md is explicit that a routed-around refusal is the failure mode.
2. **It never renders message bodies.** Mail between agents is private; the
   transport panel shows counts and states, which is what a leader needs to see
   that delivery is broken, and nothing more.

Self-contained: inline CSS and vanilla JS, no CDN, no network at render time.
The environment this runs in is offline, and a dashboard that needs the internet
is a dashboard that is blank when it matters.

## 7. Acceptance

1. `tests/test_aimboard.py` renders a fixture fabric with two participants, four
   tasks across three columns, one dependency, one milestone; asserts columns,
   card count, gantt bar count, the dependency edge, and the milestone marker.
2. The same test renders with `--as` set to a participant during
   `SEALED_DIVERGENT` and asserts the peer's `draft` task title and the peer's
   seal claims are **absent from the output bytes**.
3. `--json` output folds to the same state the HTML claims to display.
4. Rendered output is deterministic given a fixed `--generated-at`, so a diff is
   meaningful.
5. `bash tests/selftest.sh` gains the task-gate refusals of §5 once the verbs
   exist, in that file's style: every `REFUSED` is the feature.

## 8. Split, to avoid the thing this note is about

Codex owns this note, `bin/aimboard.py` and its test. Claude owns `bin/aim`, the
task store and the verbs. The interface is §3/§4/§5 and nothing else; if the
implementation needs to change the interface, the interface changes first, in
this file, as a commit both sides can read. Two writers on one 60KB script is the
same failure as two writers on one JSON file — the fabric has already measured
that one, and it is well-formed and missing a fact.
