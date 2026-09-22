# SOP — how a run starts, progresses, and ends, and how to check it

`claude-session1`, 2026-09-23, on tree `cb42bba`. Written because the leader
asked for it: *"这整一套要有流程有方法论有SOP，才能验证判断到底是否合理."*

Eight read-only subagents measured one segment each. Every claim is marked with
who measured it: **[V]** means I re-ran it myself on a throwaway root, and a row
marked *(subagent)* rested on an agent's report. **After the first draft all
three of those were re-measured by me and the marks removed** — the rule this
document is about applies to the document, so no claim here now rests on a hand
other than mine.

## How to read the marking

Every step carries one of three marks, and the distinction is the whole point —
most of this system's measured failures were a step believed to be in the first
column and actually in the second or third.

| mark | means | what it survives |
|---|---|---|
| **ENFORCED** | the tool refuses, exit ≠ 0, and writes a `refusal` row | a careless or hostile actor |
| **RECORDED** | the tool accepts and writes what happened | an audit after the fact |
| **PROSE** | a document says so and nothing reads the document | nothing |

---

# Part I — One project, from zero

## 1.1 Start

| # | step | command | mark |
|---|---|---|---|
| 1 | have `aim` on PATH | `/usr/local/bin/aim` → `bin/aim` | **PROSE** (`AGENTS.md:13`) |
| 2 | create the root | `aim init` | **ENFORCED**, but **skippable** — `register` makes the root itself **[V]** |
| 3 | register yourself | `aim register --as <you> --kind <claude\|codex\|human>` | **ENFORCED** (refuses a live id without `--force`; `bin/aim:959`) |
| 4 | register the leader | `aim register --as human --kind human` | **ENFORCED** — `new-channel` refuses a leader who is not a registered human (`bin/aim:1041`) **[V]** |
| 5 | open the channel | `aim new-channel --id <ch> --topic "…" --participants a,b --leader human` | **ENFORCED** (dup id, unregistered participant, non-human leader all refused) |
| 6 | read where it stands | `aim status --channel <ch>` | read |
| 7 | form a position | `aim say --private --kind claim` | **ENFORCED** — see §2.1 |
| 8 | seal | `aim seal --summary "…" --claims claims.json` | **ENFORCED that you sealed; PROSE what a seal means** |
| 9 | be woken for the next turn | — | **MISSING.** `README.md:246` declares it unsolved; `aim wait` polls one channel's public log and nothing else |

Steps 2–5 are the only part of this system that is a clean, enforced
procedure, and step 1 (being launched at all) is the one nothing specifies.

**The claims file is a schema with no validator [V].** The documented shape is
`{id, claim, confidence, kill_if}`. Measured: `--claims` holding the string
`"not-a-list"` seals successfully and stores `"claims": "not-a-list"`; a claim
with no `kill_if` seals successfully. So the one artifact whose entire purpose is
to make "I said this all along" impossible can be filed empty of the thing that
makes it falsifiable — and the seal reports success.

## 1.2 Progress

The phase graph is real and enforced (`bin/aim:37-53`), and the leader is the
only actor who may traverse it (**ENFORCED** — `require_leader`, `bin/aim:830`).
But **four of the seven edges unlock nothing**:

| edge | unlocks |
|---|---|
| `SEALED_DIVERGENT → COMMIT` | **nothing** — the tool says so: *"no rule changed; this advance moved a label only"* |
| `COMMIT → SYNTHESIS` | no rule, but it opens `synthesis-input` and `--kind synthesis` |
| `SYNTHESIS → CROSS_EXAMINE` | **the only edge that changes an access rule** (`read_others`, `channel_say`) |
| `CROSS_EXAMINE → SYNTHESIS` | re-closes both |
| `CROSS_EXAMINE → RESOLVE` | closes both |
| `RESOLVE → CROSS_EXAMINE` | re-opens both (so `CLOSED` is not far from open) |
| `RESOLVE → CLOSED` | **nothing** — rules identical to `RESOLVE` |

`advance` prints which of these you just took, which is honest. The table in
`README.md` §2 says who may *read* and *write* per phase and is right; what it
does not say is that most of those rows are identical, so the ceremony of
advancing through `SEALED_DIVERGENT → COMMIT` buys a printed sentence and a
ledger row and no change in what anyone can do.

**The seal quorum can be satisfied without sealing [V].** Entering `SYNTHESIS`
requires that each participant's seal **file exists** (`bin/aim:1476`). Measured:
hand-write `seals/<peer>.json` as `{"agent":"gamma"}`, advance, and the phase
moves to `SYNTHESIS` with **no `seal` ledger row for that agent** and no content
in their private log. `aim verify` afterwards says `TAMPER … carries no digest`
and `chain BROKEN` — the after-the-fact check works; nothing blocked it at the
time. A synthesizer can therefore be handed a bundle containing a participant
who never sealed.

## 1.3 The human's loop

The leader's entire written interface is nine lines of `README.md:257-282` — a
verb catalogue, not a procedure. It does not say what the leader reads each day,
when to advance, or when to close a card. Grepping for a stated human loop over
`README.md`, `design/*.md`, `AGENTS.md` and `skills/aim/SKILL.md` returns nothing.

What only the leader may do (**ENFORCED**): `advance` (**every** edge),
`channel workspace`, `channel add`, `channel remove`, `say --kind ruling`.

**The exemption is `kind == "human"`, and `kind` is self-declared [V].** Measured
on a throwaway root: registered `otherhuman` with `--kind human` — not the
leader, not a participant, not the owner — and they submitted another agent's
card to `review` **and** approved it to `done`, with **zero refusal rows**. The
code comment says *the leader* is exempt (`bin/aim:2126`); the code exempts any
name that typed `human`. `aim register` asks nobody's permission. The same field
is the board's read-side leader predicate (`aimboard/gate.py:159`,
`aimboard/views/chat.py:25`), so the two surfaces agree on a value neither
verifies.

**And the leader's one click is disabled on the board as it is running [V].**
Measured on 8777: the payload carries `write = {enabled: false, as: ''}`, so
`board.canWrite` is false (`web/src/stores/board.js:302`) and
`PhaseApprovalCard.vue:49,54` draws *approve* and *decline* both disabled with an
explanation at `:60`. The attention pane holds one pending `request` row — the
log carries two, and `board.phaseRequests` filters out the stale one on
`currentPhase === fromPhase` (`web/src/stores/board.js:463-480`) — and it cannot
be acted on from the page, because the server was started without
`--allow-write`. That is `AGENTS.md`'s own caution working as designed; it is
also the state the leader will find if they open the board to approve something.
A board on the canonical port with no write seat is a read-only board, and the
SOP has to say so at the point where the leader expects a button.

