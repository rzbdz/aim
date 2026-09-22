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
explanation at `:60`. The attention pane has two pending `request` rows in
`channels/hello/log.jsonl` — one is stale, one is live — and neither can be acted
on from the page, because the server was started without `--allow-write`. That is
`AGENTS.md`'s own caution working as designed; it is also the state the leader
will find if they open the board to approve something. A board on the canonical
port with no write seat is a read-only board, and the SOP has to say so at the
point where the leader expects a button.

## 1.4 The work item

The status graph is **ENFORCED** (`bin/aim:117-125`) with one gap that matters:
`task new` validates `--status` against the *set* of statuses and not against the
*entry* states. Measured **[V]**: `aim task new --status done` → `T-0001 created
(done, draft)`, rc 0. **A card can be born terminal with no transition ever
recorded**, which is also why the burndown curve reads 25 where its own header
reads 21.

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
| 6 | a card reaches `done` by a recorded move | **`task new --status done` is legal; four such rows exist and the burndown reads 25 where its header reads 21** | `bin/aim:1940` **[V]** |
| 7 | `CROSS_EXAMINE → SYNTHESIS` is the only rule-changing edge | **`RESOLVE → CROSS_EXAMINE` re-opens both**; `design/17:239` says otherwise | `bin/aim:51` **[V]** |
| 8 | `--force` skips transition legality and nothing else | **it also bypasses the seal quorum and the synthesizer check**; `design/17:222` says otherwise | `bin/aim:1463` **[V]** |
| 9 | `RESOLVE` is where the leader decides | **`channel_say=False` there refuses the leader's own ruling** | **[V]** |
| 10 | the write-set protocol prevents collisions | **nothing reads `CLAIM:`/`RELEASED:`; two hands on one file leave no trace** | `grep` = 0 hits **[V]** |

Ten rows, one shape: **a rule that reads as enforced and is only written down.**
That is the same failure the barrier was built to catch, one level up — and it is
the reason the SOP has to carry the three marks rather than a list of steps.

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

**The single highest-value fix is not a feature: it is to make the three marks
the contract.** Every step in Parts I and II already carries one. Where a step
reads **PROSE** and the leader believes it is **ENFORCED**, that is the defect —
and there are ten of them above, each with a line number.

**What has to be decided before an end-of-life SOP can be written:** who, or what
recorded evidence, declares a channel finished rather than merely quiet. `CLOSED`
is reachable and nothing asks for it; `README.md` §8 Q4 states the same question
and leaves it open. Until that is answered, the honest SOP ends with *"the
leader decides, and nothing will ask them."*