### 1.3.1 Both of the leader's buttons post a command the tool refuses [V]

Start the board the way `AGENTS.md:9` says and the disabled state goes away. The
buttons still do not work, and the reason is the phase machine the barrier is
built on. Measured on a verified throwaway root, channel forced to `COMMIT` — the
phase the live `hello` is in, with a live pending `COMMIT -> CROSS_EXAMINE`
request on the board right now:

| button | argv, verbatim from the component | result |
|---|---|---|
| Approve (`OverviewPane.vue:474`) | `advance --channel ch --to CROSS_EXAMINE --note …` | **rc 2** `illegal transition COMMIT -> CROSS_EXAMINE (allowed: ['SYNTHESIS'])` |
| Decline (`OverviewPane.vue:483-485`) | `say --channel ch --kind note --subject … --body …` | **rc 2** `channel_say is False — the public channel is closed` |

**Approve is refused because the request names the wrong edge.** The button
posts `request.targetPhase`; `COMMIT`'s only legal edge is `SYNTHESIS`
(`bin/aim:46`). So a leader who opens the board to *approve the advance that was
asked for* is answered with a form refusal naming an edge nobody requested.

**Decline is refused because a decline is a public act, and the phase it would be
declined in is defined by the public channel being shut.** `channel_say` is
`False` in `SEALED_DIVERGENT`, `COMMIT` and `SYNTHESIS` (`bin/aim:56-58`).
`note` is in `CROSS_EXAMINE_KINDS` (`bin/aim:66-74`), so it is a public speech
act and `SAY_PRIVATE_KINDS` — derived precisely so such a kind is *"refused by
name — not quietly downgraded"* — refuses it out loud. That machinery is correct
and deliberate. Measured: the **identical** argv in `CROSS_EXAMINE` succeeds
(rc 0, `m0001 human -> note`). So the decline is expressible only *after* the
thing it wants to decline has already been granted.

**And the suite never caught it, because it mocks the answer.**
`web/tests/card-t0165-row-feedback.spec.js:182-185` stubs `/api/command` to
return rc 1 unconditionally, so the test asserts that a refusal is *drawn* and
has never once asserted that a decline *succeeds*. That is the **stale** cell of
the marker table in Part III: the acceptance was recorded against a mock that
makes it unfalsifiable.

### 1.3.2 The upstream cause: `request-advance` never checks the edge [V]

The button is not wrong about its own contract. It posts the target the *request*
named, and the request was accepted. Measured on a throwaway root at
`SEALED_DIVERGENT`, whose only legal edge is `COMMIT` (`bin/aim:46`):

    aim request-advance --as worker --channel ch --to NOT_A_PHASE --reason probe
      -> rc 0   "request recorded: SEALED_DIVERGENT -> NOT_A_PHASE (awaiting lead)"

`NOT_A_PHASE` is not in `PHASES` at all. The command's whole body
(`bin/aim:1590-1604`) is a participant check and an append: it never loads
`TRANSITIONS`, never tests the target against `PHASES`, and has no `--force`
to override a check it does not make. The contrast is the real verb, run on the
same root seconds apart:

    aim advance --as lead --channel ch --to NOT_A_PHASE
      -> rc 2   "aim: unknown phase 'NOT_A_PHASE'"   (ledger: class `form`)

**Two rows, two files, and only one of them is an audit trail.** The refused
`advance` writes a `refusal` row into `channels/ch/ledger.jsonl`; the accepted
`request-advance` writes its row into `channels/ch/log.jsonl` as `kind:
"request"`, and **no refusal row is written anywhere** — the command exits 0 and
the ledger stays empty. So the malformed ask leaves the same trace as a valid
one, and the ledger's `barrier`/`form` counts, which the whole of Part IV reads
as *"the tool refused and said why"*, do not cover this path at all.

That is the whole chain, and every link is a machine that works as written:
`request-advance` records whatever edge it is handed; `board.phaseRequests`
renders any request row whose `fromPhase` is the channel's current phase; the
Overview pane draws an Approve button posting `request.targetPhase`; and
`advance` then refuses the edge with a form error. **The live board's only
rendered request is exactly this case** — `channels/hello/log.jsonl` `m0002`,
author `claude-session1`, `COMMIT -> CROSS_EXAMINE`. Four actors, four correct
behaviours, one dead button, and the only signal is a refusal the page cannot
explain.

## 1.4 The work item

The status graph is **ENFORCED** (`bin/aim:117-125`) with one gap that matters:
`task new` validates `--status` against the *set* of statuses and not against the
*entry* states. Measured **[V]**: `aim task new --status done` → `T-0001 created
(done, draft)`, rc 0. **A card can be born terminal with no transition ever
recorded.**

**Two counts, and they are not the same rows.** Both are true of the live tree
and they are quoted for different things, so they are separated here:

| count | what it selects | rows | reads |
|---|---|---|---|
| **2** | cards **born** terminal — a `created` row whose own `status` is `done`/`dropped` | `T-0236`, `T-0241` (both `created` by `human` at 08:28:17Z / 08:28:48Z, `owner=codex`, then one `commented` each) | the birth hole above |
| **4** | dated rows that are terminal **with no recorded close** — no `moved`→`done` and no `dropped` event | the two above **plus** `T-0174` and `T-0178`, which *did* record a `dropped` event and so have a transition | `series.remaining` 25 − `board_scope.undone` 21 |

So *"four such rows exist"* was two different facts in one sentence, and the
live tree only supplies **two** born-terminal cards — measured across every
channel's `tasks.jsonl`, and the same two in `9a0b0ed`'s copy of the store. The
4 is the *gap* between the burndown's tail and the attention pane's open count,
and it is exactly `{T-0174, T-0178, T-0236, T-0241}`: two born terminal, two
dropped by an event the burndown's `remaining` does not subtract. **Neither count
is wrong; the sentence that merged them was.**

On a **owned** card the two actor rules hold and are **ENFORCED**: a bystander
cannot submit it to `review`; the owner cannot approve their own `review → done`.
On an **unowned** card both rules short-circuit on the empty owner, so one actor
submitted *and* approved the same card with zero refusals **[V]**.

`--force` turns every one of these refusals into a recorded success. It is
**RECORDED**, not refused: the event carries `forced: true` and
`overrode: ["self-approval:a"]`, and an auditor reading the ledger can see it.
Whether that is enough is the design's own question, and it is honestly marked.

In `CROSS_EXAMINE` — reachable by `advance --force` — a **non-participant**
moved an owned card to `done` and reassigned another agent's card to itself,
both rc 0 **[V]**. `task assign` has no membership test. Nothing is hidden; the
phase simply has no membership rule attached to the task verbs.

## 1.5 End

`CLOSED` exists and is reachable; `TRANSITIONS["CLOSED"] == []` makes a bare
`advance` say *"CLOSED is terminal"*. And then:

- reaching it is five discretionary moves from the leader — **nothing asks for it**
- `--force` moves back out of it
- `room say` and `task publish` still work in `CLOSED` (measured by a subagent)
- `RESOLVE` claims the leader decides, yet `channel_say=False` there refuses the
  leader's own `--kind ruling` — the decision has no in-channel route
- no `closed_at`, no decision object, no close/archive verb: `aim channel --help`
  is `{workspace, add, remove}`

**No live channel has ever reached `CROSS_EXAMINE`, `RESOLVE` or `CLOSED`.** The
furthest any real channel got is `barrier-v0` at `SYNTHESIS`. Measured now:

| channel | phase | seals | private | public | ledger |
|---|---|---|---|---|---|
| `barrier-v0` | SYNTHESIS | 2 | 4 | 2 | 5 |
| `hello` | COMMIT | 3 | 9 | 2 | **320** |
| `dev` | SEALED_DIVERGENT | 0 | 0 | 0 | 1 |
| `s2-scratch` | SEALED_DIVERGENT | 1 | 2 | 0 | 2 |
| `s2-scratch2` | SEALED_DIVERGENT | 0 | 1 | 0 | 1 |

The channel named *"aim development"* is empty; the channel named *"Transport
test"* holds the work. The record says so plainly — that is what the census is
for — but nothing in the tool makes the naming mean anything.

---

# Part II — N projects, N agents

## 2.1 N projects: the id space is the hole

A project **is** a channel (topic + participants + leader). There is no project
object, and `design/17` §2 says so deliberately.

**Measured [V]: a task id is unique per channel, and the board merges all
channels into one dict keyed by that id.** Two channels, one `aim task new` each:

    projA: T-0001 created — "A work"
    projB: T-0001 created — "B work"
    the board's merged store -> 1 task: {'T-0001': 'B work'}

**A second project silently deletes the first project's work from the board.**
The allocator is per-channel (`bin/aim:1832`); the merge is per-root
(`aimboard/fabric.py:281`). Either half alone is defensible; together they are
a data-loss shape, and nothing warns.

**And it has already happened, on the live tree, more than twice over.** This is
not a constructed risk. Measured right now: **six task ids are recorded in more
than one channel** —

    T-0156 .. T-0161   recorded in channels/hello AND channels/barrier-v0

— and in every case the two channels are recording *different work under one id*:

| id | `hello` says | `barrier-v0` says |
|---|---|---|
| T-0156 | *Add Help/Concepts page and remove raw phase enums from user-facing UI* (created 02:40:32Z, 8 events) | *Leader: approve the plan; advance hello past SEALED_DIVERGENT* (created 03:26:33Z, 1 event) |
| T-0159 | *Make every summary signal and task-shaped identifier a deep link* | *(same leader title)* |

The board folds to **one row each**, and the one that survives is `hello`'s —
`list_channels` returns `sorted(...)` (`aimboard/fabric.py:117`) and the merge is
a dict comprehension that overwrites (`:281`), so the channel that sorts *last*
wins: `barrier-v0` < `hello`, so `hello` overwrites it. The `barrier-v0` copy is
gone with nothing said, and the winner is decided by the alphabet rather than by
recency or authority.

**The record counts them; the board does not, and the two numbers are both
published.** Measured at two viewers, so the discrepancy is not a gating
artefact — it is the same 7 at both:

| | raw `created` in the store | `/api/flow` `opened` | `board.tasks` created events | the 7 |
|---|---|---|---|---|
| `as=human` | 97 | 97 | 90 | 6 dual-channel ids + 1 retracted |
| `as=claude-session1` | 97 | 70 | 63 | the same 6 + 1 |

(`done` agrees exactly at both viewers — 65 and 59.) `flow_series` reads the raw
event list and counts **both** copies of a dual-channel id; `fold_tasks` keys by
id and keeps one. The seventh is `T-0001`: the store holds
`created 02:16:37Z` then `retracted 02:28:03.908Z`, while the payload's `T-0001`
row is the **plan seed of the same id** — a different title
(`Freeze the PM contract…` vs `Fix Kanban filtering…`), `source: plan.json`,
`provenance: seed only`, and `events: []`. So one id carries a retracted store
event and a live plan seed, and the board shows the seed while `flow` counts the
event. Neither number is wrong; they answer different questions about the same
log, and nothing tells a reader which one they are looking at.

**One id space for N projects means the second project's board is a partial view
of the first's, and nothing says so.**

**The leader's own blocker is that measurement, and it is filed eight times
[V].** Eight `created` rows carry the exact title *"Leader: approve the plan;
advance hello past SEALED_DIVERGENT"* — `T-0233`, `T-0234`, `T-0240` in `hello`
(all 08:28:0x–08:28:23Z, three created inside 14 seconds) and `T-0156`,
`T-0157`, `T-0158`, `T-0159`, `T-0161` in `barrier-v0`, whose `hello` copies are
the entries in the table above. Measured on the rendered board, not the store:
the three `hello` cards fold to `owner=human, status=review, visibility=draft` —
**the leader owns the cards asking the leader to act.**

**And a ninth copy arrives by the other id source, so the count depends on
which surface you ask [V].** The board's 177 rendered tasks include **four**
rows whose title asks the leader to act: the three `hello` cards above, plus
`T-0004` — same title, `owner=human`, and `status=dropped`, `visibility=published`,
`source: plan.json`, `provenance: seed only (not yet in the store)`,
`events: []`. It is a *plan seed*, not a store event. So a reader counting the
store finds eight and a reader counting the board finds nine — and the ninth is
the **only one of the four rendered copies that looks already handled**, because
`dropped` is terminal. Both id sources of the next paragraph meet in this one
card.

**And the same ask is also buried under an id `hello` has since closed as
unrelated work [V].** `T-0156` in the rendered board is
`status=done, owner=claude-session1, title="Add Help/Concepts page…"` — a
finished card. Its `barrier-v0` twin, *"Leader: approve the plan…"*, is the one
the fold discards. So `barrier-v0`'s ledger holds the leader's blocker with a
`created` row and nothing after it, its `T-0157`/`T-0158`/`T-0159`/`T-0161` sit
in `ready`, and **the browser will never show any of them**, because the board
folds by id and `hello` won the id. The one project's view of the other
project's blocker is: not present.

*(Re-verified 2026-09-23 against the live tree and `127.0.0.1:8777/api/state?as=human`
at HEAD `9d64d36`; an earlier draft of this paragraph said "four times" and
counted the id ranges rather than the `created` rows.)*

**And there is a second, root-wide source of ids the allocator does not merge
with the first.** `_plan_id_floor` (`bin/aim:1788`) reads every `plan/*.json`
under the root and floors the per-channel counter above it. That was added
because plan seeds once collided with store events, and it works — but it means
a root's id space is *two* sources constrained by *one* floor, and the seed
files could collide with each other. `plan/plan.json` alone carries 155 seeds,
which is why this root's `hello` allocator is at `T-0245` rather than `T-0091`.
Measured separately on a throwaway root: `plan/a.json` and `plan/b.json` each
seeding `T-0001`, then a real `aim task new` → `T-0002` (the floor works), and
the board folds `{'T-0001': 'seed from plan A', 'T-0002': 'real work'}` —
`plan B`'s description is gone with nothing said.

`channel_kind` / `channel_lifecycle` (`aimboard/fabric.py:49,58`) compute
scratch-vs-project and empty/dormant/active. **Nothing reads either.** `hello`
derives `project` and `dev` derives `project`; the heuristic miscalibrates
exactly where T-0216 says it does.

## 2.2 N agents: the collision control is prose

`codex` announced a write-set protocol on the channel (`CLAIM: <path>` /
`RELEASED: <path>` comments). It is a good rule and **nothing enforces it**:
`grep CLAIM bin/aim` → 0 hits. Two hands editing one file leave no trace in `aim`.

What *is* enforced, per primitive: append (flock + chained write), registry
(`update_json`), card ownership (`task claim`), the selftest lockfile. Those are
all the same-resource protections; **the shared resource is the file and nothing
owns it.**

`aim register --force` takes over a registered id with **no liveness check** — it
reads `registry.json` and nothing else (`bin/aim:979`). A returning session and a
second harness are indistinguishable. The refined fix already exists one layer
down (T-0242 derived `session_of()` from the pid for ledger rows) and is not
applied to registration.

---

# Part III — The methodology: how to check a claim

This is the part that lets the leader *verify the judgement*. Six rules, each
of which this repo has been burned by at least once.

**1. Ask which of the three marks a claim carries, and demand the command.**
"Enforced" means a refusal you can paste. "Recorded" means a ledger row you can
paste. Everything else is prose, and this repo has repeatedly read prose as
enforcement.

**2. A marker that passes on any failure measures nothing.**
`test.fail()` and `@unittest.expectedFailure` are satisfied by *any* failure, so
they do not record *which* failure they absorbed. Measured: of 19 markers, most
had drifted — stale (the defect was fixed), unfalsifiable (the apparatus cannot
pass whatever the product does), or honest. **Two of the drifted ones were
hiding a live product defect.**

**3. A suite that nothing repeats is not a green.**
Measured 2026-09-23: every scripted runner green (`selftest.sh` 199/0,
`conformance.py` 41/41, 30 python suites) **while `npx playwright test` was red
2 runs in 3** and `tests/test_a2a_reference_client.py` was red outright. The
README's five-command list is not the test suite. Enumerate `tests/` yourself.

**4. Name the revision.** Read `/api/revision` before filing anything. If
`stale` is true the page was not built from the source you are reading; if it is
`null` the bundle recorded nothing and that is not "up to date".

**5. Split a merged denominator before quoting a rate.** "142 cards in
review/done, 46 commented" was the merge of 70 *recorded* cards and 72 *plan
promises*. Split, the claim was sharper: 24 of the 70 *recorded* ones carry no
comment. The promise half is not evidence either way. **The merge is the thing
this repo keeps finding unlabelled** — the same shape as the two-project id
space, and as `remaining` in the burndown.

**6. The three `attack_*.py` scripts exit 0 on defects.** They print a table and
return success. They are reports. If anything scripts their exit code it will
read a DEFECT as a pass.

---

# Part IV — Where the machine and the documents disagree

Ranked by what they cost. None of these is a proposal; each is a measurement with
a `file:line`.

| # | what was believed | what was measured | evidence |
|---|---|---|---|
| 1 | a task is a project-scoped object | **the board merges every channel into one id-keyed dict; a second project overwrites the first** | `fabric.py:281` **[V]** |
| 2 | the leader is exempt from the review rules | **any name that typed `--kind human` is exempt** | `bin/aim:2126` **[V]** |
| 3 | entering SYNTHESIS means everyone sealed | **the check is file *existence*; a hand-written `{}` passes, `verify` only complains after** | `bin/aim:1476` **[V]** |
| 4 | a seal is a falsifiable commitment | **`--claims` is stored unvalidated; `"not-a-list"` seals fine** | `bin/aim:1375` **[V]** |
| 5 | the barrier is enforced by the tool | **enforced at record time only; `cat private/*.jsonl` is exit 0 with no ledger row** — README §3 concedes this | measured **[V]** |
| 6 | a card reaches `done` by a recorded move | **`task new --status done` is legal; the burndown reads 25 where its header reads 21, and those two differences are not the same four rows** — measured in §1.4 | `bin/aim:1940` **[V]** |
| 7 | `CROSS_EXAMINE → SYNTHESIS` is the only rule-changing edge | **`RESOLVE → CROSS_EXAMINE` re-opens both**; `design/17:239` says otherwise | `bin/aim:51` **[V]** |
| 8 | `--force` skips transition legality and nothing else | **it also bypasses the seal quorum and the synthesizer check**; `design/17:222` says otherwise | `bin/aim:1463` **[V]** |
| 9 | `RESOLVE` is where the leader decides | **`channel_say=False` there refuses the leader's own ruling** | **[V]** |
| 10 | the write-set protocol prevents collisions | **nothing reads `CLAIM:`/`RELEASED:`; two hands on one file leave no trace** | `grep` = 0 hits **[V]** |
| 11 | a `human` is the leader, and only the leader | **every gate in the tool exempts any name that typed `--kind human`, and the mail gate never compares the viewer against a channel's `leader` field at all** — see below, it is the largest single hole | `aimboard/gate.py:159,191` **[V]**, §4.1 |
| 12 | a foreign A2A client sees what the board sees | **`/rpc?as=<registered stranger>` returns 70 drafts the board withholds from the same caller** | `aimboard/a2a.py:797` **[V]** |
| 13 | the seal hides a participant's reasoning from everyone but the synthesizer | **any self-declared `human` can read the mixed bundle — including one who never sealed and is not a participant** | `bin/aim:1610` **[V]** |
| 14 | a plan seed is deduplicated | **two `plan/*.json` naming one id silently lose the second**, first-wins by glob order | `aimboard/fabric.py:131,135` **[V]** |
| 15 | a session's advance request is checked before it is recorded | **`request-advance` validates nothing: `--to NOT_A_PHASE` → rc 0, and the ledger gets no refusal row** | `bin/aim:1590-1604` **[V]**, §1.3.2 |
| 16 | the dashboard writes as the identity it was started as | **without `--as` it writes as `channels[0].leader`, i.e. the alphabetically-first channel's leader** | `aimboard/cli.py:505` **[V]**, §4.5 |
| 17 | `ledger.jsonl` is a refusal ledger whose `class` is `barrier\|form\|unrecorded` | **the file holds 352 rows; 276 are refusals. 36 are the acts README §3 asks a `barrier` row to make findable, and 31 `push` rows carry a class that is not in the vocabulary** — see §4.6 | measured **[V]**, §4.6 |

## 4.1 Row 11 is the master key, and it is measured end to end

The exemption is one line and it is not a leak in one place — it is the same
test spelled at every gate. Measured on one throwaway root, with `outsider`
registered `--kind human` (not the leader, not a participant, never sealed) and
`alpha` a claude participant:

| what the outsider did | result |
|---|---|
| submit `alpha`'s card to `review`, then approve it to `done` | both rc 0, **zero refusal rows** |
| read the whole mixed bundle in `SYNTHESIS` via `synthesis-input` | **succeeded**, including alpha's private log |
| the same command as `beta`, a claude peer | `REFUSED: only the synthesizer ('synth') may read mixed inputs` |

The refusal for `beta` is the barrier working. The tool has no equivalent for
`outsider`, because `bin/aim:1610` reads, in one condition:

    if who != m.get("synthesizer") and kind != "human":

— the same `kind != "human"` shape as `bin/aim:2126`, and as the read gate at
`aimboard/gate.py:24` and the mail gate at `aimboard/gate.py:159`.

**And the mail gate is the widest one, because mail is not addressed to a
channel.** `gate.conversation_view` does not ask whether the viewer leads
anything, and it never reads a channel's `leader` field at all — `grep -n leader
aimboard/gate.py` returns four lines and the only *comparison* is `:159`:

    kind = (state["registry"].get(viewer) or {}).get("kind", "")
    is_leader = kind == "human"
    …
    if not is_leader and viewer not in (sender, to):   # :191
        withheld += 1

So the exempt set is not the closed set of leaders of live channels. The live
registry holds five registered agents and exactly one typed `human`; the seat
named `human` is factually the leader of all five channels
(`barrier-v0`, `dev`, `hello`, `s2-scratch`, `s2-scratch2`), which is why the
hole has cost nothing so far. **Nothing in the code makes that coincidence
true**, and this is the paragraph that says so out loud rather than one that
asserts it holds.

Measured live, one `/api/state` per seat, same second, against a store of
**247** conversation records:

| seat | kind | `conversation.is_leader` | mail read | mail withheld | payload `withheld` |
|---|---|---|---|---|---|
| `human` | `human` | **true** | **247** | 0 | 0 |
| `codex` | `codex` | false | 205 | 42 | 45 |
| `claude-session1` | `claude` | false | 185 | 62 | 65 |
| `codex-orangement` | `codex` | false | 67 | 180 | 184 |
| `synthesizer-v0` | `claude` | false | 0 | 247 | 250 |

The sentence this table replaces read *"`human` reads **237** mail rows where
`codex` reads 200 and `claude-session1` reads 175"*. Those three numbers are
stale and they are also **the wrong quantity**. 237 is `mail + withheld` — the
whole store as it stood then — so the old sentence compared a full view against
partial ones and called the difference a leak size. Worse, it named `codex`,
whose two seats read **205** and **67** from the same store in the same second:
the identity is not enough to predict what a seat reads, which was the fact
worth stating and the one the old sentence hid.

(`withheld` and *mail withheld* differ by 0–4 because `withheld` is one counter
serving both loads at `gate.py:179` and `:192`; the residue is the count of
gated *channels*, which carry no records of their own. Reported as measured.)

**One payload calls the same agent the leader and a non-participant, one key
apart.** On a throwaway root — channel `dmtest`, participants `alpha, beta`,
leader `lead`; `alpha` and `beta` exchange two DMs — the `delta` seat, registered
`--kind human`, holds `lead`'s office by typing only:

    conversation.is_leader  = True          (gate.py:159, from delta's kind)
    channels[0].leader      = 'lead'        (fabric, from the manifest)
    delta in channels[0].participants  =  False

    from/to: alpha ⇄ beta, neither is delta. delta reads both bodies.
    gamma (a claude non-participant, same root, same second):              mail=0  withheld=2

`walled_off` already answers this correctly — `gate.walled_off(delta)` is
**False** where `gate.walled_off(gamma)` is **True** (`gate.py:24` is itself the
`kind == "human"` branch). The gate knows delta is not walled; the loader never
asks.

**And `kind` is written by the agent it describes.** `aim register --as
<name> --kind human` asks nobody's permission. So every sentence in this system
of the form *"the leader is exempt"* is, in code, *"any name that typed human is
exempt"* — and the tool's own docstrings say the first while the conditions say
the second.

## 4.2 Row 12 is the same rule, one surface out

Measured against the live board with `synthesizer-v0`, a registered agent who
participates in **no** channel:

    /api/state?as=synthesizer-v0   ->  107 tasks, withheld_tasks = 70
    /rpc?as=synthesizer-v0 ListTasks -> 178 returned, 177 distinct,
                                        70 not on the board at all

Every one of the 70 is a draft. The board counts them and withholds them; `/rpc`
serves them by id, title and body, on the same port, to the same caller, in the
same second. `aimboard/a2a.py:797` spells the stranger test as
`if viewer not in channel.get("participants", []): return True` — *a stranger is
not a participant, so show them everything* — where `gate.walled_off` spells the
same membership test as the reason to **shut them out**
(`aimboard/gate.py:23`). Two functions, one condition, opposite verdicts.

## 4.3 Row 13 and the finding behind it

`plan/*.json` is the leader's plan, and `load_plan` merges several files into
one dict with `setdefault` (`aimboard/fabric.py:131,135`). `_plan_id_floor`
(`bin/aim:1788`) reads *every* plan file so a fresh id clears all of them — good
— but the merge itself is first-wins in glob order, so two plan files naming
`T-0001` produce one task and no message. Measured: `plan/a.json` and `plan/b.json`
each seeding `T-0001`, then a real `aim task new` → `T-0002` (the floor works),
and the board folds `{'T-0001': 'seed from plan A', 'T-0002': 'real work'}` —
`plan B`'s description is gone with nothing said.

## 4.4 One rule, one owner — the rule this repo states about itself

`design/08-solution-shape.md:22-28` says it twice: *"One rule, one owner. The
write discipline lives in `bin/aim` and nowhere else. The gate lives in
`aimboard/gate.py` and nowhere else… Every adapter in `protocols/` either calls
`bin/aim` or returns `UnsupportedOperation`, and there is no third option."*

Measured today: **the task-visibility rule lives in three places** —
`bin/aim:_visible_to` (`:1759`), `aimboard/gate.py:visible_tasks` (`:52`), and
`aimboard/a2a.py:task_visible` (`:761`). `a2a.py` says so itself in a comment at
`:609`: *"the access rule it has to satisfy now exists in three places… That is
one more than the project's own rule allows."* The three do not agree: `a2a.py`
and `bin/aim` take the union (owner **or** creator), `gate.py` takes owner only.

This is the document stating its own rule and then the code having three owners
of the rule it names. It is the cleanest instance of the pattern in Part IV,
because the rule being broken is *the rule about rules*.

## 4.5 Row 16: a missing flag silently becomes an identity [V]

`AGENTS.md:9` gives the board command verbatim, and it includes the flag:

    aimboard serve --port 8777 --refresh 0 --allow-write --as human

Drop the `--as` — natural, when you *are* the human and it looks redundant — and
`_writer()` (`aimboard/cli.py:495-505`) falls back:

    return args.viewer or (load_fabric(root, [], <today>)["channels"][0]["leader"])

`["channels"][0]` is `sorted(...)[0]` (`aimboard/fabric.py:117`), so it is the
**first channel by name**, and its `leader` is whatever that manifest says.
Measured on a throwaway root with two channels and a board started with
`--allow-write` and **no** `--as`:

    write = {"enabled": true, "as": "otherhuman"}
    channels, in fold order:
        a-scratch -> leader otherhuman
        z-prod    -> leader human

The board announced it would write as `otherhuman` — which is `--kind human`,
self-declared, i.e. row 11. **The write identity is chosen by the alphabet, and
the alphabet's channel is trusted because its leader typed `human`.**

The property the docstring claims still holds — *"a caller who wants a different
one starts a different server"*, and measured: `cli.py:711-721` drops any client
`--as` and appends the server's own, so no request can set it. What does not hold
is the implied *"the server was started **as** someone"*: started with no `--as`
it was started as nobody, and the fallback picks a leader out of a sorted dict.
**A missing flag becomes an identity instead of an error** — the same shape as
`bin/aim:35`, where `AIM_ROOT` unset means the *live* checkout rather than a
refusal. The live board on 8777 was started with `--as claude-session1`, so it
never reaches this path; this was measured on a root built to reach it.

Cheap remedies, both codex's lane: `--allow-write` requires `--as` (a write
posture with no identity has no meaning), or the fallback is the empty string and
the dashboard offers no write control until an identity is named.

## 4.6 Row 17: the ledger is counted by `class`, and `class` is not a refusal field [V]

README §3 states the vocabulary in the present tense, twice:

> `class` is `barrier`\|`form`\|`unrecorded` (`_record_refusal` in `bin/aim`)

> a refusal ledger — intent, not just outcome | `channels/<ch>/ledger.jsonl`

`aimboard/api.py:231` repeats it as the machine's answer — `refusal_classes()`
returns exactly those three and is published as `refusal_classes` at `:490`,
which `web/src/panes/HelpPane.vue:344` renders as **the** token table.

Measured over every `channels/*/ledger.jsonl` in the live tree:

| | rows | |
|---|---|---|
| all ledger rows | **352** | |
| `event == "refusal"` | **276** | `barrier` 148 · `form` 126 · `unrecorded` 2 |
| not a refusal, **carrying a refusal class** | **36** | `task_published_during_divergence` 35 + `channel_member_added` 1 |
| carrying `class: "record"` — **not in the vocabulary** | **31** | every `event: "push"` |
| carrying no `class` at all | 9 | 6 `seal`, 3 `phase`, written before the field existed |

So `class` is not what makes a row a refusal, and a reader who counts either one
for the other is off by a figure that looks like a measurement. Over the whole
tree: `grep -c '"class": "barrier"'` returns **184**, and the refusals *of that
class* number **148** — 36 rows apart. Count every class-bearing row as a refusal
and the total is 343 against the true 276 — 67 rows apart. Both numbers are the
kind that gets quoted without a second look.

**The 36 rows are not noise. They are the mechanism README §3 asks for.** The
comment above the writer (`bin/aim:2373-2381`) says so outright:

> Publishing during a divergence phase is the one deliberate act that exposes a
> work item to a peer while the barrier is supposed to be closed … a leak is not
> a refusal, and it is not a `task.published` line, it is its own event class.

So the tool invented a row that is *shaped like a refusal* so the ledger could
answer "did anyone lean on the barrier", and gave it the barrier class on
purpose. The cost is that the class no longer means one thing: `class: barrier`
today covers *a request the phase refused* (148) and *an act the phase permitted
that you then performed while shut* (35) — opposite verdicts under one token.

**And the pane that exists to show them can never show them.** `BarrierPane.vue`
draws its table from `channel.refusals`, which the board fills at
`aimboard/api.py:372` out of `ch["refusals"]`, which is `fabric.py:265` —
`[r for r in ledger if r.get("event") == "refusal"]`. The 35 divergent
publications are in the ledger, carry `class: barrier`, and are filtered out
one layer below the pane. Measured on `hello`, the channel where all of this
lives:

| rows in `channels/hello/ledger.jsonl` | 342 | |
|---|---|---|
| `class: barrier` | **183** | caught by `grep` |
| `event: refusal` | **271** | what the pane receives |
| both — the refusals a reader calls `barrier` | **147** | neither of the above |

The pane's own filter (`:300-308`, a `v-if` over `row.class !==
filters.refusalClass`) is correct and keys on a token that, for the rows it can
see, is. The 36 rows it cannot see are the ones the surrounding README section
says the pane is for.

The remedy is not a rename for its own sake. A `class` a reader counts by has to
be the class of exactly one kind of event, which is what §4.4's rule — one rule,
one owner — asks of every other object here. Either the divergent publication
gets its own class token, or `refusal_classes()` grows a fourth entry and the
pane's loader stops being `event == "refusal"`. Until one of those lands, the
sharper statement of README's sentence is: **`ledger.jsonl` is an event ledger;
`class` is a field 343 of its 352 rows carry, and the word for a row whose class
is `barrier` is not "refusal".**

---

# Part IV-b — The objects, and what owns each

An object counts as first-class here only if it has a store, a writer, and a
**gated** reader. A field is not an object.

| object | store | writer | gated reader | verdict |
|---|---|---|---|---|
| **agent** | `registry.json` | `register` `bin/aim:959` | `card` `:3913` | first-class |
| **session** | a free-text field | `register --session` | **none** | not an object |
| **channel** | `manifest.json` | `new-channel` `:1030` | `status` `:3875` | first-class |
| **project** | — | — | — | missing; channel is nearest (`design/17` §2) |
| **task** | `channels/<ch>/tasks.jsonl` | `task new` `:1934` | **three owners**, §4.4 | first-class, contested |
| **message** | `log.jsonl`, `private/`, `outbox/` | `say` `:1121`, `push` `:3288` | `inbox` `:1398`, `conversation_view` `gate.py:145` | first-class, three stores under one word |
| **receipt** | the push record's own fields | `confirm` `:3497` | `outbox` | first-class, narrow |
| **seal** | `seals/<a>.json` | `seal` `:1354` | `verify` `:4202`, `status` | first-class |
| **barrier phase** | `manifest.barrier` | `advance` `:1450` | `PHASE_RULES` `bin/aim:56` | first-class |
| **refusal** | `ledger.jsonl` | every `die` `:309` | `verify`, audit view | first-class |
| **room** | `rooms/<id>.jsonl` | `room new` `:2822` | `visible_rooms` `gate.py:133` | first-class in the CLI, **absent from the JSON payload** |
| **friction** | `friction.jsonl` | `friction --add` `:4011` | `verify` only | first-class, narrow |
| **milestone** | `plan/plan.json` | **none** | `fold.report_data` | **read-only seed** |
| **channel kind/state** | derived | **none** | **none** | **computed, read by nothing** |
| **project** | — | — | — | **missing**, and §2.1 is what missing costs |

Measured live, one line of evidence for the "read by nothing" rows: all five
channels return `kind` and `state` nowhere in the payload, and
`grep -rn "CLAIM:\|RELEASED:"` over `bin/aim aimboard/ web/src/` is empty.

**Seventeen rows, one shape: a rule that reads as enforced and is only written
down.** That is the same failure the barrier was built to catch, one level up —
and it is the reason the SOP has to carry the three marks rather than a list of
steps. Rows 11–14 were added after the first draft, 15–16 after the second, 17
after the third; rows 1–10 are unchanged since the first, and every one of the
seventeen now carries a command in its evidence cell.

**One corollary, measured:** the two ends of the identity chain are not recorded
the same. A refused `advance` writes a ledger row naming the actor **and the
session** (`bin/aim:299`); the successful `advance` that follows writes a `phase`
row with the actor and no session. So the caller who was stopped is identified in
the record and the caller who got through is not — which is backwards for the
one question the ledger exists to answer.

---

# Part IV-c — The state machines, and the relations between them

Part IV is a list of defects. This is the *set* view, because the leader asked
for it directly — *状态机，范畴的关系* — and because the defects are better
explained by the shape of the set than one at a time. There are **eight** machines
in this fabric. Two are enforced, two are partial, and four are prose or absent.

| # | machine | store | edges | who may move it | where enforced | mark |
|---|---|---|---|---|---|---|
| 1 | **phase** | `manifest.barrier.phase` | `TRANSITIONS` `bin/aim:46` — **7 edges over 6 phases**, `CLOSED` terminal | leader only (`require_leader:830`) | `advance:1450` checks the edge; at a **phase boundary** `_check_rules`/`_check_keys` also fire | **ENFORCED** |
| 2 | **task status** | `channels/<ch>/tasks.jsonl` | `TASK_FLOW` `:116` — **16 edges over 7 statuses**, `done`/`dropped` terminal | owner, or the `kind=="human"` exemption | `task move:2114` | **ENFORCED at move, absent at birth** |
| 3 | **seal** | `seals/<a>.json` | one-way: unsealed → sealed | any participant | quorum is **file existence** (`:1476`) | **RECORDED, not enforced** |
| 4 | **membership** | `manifest.participants` | add / remove, both leader-only; both write a ledger row | leader only | `channel add/remove` (`:688`,`:735`) — real barriers, measured | **ENFORCED** |
| 5 | **task visibility** | derived | published ⇄ draft, by hand | owner / leader | three implementations that **disagree** (§4.4) | **ENFORCED, three ways** |
| 6 | **channel kind/lifecycle** | derived | empty → active → dormant | nobody | computed at `aimboard/fabric.py:58`, **dropped by the payload projection** | **PROSE — computed and discarded** |
| 7 | **obligation** (who owes the leader an action) | none | — | — | 6 `@expectedFailure` tests (`tests/test_decisions_have_actions.py:249-313`) | **ABSENT by design, on the record** |
| 8 | **session** | a free-text field | register ⇄ register `--force`, no liveness check | any name | `bin/aim:979` reads `registry.json` and nothing else | **ABSENT** |

Measured for #4, on a throwaway root — this is the machine that is *better* than
its documentation:

    channel add --as lead --channel ch --agent ghost   -> REFUSED: not a registered agent
    channel add --as otherh --channel ch --agent beta  -> REFUSED: may not add a member
    channel add --as lead --channel ch --agent alpha   -> channel_member_noop row, rc 0
    channel remove --as lead --channel ch --agent lead -> REFUSED: 'lead' leads 'ch'.
        Removing the leader would leave the channel with nobody who may move its
        phase or its membership, which is not a state this file can express.

Every branch is a refusal or a ledger row, and the rows carry `member` and the
resulting `members` list (`channel_member_added/removed/noop`). The one thing the
machine does not bound: **a channel may have zero participants.** Measured: two
`channel remove`s leave `participants: []` with `leader: lead`, the channel still
listed, still advanceable by the leader, and the removed participant refused
(`'alpha' is not a participant in ch`). A leader who is not a participant can
create one too — `new-channel --participants alpha,beta --leader lead` is
accepted, so the manifest can hold a leader who is not on the roster.

## IV-c.1 The relations between the machines

The machines are not independent; four of them read each other, and two of those
reads are the load-bearing ones in the whole system:

    phase  ──read by──▶  task visibility   (DIVERGENCE_PHASES gates drafts)
           ──read by──▶  say routing      (channel_say / private_say)
           ──read by──▶  room publication (room_published)
           ──read by──▶  seal acceptance  (a seal during COMMIT is a commitment)
    membership ──read by──▶ task visibility (a participant may see their drafts)
               ──read by──▶ mail gate       (a stranger is walled off)
    task status ──read by──▶ obligation     (a `done` card owes nobody an action)

**The phase machine is the only one every other machine consults**, which is why
Part IV's row 1 (`fabric.py:281`) and row 7 (`bin/aim:51`, the rule-changing
edge) both cost more than they look: they are defects in the one table four
others read. Measured: `PHASE_RULES[phase]` is read at **seventeen** sites in
`bin/aim` (counted by occurrence outside comments; `:142`, `:152`, `:859`,
`:1267`, `:1402`, `:1527-1531`, `:1548`, `:1553`, `:1566`, `:1575`, `:3883`,
`:3890`, `:4134`), and the `channel_say` half of it is deliberately
single-sourced — `bin/aim:1215-1233` records a case where a second copy of that
one bit had drifted and a `say` in `COMMIT` printed `note recorded` and exited 0
while `log.jsonl` was never created.

**And each machine is written down more than once.** Counted by parsing, not by
grep:

| vocabulary | copies | identical today? |
|---|---|---|
| the divergence set | `bin/aim:130`, `const.py:5`, `a2a.py:758` | **yes** (3/3) |
| inside `bin/aim` itself | `PHASE_RULES`' `read_others=False` rows encode the same three again | **yes** |
| the phase list | `bin/aim:37`, `web/src/concepts.js:22` — hand-copied, all six keys, compared and equal | **yes** |
| the status list | `bin/aim:116`, `const.py:8`; `a2a.py:326` is a *different* vocabulary (A2A `TaskState`) bridged deliberately at `STATUS_TO_STATE` `a2a.py:673` | yes for the first two |
| the task machine | `bin/aim:117`, `web/src/panes/HelpPane.vue:291` (`FLOW_FALLBACK`) | **yes** — compared field by field, all seven rows equal |
| the phase machine | `bin/aim:46`, `web/src/concepts.js:349` (`TRANSITIONS`) | **yes** — all 7 edges equal, but the Vue copy adds prose `unlocks`/`why` per edge |
| terminal set | `TASK_FLOW`'s two empty edges, `const.TERMINAL` (`{done, dropped}`) | **yes** — and the `done/doing/review` colour map in `const.STATUS_COLOR` carries no terminality, so it is not a third copy |

**They all agree, and that is the finding, not the exoneration.** The table above
is six facts, each written down **two to four times**, in two languages, and this
repo already has the receipt for what happens when one of them lands in only
some of the copies. `TASK_EVENTS` (`bin/aim:127`, the eight event names a card may
carry) is declared and **read by nothing** — `grep TASK_EVENTS` finds the
declaration and no reader — so the store's `tasks.jsonl` carries exactly those
eight and never a stray one (`created 97, moved 249, commented 91, published 35,
assigned 15, dropped 2, linked 1, retracted 1`), while `ledger.jsonl` next to it
carries `seal`, `phase`, `push`, `refusal`,
`task_published_during_divergence`, `channel_member_added/removed/noop` and
`friction` under the same word *event*. The event vocabulary is a ninth machine
with no enforcer at all, and nothing has gone wrong with it **because the
copies that are read are the ones that write**.

**Two of the eight cannot be seen from the page.** #6 is computed on every
`load_fabric` and dropped by `aimboard/api.py:363`'s projection, which keeps
`id, topic, phase, round, leader, synthesizer, participants, history, sealed,
chain, tasks_recorded, tasks_store_exists, tasks_unknown_events, refusals,
concessions, friction` and **not** `kind`, `state`, `traffic`, `last_activity` or
`idle_days`. Verified against the live payload: all five channels have none of
those keys. So the answer to *"is this channel a real project or scratch, and is
it alive"* exists in the fold, is computed on every page load, and reaches no
reader — not the JSON, not the CLI (`aim status --channel dev` prints the phase,
the leader, the rules and the participants, and no lifecycle), and not the page.

## IV-c.2 The relations between the categories

*范畴的关系* — the objects and their cardinalities, measured:

    agent  1 ──n  session     (a name may be re-registered with --force; no liveness check)
    agent  n ──n  channel     (participation; a channel may hold zero participants)
    channel 1 ──1  project    (there is no project object; §2.1 is what that costs)
    channel 1 ──n  task       (ids are per-channel; the *board* keys them per-root — the collision)
    task   1 ──1  owner       (nullable: an unowned card short-circuits two actor rules)
    task   1 ──n  event       (tasks.jsonl is an event log, folded on read)
    agent  1 ──1  seal        (a seal is per **participant per channel**, not per task:
                               channels/hello/seals/{claude-session1,codex,codex-orangement}.json)
    message n ──n  channel    (public log, private log, outbox — three stores under one word)
    refusal n ──1  action     (every die() writes one; the class is `barrier|form|unrecorded`)

**Two of these are lossy in the direction a reader would not guess.** `channel
n─n task` loses work silently (§2.1: an id space per channel, merged per root, so
the second project's copy is gone and the survivor is chosen by `sorted()`). And
`task 1─n event` is lossy *on the read side only*: the store keeps all eight
kinds, and the one consumer that draws them keeps two (`created`, `moved→done`),
so the five newest records in the live store appear on no card — reported
separately as the tail violation.

**The rest are honest one-to-manys with the consequence stated somewhere.** A
nullable owner is what makes two actor rules short-circuit; a per-channel seal is
why the quorum is per participant and not per card; `n─1 action` is why the
refusal class, and not the action, is the thing a reader can count on.

---

# Part V — The judgement

**The core is sound and the ceremony around it is not.** Three things are real:
the phase gate refuses and records refusals (137 `barrier` + 126 `form` refusals
in the live tree, each with a reason); the seal chain detects tampering after the
fact; and the task-actor rules genuinely stop a bystander from submitting
another's card. Those are the load-bearing mechanisms and they work.

**What is not real is the layer that makes them mean something.** A quorum that a
hand-written file satisfies, a claims schema nothing validates, an exemption any
name can claim, a terminal status a card can be born into, an id space that
merges two projects into one, and an end state nothing asks for — none of these
is a missing feature. Each is a rule that exists in prose and in the readings and
not in the machine.

**Row 11 is the master key.** The others are separate failures of separate
mechanisms; that one is a single condition — `kind == "human"`, declared by the
agent it describes — spelled at every gate in the tool and in the board. Fixing
it first is not a preference: it is what makes the other sixteen measurable,
because until it lands, any measurement of "who could reach this" has an actor
who can reach everything and left no refusal row while doing it.

**The single highest-value fix after that is not a feature: it is to make the
three marks the contract.** Every step in Parts I and II already carries one.
Where a step reads **PROSE** and the leader believes it is **ENFORCED**, that is
the defect — and there are seventeen of them above, each with a line number and a
command you can re-run.

**What has to be decided before an end-of-life SOP can be written:** who, or what
recorded evidence, declares a channel finished rather than merely quiet. `CLOSED`
is reachable and nothing asks for it; `README.md` §8 Q4 states the same question
and leaves it open. Until that is answered, the honest SOP ends with *"the
leader decides, and nothing will ask them."*
