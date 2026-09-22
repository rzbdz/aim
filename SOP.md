# SOP — how a run starts, progresses, and ends, and how to check it

`claude-session1`, 2026-09-23. First draft on tree `cb42bba`; the body of this
document is measured at **`7def563`**, which is **18 commits** further on — and by
this document's own rule that is the number that matters, because every figure in
it that has moved, moved inside those 18 commits. Written because the leader
asked for it: *"这整一套要有流程有方法论有SOP，才能验证判断到底是否合理."*

*(The sentence above said "21 commits" and was wrong. `git rev-list --count
cb42bba..7def563` is 18; `cb42bba..HEAD` is 25. It is the smallest error in this
document and it is in the fourth line, which is where a reader decides how much
to trust the rest — so it is corrected here and left visible rather than
silently patched. Every count in this document is a measurement at a tree and a
second, and this one was a count at neither.)*

Twelve read-only subagents measured one segment each, and then four more were
pointed at the finished text and told to *falsify* it. Every claim is marked with
who measured it: **[V]** means I re-ran it myself on a throwaway root, and a row
marked *(subagent)* rested on an agent's report.

**The header that stood here said every subagent mark had been re-measured and
removed, so that no claim rested on a hand other than mine. That was false, and
a falsifier caught it in the way this document is about.** At the first draft
(`0df5650`) `grep -c subagent` returns **5** — one of which is the header
sentence counting them, leaving **four marks**: three evidence cells in the
ranked table (rows 7, 9 and 10) and one bullet in §1.5 (`room say` and
`task publish` still work in `CLOSED`). **Every one of those four was a claim I
had not run.** The sentence was then edited to say "all three of those were
re-measured" — true of three, silent about the fourth, and the fourth was the
one about the *terminal* phase of the lifecycle. All four have now been
re-measured by me, and the marks are gone; §1.5's bullet carries `[V]` like the
rest. The generalisable form: **a claim whose wording is adjusted to match the
evidence gathered is not a re-measurement**, and a count of the marks is the one
place in this system where that is checkable at a glance — which is exactly why
the count was worth getting right and was not.

## How to read the marking

Every step carries one of three marks, and the distinction is the whole point —
most of this system's measured failures were a step believed to be in the first
column and actually in the second or third. A fourth token, **`read`**, appears
in one row of §1.1 and is not a mark: it means the step is a *reader*, nothing is
enforced and nothing is written, and the three-mark table below does not cover
it. It is written this way rather than silently forced into `PROSE` because the
taxonomy having a hole for one row is itself the finding.

| mark | means | what it survives |
|---|---|---|
| **ENFORCED** | the tool refuses, exit ≠ 0, and writes a `refusal` row | a careless or hostile actor |
| **RECORDED** | the tool accepts and writes what happened | an audit after the fact |
| **PROSE** | a document says so and nothing reads the document | nothing |

**And the marks reach the document, not just the system.** Every figure below was
re-derived by a verifier, and the ones that had moved are corrected in place
rather than quietly re-printed: the header's own count (below), §1.1's step 4
citation, §1.2's edge table, §1.3's identity claim, §1.4's two counts, §1.5's
census and its `dev` reading, §4.2's four integers, and §4.4's mechanism — which
a verifier broke completely and which was the cleanest instance of the pattern it
was describing. **A number in this document is a measurement at a tree and a
second, and the ones that are not are now labelled as such.**

---

# Part I — One project, from zero

## 1.1 Start

| # | step | command | mark |
|---|---|---|---|
| 1 | have `aim` on PATH | `/usr/local/bin/aim` → `bin/aim` | **PROSE** (`AGENTS.md:13`) |
| 2 | create the root | `aim init` | **ENFORCED**, but **skippable** — `register` makes the root itself **[V]** |
| 3 | register yourself | `aim register --as <you> --kind <claude\|codex\|human>` | **ENFORCED** (refuses a live id without `--force`; `bin/aim:959`) |
| 4 | register the leader | `aim register --as human --kind human` | **ENFORCED** — `new-channel` refuses a leader who is not a registered human (`bin/aim:1041`), and the check before it (`:1035-1040`) refuses an unregistered participant. A leader need not be a participant, and the participant loop does not stand in front of the leader check for the ordinary case — see the four shapes below |
| 5 | open the channel | `aim new-channel --id <ch> --topic "…" --participants a,b --leader human` | **ENFORCED** (dup id, unregistered participant, non-human leader all refused) |
| 6 | read where it stands | `aim status --channel <ch>` | read |
| 7 | form a position | `aim say --private --kind claim` | **ENFORCED** — but not by §2.1, which this cell pointed at and which has never said anything about `say` (it is "N projects: the id space is the hole", at the first draft and now). Measured: in `SEALED_DIVERGENT`, `say --private --kind claim --body …` → rc 0, `[private/<you>] claim recorded`. The mark is right and the cross-reference was stale from the first draft |
| 8 | seal | `aim seal --summary "…" --claims claims.json` | **ENFORCED that you sealed; PROSE what a seal means** |
| 9 | be woken for the next turn | — | **MISSING.** `README.md:246` declares it unsolved; `aim wait` polls one channel's public log and nothing else |

> **Step 4, the four shapes of a bad leader.** Measured on a throwaway root,
> `aim new-channel --participants a --leader X`:
>
> | leader `X` | also a participant? | which check refuses | message |
> |---|---|---|---|
> | `codex` (registered, non-human) | no | **`:1041`** | `leader 'codex' must be a registered human` |
> | `codex` (registered, non-human) | yes | **`:1041`** | `leader 'codex' must be a registered human` |
> | `ghost` (unregistered) | no | **`:1041`** | `leader 'ghost' must be a registered human` |
> | `ghost` (unregistered) | yes | `:1040` | `participant 'ghost' is not registered` |
>
> A leader who is a registered human and *not* a participant is accepted
> (`manifest.leader == "h"`, `participants == ["a"]`), so the participant loop
> does not stand in front of the leader check for the ordinary case.
>
> *This cell said the opposite: that `:1041` was a dead branch, reachable only
> for an already-registered leader, whose refusal "comes from the participant
> check with the same message". Both halves are false — the two lines print
> different messages, and the participant check wins in exactly one of the four
> shapes. The text presented this as a measurement ("measured: register `codex`
> …") and the case it described, run, gives the leader message from `:1041`. The
> shape that shadows is an unregistered leader *inside* the participant list.
> The mark was right and the reasoning for it was invented.)*

Steps 2–5 are the only part of this system that is a clean, enforced
procedure, and step 1 (being launched at all) is the one nothing specifies.

**The claims file is a schema with no validator [V].** The documented shape is
`{id, claim, confidence, kill_if}`. Measured on a throwaway root: a claims file
holding `[{"id":"x1","claim":"…","confidence":0.5}]` — **no `kill_if`** — seals
rc 0 and is stored verbatim, so the one artifact whose entire purpose is to make
"I said this all along" impossible can be filed empty of the thing that makes it
falsifiable. That is the hole.

**And a claims payload of the wrong *type* is not rejected — it is counted by the
wrong quantity, and it takes the whole board down.** `bin/aim:1375` is
`json.loads(Path(args.claims).read_text())` with no shape check, and `:1395`
prints `len(seal["claims"])`. So a claims file holding the bare string
`"not-a-list"` seals **rc 0** and prints:

    sealed alpha: e217ea4cc8a845e4…  (10 claims)

There is no list, the string is stored verbatim as `"claims": "not-a-list"`, and
`10` is `len("not-a-list")` — the character count, reported to the sealer as a
claim count. **The seal reports a quantity it did not measure.**

**And the board cannot render any payload containing that seal — for exactly
the viewers the barrier is aimed at.** Measured on a throwaway root:
`fabric.load_fabric` succeeds, and then `api.channel_payload`
(`aimboard/api.py:354-357`, `[{"id": c.get("id", "")…} for c in
(seal.get("claims") or [])]`) raises `AttributeError: 'str' object has no
attribute 'get'`. `aim seal` exits 0 while writing it, and `aim verify` still
returns `chain OK` rc 0 and never touches `claims`.

Six viewers against that one root, `GET /api/state?as=…`:

| viewer | kind | who they are | HTTP |
|---|---|---|---|
| the leader | `human` | channel `leader` | **500** |
| a second `human` | `human` | not the leader, not a participant | **500** |
| the sealer | `claude` | participant | **500** |
| a peer participant | `codex` | participant | 200 |
| a registered stranger | `claude` | not a participant | 200 |
| `codex-orangement` | — | — | 200 |

No viewer with `kind == "human"` can be 200, and no participant can read
**their own** seal — `channel_payload`'s exempting branch is `if secrets or who
== viewer` (`:353`), one condition, and `secrets = not walled_off(...)` is
`False` for every participant while the phase is `SEALED_DIVERGENT`. So the
seal that crashes is always reached by *someone*: if the malformed seal belongs
to a human, the humans 500; if it belongs to a participant, that participant
500s. A dashboard where the leader and the sealer both 500 while the peers
render is a bricked board, and it stays bricked until someone hand-edits the
seal file. What survives is the *rendering*, not the whole board — the sentence
this replaces said "for every viewer" and was wrong in the direction of
understating the rule and overstating the blast radius at once.

*(This paragraph has now been wrong twice, in opposite directions, and the
sequence is the finding. A falsifier said the seal crashes with `AttributeError`
— it does not; that trace comes from the board two layers away. I wrote the
crash version in without running it. The falsifier then withdrew it, I re-ran
and measured rc 0, wrote "does not crash" — and *stopped there*, which missed
the board 500 that the same malformed input causes. Then I "fixed" it by naming
a blast radius I had not measured: I tested the leader and one peer, got 500
and 200, and generalised to "every viewer". Both the original and the fix came
from the same move: **stopping at the first command instead of following the
value to where it is read.** That is the thesis of this document, committed
against this document, twice, in one paragraph — and the correction was the
second time.)*

## 1.2 Progress

The phase graph is real and enforced (`bin/aim:37-53`), and the leader is the
only actor who may traverse it (**ENFORCED** — `require_leader`, `bin/aim:830`).
But **three of the seven edges change no access rule at all**, and the count is
not a reading of the prose: it is the ledger's own `rules_changed` column, on a
throwaway root with four registered agents, every edge driven and every phase row
read back **[V]**.

| edge | `rules_changed` (the ledger's column) | what it actually does |
|---|---|---|
| `SEALED_DIVERGENT → COMMIT` | `[]` | **nothing** — *"no rule changed; this advance moved a label only"* |
| `COMMIT → SYNTHESIS` | `[]` | **no access rule** — but it is the edge that opens `synthesis-input` (`bin/aim:1615`, *"only available in SYNTHESIS"*) and the `--kind synthesis` public write (`:1283`, `if kind_of != "synthesis": gate(m, who, "channel_say")` — the exemption itself is the `kind_of == "synthesis"` disjunct of the routing expression at `:1265`, and the *check* it skips is at `:1283`) |
| `SYNTHESIS → CROSS_EXAMINE` | `["read_others", "channel_say"]` | opens both |
| `CROSS_EXAMINE → SYNTHESIS` | `["read_others", "channel_say"]` | closes both |
| `CROSS_EXAMINE → RESOLVE` | `["channel_say", "private_say"]` | closes both — including the *private* log |
| `RESOLVE → CROSS_EXAMINE` | `["channel_say", "private_say"]` | re-opens both |
| `RESOLVE → CLOSED` | `[]` | **nothing** — `CLOSED` is `RESOLVE`'s rules, not a reopening |

**Four of the seven edges move an access rule, and they come in two pairs that
are the same two bits.** The version of this table that stood here said *"the
only edge that changes an access rule"* of `SYNTHESIS → CROSS_EXAMINE` — false,
and falsifiable from the same column three lines away, which the falsifier did.
The edit that fixed it then asserted *"three of the four are the same two bits"*,
which is also false: the four are **2 + 2** — `{read_others, channel_say}` on the
two `SYNTHESIS ⇄ CROSS_EXAMINE` edges, and `{channel_say, private_say}` on the
two `CROSS_EXAMINE ⇄ RESOLVE` ones. Only `channel_say` is common to all four.
It also carried the aside *"(so `CLOSED` is not far from open)"*, which describes
`CROSS_EXAMINE` and is attached to the wrong row: measured, `RESOLVE → CLOSED` is
`noop: true`, `CLOSED`'s three bits are `RESOLVE`'s (`bin/aim:61-62`), and
`CLOSED` is the *farthest* thing from open in the graph — `TRANSITIONS["CLOSED"]
== []`.

`advance` prints which of these you just took, which is honest. The table in
`README.md` §2 says who may *read* and *write* per phase and is right; what it
does not say is that **three of the seven rows move a label and nothing else**,
so the ceremony of advancing through `SEALED_DIVERGENT → COMMIT` buys a printed
sentence and a ledger row and no change in what anyone can do.

**The seal quorum can be satisfied without sealing [V].** Entering `SYNTHESIS`
requires that each participant's seal **file exists** — the check is
`.exists()` inside the `if to == "SYNTHESIS":` block (`bin/aim:1475`, check at
`:1476`). Measured: hand-write `seals/<peer>.json` as `{"agent":"gamma"}` for a
participant who has never sealed, advance, and the phase moves to `SYNTHESIS`
with **no `seal` ledger row for that agent**. `aim verify` afterwards says
`TAMPER … carries no digest` and `chain BROKEN`; nothing blocked it at the time,
and a synthesizer can be handed a bundle containing a participant who never
sealed.

The first version of this paragraph added *"and no content in their private
log"*, joining two different causes. A participant who never ran `say` has no
private log whether or not they sealed, and their reasoning is not thereby
hidden: the bundle `synthesis-input` builds carries `"private_log": read_jsonl(
private/<p>.jsonl)` for **every** participant (`bin/aim:1619-1625`), so the log
ships as `[]` — the hole is that a seal may not exist, not that a log goes
missing.

## 1.3 The human's loop

The leader's entire written interface is twelve `aim` lines inside
`README.md`'s "## 6. Using it" block — a verb catalogue, not a procedure. It
does not say what the leader reads each day, when to advance, or when to close a
card. Grepping for a stated human loop over `README.md`, `design/*.md`,
`AGENTS.md` and `skills/aim/SKILL.md` returns nothing.
*(This section said "nine lines", then "counted at every revision of that range —
12 at `4d2b89a` through HEAD, 10 further back — it was never nine". The first
half of that is right and the last clause is not: counted as `^\s*aim ` over the
section-6 block across all **17** commits that touch `README.md`, it is **12** in
16 of them and **9** in exactly one (`c8289cb`), so "nine" was once true and the
number the paragraph was arguing about is the 12 it prints. The claim it is
making — that a verb catalogue is not a procedure — does not depend on either.)*

What only the leader may do (**ENFORCED**): `advance` (**every** edge),
`channel workspace`, `channel add`, `channel remove`, `say --kind ruling`.

**The exemption is `kind == "human"`, and `kind` is self-declared [V].** The
first version of this paragraph was wrong in a way worth keeping. It said a human
who is not the leader, not a participant and not the owner "submitted another
agent's card to `review` and approved it to `done`". Measured properly on a
throwaway root, with the card explicitly owned by `a` (`aim task assign`):

    otherhuman (--kind human, non-owner, non-participant)
        T-0001: doing  -> review     rc 0   # the submission, :2128
        T-0001: review -> done       rc 0   # the approval,  :2141
    ledger refusal rows:             0

Both halves hold on an **owned** card, and the reason is the same `actor_exempt`
on both lines: `:2128` is `if args.to == "review" and owner and who != owner and
not actor_exempt`, `:2141` is `if args.to == "done" and who == owner and not
actor_exempt`. Neither fires. The *unowned* card belongs beside this rather than
in it, because there the exemption is irrelevant — with `owner == ""` the `owner`
conjunct short-circuits for every agent kind, so one actor doing
`doing → review → done` on an unowned card is **not** evidence about `human` at
all. **The two measurements are the same verdict from different mechanisms, and
the earlier sentence merged them.** The same correction runs through §1.4.

**And there is a third mechanism above both of them, which a falsifier pointed at
and which is worth stating because it is the actual first wall.** Before `cmd_task_move`
reaches either actor rule it calls `_load_task_or_die`, and `bin/aim:2079` is
`if not _visible_to(t, who, m["barrier"]["phase"]) and kind != "human"` — **the
same `kind != "human"` escape, on the read.** So a human reaches `:2128` and
`:2141` partly because the *card is visible to them at all*; a claude peer is
stopped two hundred lines earlier, with `REFUSED: 'T-0001' is a draft owned by
someone else and the channel is in SEALED_DIVERGENT` — judged on owner and phase,
never on kind. Measured: `b` (a claude) got exactly that. **The exemption is one
flag spelled at three depths on one path** — the read gate, the submission, and
the approval — which is a stronger statement of the same finding than any one of
the three measurements alone, and it is what makes `require_leader`'s being the
only *name-checking* site a real guarantee rather than a decorative one.

The code comment says *the leader* is exempt (`bin/aim:2126`); the code exempts
any name that typed `human`. `aim register` asks nobody's permission. The same
field is the board's read-side leader predicate (`aimboard/gate.py:159`,
`aimboard/views/chat.py:25`), so the two surfaces agree on a value neither
verifies.

**And the leader's one click is disabled on the board as it is running [V].**
Measured on 8777: the payload carries `write = {enabled: false, as: ''}`, so
`board.canWrite` is false (`web/src/stores/board.js:302`) and
`PhaseApprovalCard.vue:49,54` draws *approve* and *decline* both disabled with an
explanation at `:60`. The cause is narrower than *"the server was started without
`--allow-write`"* and the difference matters, because the first version of this
sentence gave that as the reason: `cli.py:813-814` sets `"as"` to
`self._writer() if args.allow_write else ""`, so **`as: ""` is exactly what it
prints when `--allow-write` is absent** — but the process on 8777 was started as
`python3 bin/aimboard.py serve --root . --port 8777 --as claude-session1`, i.e.
*with* an identity and *without* the write flag, and the useful statement is the
one §4.5 measures separately: **the write seat and the read identity are two
different flags, and the board has read-only default on one of them.** The
attention pane holds **two** pending `request` rows, not one — the log carries
three, `m0001` is filtered out because its `fromPhase` is `SEALED_DIVERGENT` and
the channel is in `COMMIT`, and `m0002` and `m0003` both survive because both
declare `COMMIT` as their `fromPhase`, which **is** the channel's current phase
(`web/src/stores/board.js:479`, `filter((request) => request.targetPhase &&
request.currentPhase === request.fromPhase)`). So the filter does not filter
either of the two that are live — and it cannot be acted on from the page
anyway. *(This said "one pending `request` row", and named `web/src/stores/
board.js:479` as the reason the other was dropped. Measured: `m0002`
`COMMIT -> CROSS_EXAMINE` and `m0003` `COMMIT -> SYNTHESIS` both pass that
filter; the one it drops is `m0001`.)* That
is `AGENTS.md`'s own caution working as designed; it is also the state the leader
will find if they open the board to approve something. A board on the canonical
port with no write seat is a read-only board, and the SOP has to say so at the
point where the leader expects a button.

### 1.3.1 One of the leader's buttons posts a command the tool refuses, and the other is answerable only after the fact [V]

The heading here used to read *"Both of the leader's buttons post a command the
tool refuses"*, and the table under it already said otherwise: the Decline cell
records that the **identical argv succeeds in `CROSS_EXAMINE`**. One button is
refused *in its phase*, the other is refused *until the phase it wants to decline
is over*. The pair is not "both refused", and a heading that says so is the same
failure mode as the classification tables in Part V — a summary that outran its
own cells.

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
`False` in `SEALED_DIVERGENT`, `COMMIT` and `SYNTHESIS` (`bin/aim:57-59`).
`note` is in `CROSS_EXAMINE_KINDS` (`bin/aim:66-74`), so it is a public speech
act and `SAY_PRIVATE_KINDS` — derived precisely so such a kind is *"refused by
name — not quietly downgraded"* — refuses it out loud. That machinery is correct
and deliberate. Measured: the **identical** argv in `CROSS_EXAMINE` succeeds
(rc 0, `m0001 human -> note`). So the decline is expressible only *after* the
thing it wants to decline has already been granted.

**And the suite never caught it, because its success path is a different action.**
`web/tests/card-t0165-row-feedback.spec.js:182-197` stubs `/api/command` behind a
`refuse` flag that **defaults to true**, so five of the file's six tests assert
that a refusal is *drawn* — and the sixth, *"a successful receipt leaves the phase
requests unannotated"* (`:268`), flips `refuse = false` and asserts success for
**`confirm receipt`**, not for the decline. So the decline's success path is
asserted nowhere: the file's only success case is a different verb on a different
row. That is still the **stale** cell of the marker table in Part III — an
acceptance that cannot fail — but the mechanism is narrower than "the mock makes
it unfalsifiable": the mock *can* succeed, and the test that uses the success
path is about the wrong action.
*(This said the stub "returns rc 1 unconditionally" and that the file "has never
once asserted that a decline succeeds". The second half is right; the first is
not, and the falsifier that read the mock is the reason the difference is now
written down.)*

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
the ledger stays empty *of a refusal*. (Careful: it is not empty in general. On
this throwaway root `ch` has no other rows at all, which is why the sentence read
as it did; on the live `hello` the same command leaves a 348-row ledger exactly
as it was. The claim that survives is narrower and it is the one that matters:
**the malformed ask adds no row to the ledger**, so a channel cannot be audited
for it. The ledger's `barrier`/`form` counts, which the whole of Part IV reads as
*"the tool refused and said why"*, do not cover this path at all.)

That is the whole chain, and every link is a machine that works as written:
`request-advance` records whatever edge it is handed; `board.phaseRequests`
renders any request row whose `fromPhase` is the channel's current phase; the
Overview pane draws an Approve button posting `request.targetPhase`; and
`advance` then refuses the edge with a form error. **The live board's only
rendered request is exactly this case** — `channels/hello/log.jsonl` `m0002`,
author `claude-session1`, `COMMIT -> CROSS_EXAMINE`.

**The closing sentence here used to be *"the only signal is a refusal the page
cannot explain", and that is false.** Measured on a throwaway root in
`CROSS_EXAMINE` with an **empty** log:

    aim say --as lead --channel ch --kind note --subject "declined: COMMIT -> CROSS_EXAMINE" --body …
      -> rc 0   "[ch] m0001 lead -> note"

The decline is expressible the moment the phase allows public speech, and
`note` is `CROSS_EXAMINE`-only for exactly that reason (`known` is empty there,
so `--responds-to` is not required). So the page *can* explain it — it simply
offers the button in the phase where it cannot be used, and offers no path to the
phase where it can. That is a worse defect than an unexplained refusal, and it is
the honest one: **the leader's Decline is not broken, it is scheduled after the
thing it declines.**

## 1.4 The work item

The status graph is **ENFORCED** (`bin/aim:117-125`) with one gap that matters:
`task new` validates `--status` against the *set* of statuses and not against the
*entry* states. Measured **[V]**: `aim task new --status done` → `T-0001 created
(done, draft)`, rc 0. **A card can be born terminal with no transition ever
recorded.**

**Two counts, and they are not the same rows.** Both are true of the live tree
and they are quoted for different things, so they are separated here. Re-derived
at HEAD, and the mechanism is now stated rather than inferred — the burndown's
predicate is `fold.py:325`:

    "remaining": sum(1 for h in dated.values()
                     if day_of(h["created"]) <= d
                     and not (h["done"] and day_of(h["done"]) <= d))

**It subtracts `done` and has no term for `dropped` at all.**

| count | what it selects | rows | reads |
|---|---|---|---|
| **2** | cards **born** terminal — a `created` row whose own `status` is `done`/`dropped` | `T-0236`, `T-0241` (both `created` by `human` at 08:28:17Z / 08:28:48Z, `owner=codex`, then one `commented` each) | the birth hole above |
| **4** | dated cards the burndown's `remaining` still counts after its own date | the two above **plus** `T-0174` and `T-0178` | `series.remaining` **28** − `board_scope.visible.undone` **24** — *the leader's* 24; see below |

The membership is exact and I re-derived it from the store: the remaining-set at
2026-09-22 is **28** rows, of which **24** are non-terminal, and the four excess
rows are precisely `{T-0174, T-0178, T-0236, T-0241}`. *(The earlier draft of
this table read 26 and 22, and the falsifier that re-derived it found 24; the
live payload now reads 28 and 24, because the store gained cards between the two
reads. The four excess rows are the part that does not move, and the arithmetic
`28 − 24 = 4` is the check that the method is sound.)* **Two things about that
pair have to be stated or the arithmetic is not re-derivable.** First,
`board_scope` is published twice and **viewer-scoped on one of them**:
`visible.undone` is **24** for `human`, **17** for `codex`, **5** for
`codex-orangement` and **2** for `claude-session1`, while `fabric.undone` is
**24** for all four and `/api/state`'s `reports_scope` field says which scope the
payload's headline number is. The 24 in this
row is the leader's, because the burndown is a whole-project figure and the
leader is the only seat that sees the whole project — and a reader comparing the
two numbers from any other seat would find a gap of 28−2=26 and conclude the
burndown was broken, which is the failure mode a number without its viewer
invites. Second, `undone` excludes `dropped` on purpose
(`aimboard/api.py:461`, `scored = total - counts.get("dropped", 0)`, with the
comment saying counting it undone "keeps a card that was deliberately closed open
forever") — and the four excess rows are **two `dropped` and two `done`**. The
gap is a union of two different rules: `remaining` subtracts `done` and has no
term for `dropped`, and `undone` subtracts both.

The stated *reason* the last two are in it was wrong, though. `T-0174` and
`T-0178` **do** record a
`dropped` event — I checked: `T-0174` has 5 events, the set exactly
`{created, moved, published, commented, dropped}`; `T-0178` has 5 events over 4
distinct names, `{created, published, commented, dropped}`, because two of them
are `commented`.
They are in the gap **because `dropped` is a status the burndown does not
subtract**, not because they lack a transition. The sentence here said the
opposite of what the data says, and said it in a table whose own next column
contradicts it.

So *"four such rows exist"* was two different facts in one sentence, and the
live tree only supplies **two** born-terminal cards — measured across every
channel's `tasks.jsonl`. The 4 is the *gap* between the burndown's tail and the
attention pane's open count: two born terminal with no `done` event to subtract,
two dropped by a verb the burndown has no branch for. **Neither count is wrong;
the sentence that merged them was, and so was the reason it gave.** The numbers
in the earlier version (25 − 21) were a correct snapshot of a revision two
behind HEAD; this pair is 26 − 22 and the gap is still 4, which is why the error
survived a reading — the *difference* was stable while both terms moved.

On an **owned** card both actor rules hold and are **ENFORCED** **[V]**: with
`T-0001` assigned to `a`, a bystander cannot submit it to `review` (`:2128`,
`class: barrier`) and the owner cannot approve their own `review → done`
(`:2141`, `REFUSED: T-0001 is owned by 'a', so 'a' cannot approve it`).

**The unowned card is a different mechanism wearing the same verdict, and the
earlier version of this paragraph merged them.** It said *"on an unowned card
both rules short-circuit on the empty owner, so one actor submitted and approved
the same card with zero refusals"*. The run is right; the conclusion drawn from
it is not. With `owner == ""` the `owner` conjunct is false for **every** agent
kind, so the exemption being demonstrated is not `kind == "human"` at all — a
claude doing `backlog → ready → doing → review → done` on a card nobody owns is
walking a status graph, not exercising an exemption. Measured: `task new` leaves
`owner: ""` (`created_by` is `None` on the event), and the actor rules are
unreachable on that card for anyone. §1.3's `human` finding is the one that
carries, and it was measured on an **owned** card precisely so that the two would
stop being confused; this paragraph now says so.

`--force` turns every one of these refusals into a recorded success. It is
**RECORDED**, not refused: the moved event carries `forced: true` and an
`overrode` list, and `aim verify` covers `tasks.jsonl`, so an auditor can see it.
Whether that is enough is the design's own question, and it is honestly marked.

**It is written to `tasks.jsonl`, not to the ledger** — the first version of this
paragraph said "an auditor reading the ledger", and a falsifier went looking and
found none: `grep '"overrode"' channels/*/ledger.jsonl` matches **nothing**, and
`grep '"forced"'` matches only `"forced": false` on `phase` rows. The live store
holds **41** rows with `forced: true` and 41 with `overrode`, all in `tasks.jsonl`.
That is not a smaller guarantee, it is a different one — the record is in the
store's own event chain rather than beside it.

**And the shape named here was one of the two it can take.** The same sentence
used to read `overrode: ["self-approval:a"]` as the generic shape; `bin/aim:2140`
appends `f"owner:{owner}"` for the **submission** half and `:2155` appends
`f"self-approval:{who}"` for the **approval** half. Every one of the live 41
carries the approval form (`self-approval:claude-session1`) because that is the
only half anyone has forced on this box. A forced submission records
`["owner:<name>"]` and nothing in the store shows it, which is exactly the kind
of shape a document should not have generalised from one observed instance.

In `CROSS_EXAMINE` — reachable by `advance --force` — a **non-participant**
moved an owned card to `done` and reassigned another agent's card to itself,
both rc 0 **[V]**. `task assign` has no membership test. Nothing is hidden; the
phase simply has no membership rule attached to the task verbs.

## 1.5 End

`CLOSED` exists and is reachable; `TRANSITIONS["CLOSED"] == []` makes a bare
`advance` say *"CLOSED is terminal"*. And then:

- reaching it takes five advances from `SEALED_DIVERGENT` —
  `COMMIT → SYNTHESIS → CROSS_EXAMINE → RESOLVE → CLOSED`. **Four of them are
  discretionary; the first one is not.** `COMMIT → SYNTHESIS` refuses without
  `--synthesizer <name>` (measured: `aim advance --as human --channel ch --to
  SYNTHESIS` → `rc 2: REFUSED: SYNTHESIS needs a synthesizer`). The other four
  are leader's call alone.

  *(The sentence here added "— a precondition no other edge has", and that is
  false. `assert_barrier_defensible` (`bin/aim:556`) runs on **every**
  advance (`:1473`) and refuses any transition **into a divergence phase** when
  the manifest declares a shared writable path: measured, with `a=src` and `b=src`
  declared, `CROSS_EXAMINE → SYNTHESIS` → `rc 2 REFUSED: channel 'ch' declares a
  shared workspace…`. So three of the seven edges carry that precondition —
  every `*→ divergence` edge — and `--synthesizer` is a precondition on *one*.
  The claim is weaker than it was written and the writing happened in the edit
  meant to fix this same bullet.)*
- **`--force` is the only way out of `CLOSED`.** `TRANSITIONS["CLOSED"] == []`
  (`bin/aim:52`), so every ordinary edge is refused: measured, `CLOSED → RESOLVE`
  rc 2, `CLOSED → SYNTHESIS` rc 2, `CLOSED → CROSS_EXAMINE` rc 2, `CLOSED →
  COMMIT` rc 2, `CLOSED → SEALED_DIVERGENT` rc 2 — all with `allowed: []` —
  while the same five with `--force` are **all rc 0** and reach the phase named.
  *(The earlier bullet said "`CLOSED` to any non-stay edge is the only way out",
  which has no parseable meaning and inverts the mechanism: the edges are all
  refused, `--force` is what moves.)*

  **The sentence that used to follow that list was false, and it was the
  interesting half.** It said "even the forced exit still routes through
  `assert_barrier_defensible`, so it cannot land back on `COMMIT` or
  `SEALED_DIVERGENT`." Measured on a throwaway root with **no shared workspace
  declared anywhere** — the ordinary case:

      CLOSED --force -> COMMIT             rc=0  "ch: CLOSED -> COMMIT (round 1, by h)"
      CLOSED --force -> SEALED_DIVERGENT   rc=0  "ch: CLOSED -> SEALED_DIVERGENT (round 1, by h)"

  and the ledger writes `forced: true` on the row. `assert_barrier_defensible`
  does run on every advance, but it refuses only when the manifest declares a
  shared writable path — so on a channel without one, which is every channel
  this repo has, the guard cannot fire and the forced exit reaches any phase
  including the two the sentence named. A closed channel can be forced back to
  `SEALED_DIVERGENT`, i.e. **before the run started**, and read as one that
  never opened.

  *(The mistake is the one this document keeps making: I confirmed the guard
  fires — in a *different* experiment, the one two bullets up where I had
  declared `a=src b=src` to make it fire — and then described its reach as
  general. Two measurements, one conclusion, and the conclusion belonged to the
  experiment I ran to produce it.)*

  **And the guard is fatal to exactly one edge, which strands a channel.**
  Declaring a shared workspace on a channel already in `COMMIT` is allowed
  (`aim channel workspace --set` → rc 0, *"This channel can no longer enter or
  remain in a divergence phase"*), and then:

      COMMIT -> SYNTHESIS      bare   rc=2  REFUSED: declares a shared workspace
      COMMIT -> SYNTHESIS      FORCE  rc=2  REFUSED: declares a shared workspace
      COMMIT -> SEALED_DIVERGENT  FORCE  rc=2  REFUSED
      COMMIT -> CROSS_EXAMINE  FORCE  rc=0   (round 1, by h)
      CROSS_EXAMINE -> RESOLVE FORCE  rc=0
      RESOLVE -> CLOSED        FORCE  rc=0

  `SEALED_DIVERGENT`, `COMMIT` and `SYNTHESIS` are the divergence phases
  (`const.DIVERGENCE`), so the guard bites on every edge *into* one — and the
  only forward edge out of `COMMIT` in `TRANSITIONS` goes into one. The five
  advances that reach `CLOSED` from the start are `COMMIT → SYNTHESIS → …`, so
  a channel that declares a shared workspace while in `COMMIT` can no longer
  close the ordinary way: the single legal edge out is refused **even with
  `--force`**, and the only exits are forced jumps that skip past it. The
  mechanism designed to stop a barrier from being claimed falsely will, in this
  one state, refuse the honest move and permit the dishonest one. The message
  offers the way out correctly (`aim channel workspace --none`, measured rc 0,
  after which `COMMIT → SYNTHESIS` is rc 0 again), so this is a foot-gun with a
  labelled release, not a trap. But nothing in the tool says "you have just
  disabled this channel's ordinary exit", and the bullet above it is titled
  *End*.

- `room say` works in `CLOSED` for a **participant**, refused for a non-participant
  (`aim room say --as out --channel ch --id r1` → `'out' is not a participant in
  ch`); `task publish` works for an owning participant. **Re-measured by me** on
  a throwaway root — the previous version of this bullet carried a *(measured by
  a subagent)* mark, and the bullet above the table is the reason that mark was
  removed from the document
- `RESOLVE` claims the leader decides, yet `channel_say=False` there refuses the
  leader's own `--kind ruling` — the decision has no in-channel route
- no `closed_at`, no decision object, no close/archive verb: `aim channel --help`
  is `{workspace, add, remove}`

**No channel under `channels/` has ever reached `CROSS_EXAMINE`, `RESOLVE` or
`CLOSED`.** The furthest any of the five got is `barrier-v0` at `SYNTHESIS`. But
the scope has to be stated, and the first version of this sentence did not state
it — it said *"no live channel"*, and a falsifier went looking past `channels/`
and found one. **`.dbg/channels/c` is tracked in this repository and is at
`CROSS_EXAMINE`, round 1**, with an unbroken chain:

    SEALED_DIVERGENT -> COMMIT -> SYNTHESIS -> CROSS_EXAMINE   (all by 'h')

Five rows, and the arithmetic is worth reading closely because the first version
of this sentence got it wrong: **two `seal` rows** (agents `a` and `b`, both
`"claims": 0`) and **three `phase` rows**. `prev`/`hash` links end to end from
`genesis`. The three transitions span `08:14:36.252Z` → `08:14:36.362Z`, i.e.
**0.110 s**; the whole root, first seal to last transition, is **0.274 s**. The
earlier text said "four phase rows … one second" — the four is the
**manifest's** `barrier.history` (which counts the opening `SEALED_DIVERGENT`
entry as well, and is not a ledger), and the second is wall-clock rounding. Four
phases are *named* above and three transitions *happen*; the ledger counts
transitions.

So the barrier *has* been crossed — on a debug root, by a script, in a tenth of
a second. The earlier text called it barren ("no card and no message in it") and
that is wrong in the direction that matters least but changes the reading: the
root has **no `tasks.jsonl` at all** — never a card — and **two public messages
and two private notes**. It is a scripted but complete run:

    private/a  "a position"      (SEALED_DIVERGENT, round 0)
    private/b  "b position"      (SEALED_DIVERGENT, round 0)
    m0001  b -> a  question   "Name the observation that would have made you
                              drop your first claim."
    m0002  a -> b  rebuttal   "The observation is a second draft changing shape
                              after exposure; I would have dropped it if two
                              drafts had stayed incompatible."

Those are, in miniature, the two artefacts the whole design exists to produce:
the question is the falsifier asked *for its own answer*, and the answer names a
specific observation. `echo_ratio: 0.0` on both. So the repo's only
barrier-crossing run is also its only example of a well-formed cross-examination
— not because anyone built one, but because a debug script did. **The demo
proves the mechanism can work and the census proves nobody has used it**; both
sentences are true of the same five-row file.

That is a weaker fact than the sentence was claiming and a more interesting one:
the five channels in `channels/` are the only ones that ever held real work, and
none of them got past `COMMIT`. This root is *visible* in every `git show` and
nobody had read it — but **not for the reason this paragraph first gave.**

It said "the unfixed `.gitignore` does not cover `.dbg/`", citing
`git check-ignore .dbg/channels/c/ledger.jsonl` → **1**. The rule does cover it.
`.gitignore:13` is `.dbg/` and has been since `0dae3f3`. The **1** is git's
default `check-ignore` declining to answer for a **tracked** path — it is a
statement about the index, not about the rule:

    $ git check-ignore -v .dbg/channels/c/ledger.jsonl      # tracked
    (no output)                                              rc=1
    $ git check-ignore -v .dbg/nonexistent.jsonl            # untracked
    .gitignore:13:.dbg/     .dbg/nonexistent.jsonl           rc=0
    $ git check-ignore -v --no-index .dbg/channels/c/ledger.jsonl
    .gitignore:13:.dbg/     .dbg/channels/c/ledger.jsonl     rc=0

The real chronology is six minutes wide and runs the other way. The 11 `.dbg`
files entered the index in `94c116d` (`16:15:07 +0800`); the ignore line was
added in `0dae3f3` (`16:21:05 +0800`), and `git merge-base --is-ancestor 94c116d
0dae3f3` is **true**. The debug root was committed first, the rule was written
minutes later by the same session — and a path already in the index is never
ignored again, so the rule has been inert on it ever since. That is the
mechanism, and it is a much smaller one than a missing rule: nobody forgot to
write the line; the line cannot reach backwards. The same residue is still in
the tree — `outbox/_drafts/handoff-to-codex.md` is tracked while
`outbox/_drafts/` is ignored (`git check-ignore --no-index` finds 12 tracked
paths matching the ignore file, all 11 `.dbg` and that one).

*(The correction is worth more than the claim. `rc=1` was a real measurement
attached to an invented reason — "check-ignore says no, therefore the rule is
missing" — which is the document's own failure mode for the third time in this
section. The rule was never missing. What is missing is anything that would
have made me test the difference between "this path is untracked and would be
ignored" and "this path is tracked and the question does not apply".)*

**A census that names its own glob is a census; one that says "no live channel"
is a sentence about a directory the author did not enumerate.** Re-measured at
`7def563` (the ledger counts move between sessions; the phase column does not,
which is itself the point):

| channel | phase | seals | private | public | ledger |
|---|---|---|---|---|---|
| `barrier-v0` | SYNTHESIS | 2 | 4 | 2 | 6 |
| `hello` | COMMIT | 3 | 9 | 2 | **348** |
| `dev` | SEALED_DIVERGENT | 0 | 0 | 0 | 1 |
| `s2-scratch` | SEALED_DIVERGENT | 1 | 2 | 0 | 2 |
| `s2-scratch2` | SEALED_DIVERGENT | 0 | 1 | 0 | 1 |

Re-measured again at `e6ba913`, from the blobs rather than the worktree, every
cell is identical except `hello`'s ledger, **348 → 349**: one more row, added by
the same work this document describes, in the hours between the two readings.
`barrier-v0`'s 6 was checked two ways: `git show 7def563:channels/barrier-v0/
ledger.jsonl | wc -l` returns 6 (blob `a175be050f30d8107fbe2bcc065600c32fc63f58`),
and the worktree is 6. A falsifier read the committed copy as empty by mistake —
it is not, and the cell was not changed by that misreading. The `hello` ledger
grew 320 → 348 → 349 while this document was being written — every row of it a
refusal or a phase row from the same work the document describes. The census is
the one place where a number that moves is *evidence* rather than drift: five
channels, none above `COMMIT` after two days of real use.

**Two columns of the table are counts of messages and three are counts of
files, and the caption has to say which.** `seals`, `private` and `public` are
records: `seals/*.json`, the lines of `private/*.jsonl`, the lines of
`log.jsonl`. `ledger` is lines of `ledger.jsonl` — also records. What is *not* a
count here is anything you get by `ls | wc -l` on `private/`: for `hello` that
returns **4**, because four agents each have a file, and the table's 9 is the
nine notes inside them. Measured both ways at HEAD and they agree with the
table; the distinction is written down because it is the exact one the
`dev` paragraph below got wrong once already.

The channel named *"aim development"* (`channels/dev`, topic `aim development:
task store, rooms, dashboard`, leader `human`, participants
`claude-session1, codex`) holds **one** row in its ledger and no `log.jsonl` at
all — it never carried a message, a seal or a room (measured: `seals/` 0 files,
`private/` 0 files, `log.jsonl` absent, no `rooms/`), and the single row is a
`task move` refusal (`class: form`, `no such task: T-0206`, `09:43:27Z`). The
cell of the census says so.
*(The sentence here first read "is empty" — a misreading of a `log` count as a
`ledger` count, and a falsifier caught it. The correction then said the row was
"a refusal of mine from this very rewrite", which is also wrong: `09:43Z` is ten
hours before the first SOP commit. Both errors were statements about provenance
neither of us had looked up.)* The channel named *"Transport test"* holds the
work. The record says so plainly — that is what the census is for — but nothing
in the tool makes the naming mean anything.

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

**The winner is chosen by the alphabet, not by which project came second.**
The allocator is per-channel (`bin/aim:1832`); the merge is per-root
(`aimboard/fabric.py:281`). Either half alone is defensible; together they are
a data-loss shape, and nothing warns. *(This sentence used to read "a second
project silently deletes the first project's work", which is the right fear
stated with the wrong mechanism. Measured two roots, both orders:
`zeta` created first then `alpha` → survivor `ZETA work`; `alpha` first then
`zeta` → survivor `ZETA work`. The survivor is `zeta`'s card either way, because
`list_channels` returns `sorted(...)` and the dict comprehension overwrites in
that order — so the loss follows the alphabet and is blind to time. The
doc's own example, `projA`/`projB`, holds only because `B` sorts after `A`.)*

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
gone with nothing said.

**What the code decides by is the alphabet; what it is blind to is time.** No
step in the path looks at either copy's `created` timestamp — `list_channels`
sorts *names*, and the merge is a dict comprehension over that order — so the
survivor is stable across reloads and blind to which card was written first.
**The claim the code supports is recency-blindness, and nothing more than that.**
An earlier draft went further and said *"in this run it cost nothing: for five of
the six ids `hello`'s `created` also predates `barrier-v0`'s, so 'most recent
wins' would have picked the same copy."* The five-of-six is right **only for the
`created` event**. Re-derived on the *last* event of each copy — a defensible
reading of "most recent", and the one a reader who says "recency" usually means —
**three of the six flip**, and the fold keeps the copy that was touched *less*
recently:

| id | `hello` last event | `barrier-v0` last event | newest wins | the fold keeps |
|---|---|---|---|---|
| T-0156 | 09:32:01.676Z | 03:26:33.972Z | `hello` | `hello` ✓ |
| T-0157 | 03:02:57.644Z | 07:30:23.301Z | `barrier-v0` | `hello` ✗ |
| T-0158 | 03:02:58.088Z | 07:58:19.376Z | `barrier-v0` | `hello` ✗ |
| T-0159 | 08:17:41.136Z | 08:28:39.670Z | `barrier-v0` | `hello` ✗ |
| T-0160 | 09:29:54.684Z | 08:28:44.180Z | `hello` | `hello` ✓ |
| T-0161 | 09:29:50.635Z | 08:35:25.956Z | `hello` | `hello` ✓ |

So the honest sentence is weaker than either draft's: **it is not that recency
would have agreed. It is that nothing in the system has an opinion about recency
at all, so "would recency have agreed" has no answer the code can give.** The
counts below are the part that is not a matter of reading: it is the silence that
matters — nothing compares the two rows, and nothing reports that one was
dropped.

**The record counts them; the board does not, and the two numbers reach a reader
by different routes.** Measured at two viewers, so the discrepancy is not a
gating artefact — it is the same gap at both. Re-measured at `7def563`:

| | raw `created` in the store | `/api/flow` `opened` | `board.tasks` created events | the gap |
|---|---|---|---|---|
| `as=human` | **98** | 98 | 91 | 6 dual-channel ids + 1 retracted = 7 |
| `as=claude-session1` | **98** | 70 | 63 | the same 6 + 1 |

(`done` agrees exactly at both viewers — 65 and 59.) Both columns stay internally
consistent (`98 − 91 = 7`), which is the check that the method is sound rather
than the number. `flow_series` was measured as 97/97/90 one commit earlier and
the store gained a `created` (T-0246, filed by this pass) between the two reads —
the arithmetic is the stable part, and it is why the table is now pinned to a
revision instead of saying "measured right now". `flow_series` reads the raw
event list and counts **both** copies of a dual-channel id; `fold_tasks` keys by
id and keeps one. The seventh is `T-0001`: the store holds
`created 02:16:37Z` then `retracted 02:28:03.908Z`, while the payload's `T-0001`
row is the **plan seed of the same id** — a different title
(`Freeze the PM contract…` vs `Fix Kanban filtering…`), `source: plan.json`,
`provenance: seed only`, and `events: []`. So one id carries a retracted store
event and a live plan seed, and the board shows the seed while `flow` counts the
event. Neither number is wrong; they answer different questions about the same
log, and nothing tells a reader which one they are looking at.

**One id space for N projects means the board shows one project's cards wherever
two projects used the same id, and nothing says so.** *(This read "the second
project's board is a partial view of the first's", which names an ordering the
merge does not have: the survivor is decided by `sorted()` over channel names, so
which project is "first" depends on the alphabet and not on creation order — see
§2.1's measurement, two roots, both orders.)*

**The leader's own blocker is that measurement, and it is filed eight times
[V].** Eight `created` rows carry the exact title *"Leader: approve the plan;
advance hello past SEALED_DIVERGENT"* — `T-0233`, `T-0234`, `T-0240` in `hello`
(all 08:28:0x–08:28:23Z, three created inside 14 seconds) and `T-0156`,
`T-0157`, `T-0158`, `T-0159`, `T-0161` in `barrier-v0`, whose `hello` copies are
the entries in the table above. Measured on the rendered board, not the store:
the three `hello` cards fold to `owner=human, status=review, visibility=draft` —
**the leader owns the cards asking the leader to act.**

**And a ninth copy arrives by the other id source, so the count depends on
which surface you ask [V].** Measured by parsing both sources and the payload:

| asked of | rows with that exact title |
|---|---|
| `channels/*/tasks.jsonl` | **8** — the five `barrier-v0` rows above plus `T-0233`/`T-0234`/`T-0240` in `hello` |
| `plan/*.json` | **1** — `T-0004` |
| both stores | **9** |
| `/api/state?as=human` — what the browser draws | **4** — `T-0004` (`dropped`, `provenance: seed only`), `T-0233`/`T-0234`/`T-0240` (`review`, `store only`) |

So the board **shows four** and the two stores **hold nine**, and the gap is the
whole of §2.1: five of the nine are `barrier-v0` copies of ids `hello` also
allocated, and the merge discards them. Of the four the browser does draw, the
only one that looks already handled is the plan seed — because `dropped` is
terminal — and it is the only one that was never work at all. Both id sources
meet in that one card.

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
files could collide with each other. `plan/plan.json` carries **82** seeds, and
it is their *ids* that run to `T-0155` — the list is sparse, with **73 gaps** in
`1..155`. An earlier draft of this paragraph read the top of the id range as the
size of the list, which is exactly the kind of number that looks measured. The
floor is what the allocator actually reads, so the sentence that survives is the
one about the range: `hello` is at `T-0248` rather than `T-0091` because 155 ids
are spoken for, not because 155 seeds exist. *(This said `T-0245` — a falsifier
re-derived it, and then re-derived it again: `T-0245` was `9d64d36`, `T-0247`
was HEAD when the correction was written, and the live store's max is `T-0248`.
The pin added to stop exactly this rot did not stop it, because the pin names a
revision and the sentence reads a working tree.)* Measured separately on a throwaway
root: `plan/a.json` and `plan/b.json` each
seeding `T-0001`, then a real `aim task new` → `T-0002` (the floor works), and
the board folds `{'T-0001': 'seed from plan A', 'T-0002': 'real work'}` —
`plan B`'s description is gone with nothing said.

`channel_kind` / `channel_lifecycle` (`aimboard/fabric.py:49,58`) compute
scratch-vs-project and empty/dormant/active. **Nothing reads either.** `hello`
derives `project` and `dev` derives `project`; the heuristic miscalibrates
exactly where T-0216 says it does.

## 2.2 N agents: the collision control is prose

`codex` announced a write-set protocol (`CLAIM: <path>` / `RELEASED: <path>`
comments). It is a good rule and **nothing enforces it**: `grep CLAIM bin/aim` →
0 hits. *(The announcement never reached the public channel either — it is in
`channels/hello/private/codex.jsonl`, and `channels/hello/log.jsonl` holds three
rows, none of them the protocol. A peer could not have fetched it: `aim search
CLAIM --as human --channel hello` returns rc 2, `REFUSED: name at least one
scope`. So the rule is unenforced **and** unannounced, which is two failures and
the sentence had one.)*

What *is* enforced, per primitive: append (flock + chained write), registry
(`update_json`), card ownership (`task claim`), the selftest lockfile. Those are
the same-resource protections for **everything the tool models as an object** —
and the sentence that used to stand here, *"the shared resource is the file and
nothing owns it"*, overstated the gap in one direction and understated it in the
other. Measured on a throwaway root, a channel that names one workspace twice:

    aim new-channel --id ch --participants a,b --leader h \
        --workspace a=/root/tmp/agent-im --workspace b=/root/tmp/agent-im
    -> rc 2  REFUSED: channel 'ch' declares a shared workspace, so its
       participants can read each other's work, and a barrier here is a claim
       the tool cannot keep.

`_workspace_conflicts:512` + `assert_barrier_defensible:556` are the mechanism,
`aim status --channel ch` prints `workspace … WARNING: 1 shared writable
path(s)`, and 35 `task_published_during_divergence` rows in the live ledger
record the *exposure* half of the same concern. So what is missing is narrower
and sharper than "nothing owns it": **two hands on one *card* is refused, two
hands on one *file* is refused when the channel declares it, and there is no verb
that takes a path** — so the `CLAIM:` convention has no product surface to land
on, and a path collision inside a workspace nobody declared is invisible.

`aim register --force` takes over a registered id with **no liveness check** — it
reads `registry.json` (`bin/aim:979`) and compares only `prior` and `args.force`
(`:980`). A returning session and a
second harness are indistinguishable. The refined fix already exists one layer
down (T-0242 derived `session_of()` from the pid for ledger rows) and is not
applied to registration.

---

# Part III — The methodology: how to check a claim

This is the part that lets the leader *verify the judgement*. Seven rules, each
of which this repo has been burned by at least once.

**1. Ask which of the three marks a claim carries, and demand the command.**
"Enforced" means a refusal you can paste. "Recorded" means a ledger row you can
paste. Everything else is prose, and this repo has repeatedly read prose as
enforcement.

**2. A marker that passes on any failure measures nothing.**
`test.fail()` and `@unittest.expectedFailure` are satisfied by *any* failure, so
they do not record *which* failure they absorbed. Measured at HEAD: **14 live
markers** — **0** `test.fail(...)` *calls* in `web/tests` (a text grep returns 21
hits, and every one of them is a comment explaining a marker that came *off*; the
count of live calls is zero) plus **14** `@unittest.expectedFailure` decorators
in `tests/`. Of those, most had drifted — stale (the defect was fixed),
unfalsifiable (the apparatus cannot pass whatever the product does), or honest.
**Two of the drifted ones were hiding a live product defect.**

The number here used to read **19**, and that error is worth keeping because its
cause is a *third* kind of count. 19 was the total at `da10892` (5 live
`test.fail` calls + 14 decorators); it fell to 14 by `720cb83` and has been 14
ever since. So a marker population **shrinks as defects are fixed** — neither the
progress bar rule 7's corollary gives for snapshots nor a ledger's monotone
growth. **A count that only falls is a TODO; a count that only rises is a
ledger; a count that does neither is a structure.** Quoting one as if it were
another is how a document ends up measuring a tree two of its own commits back.

**3. A suite that nothing repeats is not a green.**
Measured 2026-09-23: 28 of the 29 `tests/test_*.py` files rc 0, with `selftest.sh`
199/0 and `conformance.py` 41/41 green, **while `npx playwright test` flaked on
one test** — `web/tests/boards.spec.js:450`, *"a phase is said in English, and the
enum stays available but secondary"*, at its `#/barrier` navigation (the earlier
draft of this rule said "the one red" and named no file, which is the shape of
error this rule is about: a rate quoted over an unstated denominator). And the
29th of those files is the one that cannot run here at all,
so the honest phrasing is *"28 green, one unrunnable"*, not *"all 29 green and a
thirtieth file besides"*. The first version of this rule said "a thirtieth python
file", and there is no thirtieth: `tests/test_*.py` is 29 files, `tests/*.py` is
33, and the other four are three `attack_*.py` scripts plus `conformance.py` —
reports and a runner rather than suites. A falsifier counted, and *"a category
that does not exist"* is the exact note an earlier commit message in this repo
had already attached to the same mistake. The README's five-command list is not
the test suite; enumerate `tests/` yourself and count what you enumerate.

A later pass refined both halves, and the refinement is the lesson: at `9fc4d7d`
the full suite was **175 passed / 1 failed**, and the re-run was **176 passed** —
so the rate is load-dependent and a single green proves nothing. The one red
reproduces 3/3 alone and 1-in-2 in a full run. And the file that "cannot be run"
(`tests/test_a2a_reference_client.py`) is not a failing test on this box at all
**and the mechanism is not the one first written here**: its shebang is
`#!/usr/bin/env python3` — it has been that at every revision in its history —
and the file's mode is 0644, so invoking it through the shebang would give 126
rather than 2. The **rc 2 comes from a guard inside the file** (`:386-393`): the
`a2a-sdk` module is not importable, so it prints **four** lines of remediation and
calls `sys.exit(2)`. **The absence is the absence of a Python package from the
interpreter's path, not of a shebang interpreter** — the venv path in the printed
message is advice, not delegation. Two consequences worth stating because they
are what a runner sees: `python3 -m unittest tests.test_a2a_reference_client`
exits **0** with `OK (skipped=6)`, so the module path is green and the *script*
path is red — the same file reports success or a 2 depending on how it is
invoked, and that is why enumerating exit codes is not enough. And
`npx playwright test` from the repo root does not find the suite at all; it runs
from `web/` (`cd web && npx playwright test` → `176 tests in 33 files`), which is
the kind of detail a five-command README block omits. It is a real defect with an
alarm that *does*
fire, loudly, on stderr, and that nobody reads, because a runner enumerating exit
codes files it as "skipped". **Report which of red-by-assertion and
red-by-absence you are looking at, because they call for opposite responses —
one is a fix, the other is a missing environment.**

**4. Name the revision, and read what it actually hashes.** `/api/revision` is
the right first read, and `stale` is a weaker signal than the three-state
docstring at `aimboard/revision.py:116-125` implies. Measured live, one board on
the canonical port:

    {"fabric": "2980293",
     "bundle": {"revision": "2930c74+dirty", "built_at": "...T16:42:05Z",
                "dirty": true, "source": "vite build",
                "source_sha256": "edd2518e..."},
     "stale": false, "front_end_sha256": "edd2518e..."}

**`stale: false` while the bundle says `+dirty`** — because `front_end_hash()`
(`:90-94`) hashes the **working tree** (`web/src`, `index.html`,
`vite.config.js`), not the commit. So `stale` answers *"do the bytes on the wire
match the source as it sits right now"*, which is true and useful, and it does
**not** answer *"was this page built from the committed code"*, which is the
question a document getting filed about a revision is usually asking. The pair
`bundle.revision = 2930c74+dirty` and `fabric = 2980293` is the honest answer
and both halves have to be read. `null` remains what the docstring says it is: a
bundle that recorded nothing, which is not "up to date".

**5. Split a merged denominator before quoting a rate.** "142 cards in
review/done, 46 commented" was the merge of 70 *recorded* cards and 72 *plan
promises*. Split, the claim was sharper: 24 of the 70 *recorded* ones carry no
comment. *(Re-derived at HEAD, with `plan/*.json` loaded so both halves are
present: merged `review/done` is **142**, and the split is **70 recorded + 72
promises** — the promise half from `plan/plan.json`'s seeds, the recorded half
from the merged store minus those ids — with **46** of the 70 carrying a comment
and **24** not. Every figure in the sentence reproduces; the `46` is the
numerator, not the size of the recorded half.)* The promise half is not evidence
either way. **The merge is the thing
this repo keeps finding unlabelled** — the same shape as the two-project id
space, and as `remaining` in the burndown.

**6. The three `attack_*.py` scripts exit 0 on defects.** They print a table and
return success. They are reports. If anything scripts their exit code it will
read a DEFECT as a pass.

**7. Give the verifier the instruction "falsify this", not "check this".**
Every number in Parts I, II and IV was re-derived from primary data by an
independent reader whose instruction was to try to break it. Six came back wrong
and three claims came back over-argued — **and all nine were mine.** Nothing was
falsified in substance.

| what was wrong | how a falsifier caught it |
|---|---|
| "the alphabet, *rather than recency or authority*" | it re-measured which copy was older: for 5 of 6 ids recency picked the same one, so the "rather than" claimed a contrast the data cannot show |
| "serves them *by id, title and body*" | it read the serialiser and found `a2a_task` never emits `title` or `body` — the mechanism was right and the sentence sold more |
| ledger totals 352 / 276 / 343 (rows, refusals, class-bearing) | it re-counted and got **354 / 276 / 345**, because the ledger had grown since I wrote the sentence — and a third measurement at `7def563` reads **358 / 280 / 349**, so the number is a snapshot by construction (see §4.6) |

The pattern across all three: **the measurement was sound and the sentence was
not.** A verifier asked to *confirm* would have agreed with each; the instruction
to falsify is what makes the difference, and it is cheap — one word in the
prompt. Two corollaries the same pass established: give the falsifier the
*command*, not the conclusion (every verifier that re-ran the numbers found drift
I could not have seen by re-reading); and when a number is a **snapshot of
something that grows** — a mail store, a ledger — say so in the sentence, because
otherwise the next reader measures a different tree and concludes you lied.

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
| 6 | a card reaches `done` by a recorded move | **`task new --status done` is legal; the burndown reads 28 where the board's own count reads 24, and those two differences are not the same four rows** — measured in §1.4 | `bin/aim:1939` **[V]** |
| 7 | `CROSS_EXAMINE → SYNTHESIS` is the only rule-changing edge | **`RESOLVE → CROSS_EXAMINE` re-opens both**; `design/17:239` says otherwise | `bin/aim:51` **[V]** |
| 8 | `--force` skips transition legality and nothing else | **it also bypasses the seal quorum and the synthesizer check**; `design/17:222` says otherwise | `bin/aim:1478`, `:1491` **[V]** |
| 9 | `RESOLVE` is where the leader decides | **`channel_say=False` there refuses the leader's own ruling** | **[V]** |
| 10 | the write-set protocol prevents collisions | **nothing reads `CLAIM:`/`RELEASED:`; two hands on one file leave no trace** | `grep` = 0 hits **[V]** |
| 11 | a `human` is the leader, and only the leader | **every gate in the tool exempts any name that typed `--kind human`, and the mail gate never compares the viewer against a channel's `leader` field at all** — see below, it is the largest single hole | `aimboard/gate.py:159,191` **[V]**, §4.1 |
| 12 | a foreign A2A client sees what the board sees | **`/rpc?as=<registered stranger>` returns the drafts the board withholds from the same caller — measured 180 vs the board's 107, a 73-draft divergence** | `aimboard/a2a.py:794` **[V]** |
| 13 | the seal hides a participant's reasoning from everyone but the synthesizer | **any self-declared `human` can read the mixed bundle — including one who never sealed and is not a participant** | `bin/aim:1610` **[V]** |
| 14 | a plan seed is deduplicated | **two `plan/*.json` naming one id silently lose the second**, first-wins by glob order | `aimboard/fabric.py:131,135` **[V]** |
| 15 | a session's advance request is checked before it is recorded | **`request-advance` validates nothing: `--to NOT_A_PHASE` → rc 0, and the ledger gets no refusal row** | `bin/aim:1590-1604` **[V]**, §1.3.2 |
| 16 | the dashboard writes as the identity it was started as | **without `--as` it writes as `channels[0].leader`, i.e. the alphabetically-first channel's leader** | `aimboard/cli.py:505` **[V]**, §4.5 |
| 17 | `ledger.jsonl` is a refusal ledger whose `class` is `barrier\|form\|unrecorded` | **the file holds 358 rows; 280 are refusals. 36 are the acts README §3 asks a `barrier` row to make findable, and 33 `push` rows carry a class that is not in the vocabulary** — see §4.6 | measured **[V]**, §4.6 |

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

— **the `and`-joined shape**, which is the one that *bites*: it refuses the
bystander only when the caller is neither the synthesizer nor a `human`. The
sibling sentences used to point at `bin/aim:2126` and the two `gate.py` lines as
"the same shape", and all three are the **mirror** shape — `:2126` is
`actor_exempt = kind == "human"`, and `gate.py:24`/`gate.py:159` are
`kind == "human"` as well, i.e. the flag read as a *positive*. Cite the `!=`
family when the claim is about the exemption (`:1937`, `:2020`, `:2526`,
`:2723`, `:2747`, `:2835`, `:2981`, `:3301`, `:4042` are the bare membership
ones) and the `==` family when the claim is about the reader (§4.1's table
below).

**"At every gate" is not an impression; it is a count, and the count has a shape
worth stating.** Parsed rather than grepped — `ast.Compare` nodes with a
`"human"` operand, over `bin/aim` and every `.py` under `aimboard/` (**not**
`aimboard/*.py`: `aimboard/views/` is a subdirectory, and missing it is how the
earlier version of this table lost a surface):

| | |
|---|---|
| comparisons on `"human"` | **31** — 25 `!=`, 6 `==` |
| of which in `bin/aim` | 27 (25 NotEq over **19 distinct functions**, 2 Eq) |
| of which in `aimboard/` | 4 — `a2a.py:788 task_visible`, `gate.py:24 walled_off`, `gate.py:159 conversation_view`, **`views/chat.py:25 render_conversation`** |
| distinct enclosing functions | **24** |
| that also ask *who is calling* | **1** — `require_leader` (`bin/aim:831`) |

A grep for the text `!= "human"` returns **26**, one more than the AST finds;
the extra is a comment at `bin/aim:4424` quoting the idiom. That one-line gap is
the difference between counting a token and counting a *branch*, and it is why
the number here is from the parser.

**And exactly one of the thirty-one also compares the caller against the named
leader.** `require_leader` reads
`if kind != "human" or who != manifest["leader"]` (`bin/aim:831`) — the only site
where `human` is not sufficient on its own. *(A falsifier broke the stronger
version of this sentence, which read "the only site where… Every other one is a
disjunction whose left side is a membership test and whose right side is the
self-declared flag". That is true of at most 21 of the 30 that are not
`require_leader`; the other **8 stand alone**, and the joins that exist are
**`and`s**, not disjunctions. The narrow claim — one site compares the caller to
`manifest["leader"]` — is the one that survives, and it is the one measured.)*

**But "every gate" is itself the wrong shape of sentence, and the falsifier was
right to break it.** Seven gates on the barrier path carry **no** exemption at
all — `assert_barrier_defensible:556`, `resolve_actor:806`, `gate:850`,
`cmd_seal:1354`, `cmd_advance:1450`, `cmd_request_advance:1590`,
`cmd_reveal:3242` — and their refusals are the ones that hold everywhere. So the
true statement is narrower and stronger than the one this section was selling:
**the exemption is spelled at every gate that *consults a membership test*, and
absent from every gate that checks the barrier's own bookkeeping.** What that
buys is not "a human can do anything" but "a human can do anything a
*participant* could do, without being one" — which is exactly the measured
result in the table at the top of this section, and not the total bypass the
phrase "master key" suggests.**
stated as a number: **31 comparisons, 24 functions, 1 of them also compares the
caller against the manifest's `leader` field.**

*(This line read "30 comparisons" — the table eleven lines above it says 31, and
an AST walk says 31, so the section contradicted itself in one screen. It also
said "1 of them also checks the name", which is right only under a reading the
sentence did not give: seven of the 31 sit in a function that has the caller's
identity in scope, and of those only `require_leader:831` compares it against
`manifest["leader"]`. `cmd_task_edit:2289` and `_load_task_or_die:2079` also ask
who is calling and then test **membership** (`who not in (owner, created_by)`),
which is a different question. The precise claim is the narrow one, and it is
the one the sentence now makes.)*

The six `==` sites are the mirror image and worth one line, because a reader who
greps only for the exemption misses them: `cmd_task_move:2126` sets
`actor_exempt = kind == "human"` and consults it twice, and the other five ask
the same predicate as a positive (`_room_withheld:2727`, `task_visible:788`,
`walled_off:24`, `conversation_view:159`, `views/chat.py:25`). Same rule,
spelled the other way round — the same rule as a **positive predicate**, which is
a different claim from §4.4's (that section is about one rule with three
implementations; this is about one rule *spelled two ways*, and both are one
level below the design's "one rule, one owner").
*(This said "five" and named five; the table above counts six `==` and lists
`views/chat.py:25` among them, so the enumeration had dropped the one surface
that paragraph is about.)*

**And the 31 are not 31 disjunctions, and the paragraph above had the join
shape exactly backwards.** Measured over the same 31 nodes, with each node's
*parent* expression read rather than its own text: **22 sit inside an `and`, one
inside an `or`, and 8 stand alone**. Of the 22, **21 are joined to a test on the
caller** (`who not in m["participants"]` at `:1937`, `:2020`, `:2526`, `:2723`,
`:2747`, `:2835`, `:2981`, `:3301`, `:4042`; `who != synthesizer` at `:1171`,
`:1610`; `_visible_to` at `:2079`, `:2563`, `:4155`, `:4164`; the owner pair at
`:2289`; `author` at `:2941`, `:2995`; and the two-conjunct `:1128`, `:3765`),
and the 22nd (`:1946`) is joined to no caller test at all — its siblings are
`vis == "published"` and `phase in DIVERGENCE_PHASES`.

**Which way round the joins run is the whole point, and it is the reverse of
what this section used to say.** For `A and B` to `die`, both must hold; a
`kind != "human" and who not in (participants)` guard therefore **lets a
self-declared `human` through on the flag alone, without membership** — measured
on a throwaway root: `ghosth` (registered `--kind human`, participant of
nothing) ran `task new` rc 0 and `aim room new` rc 0, into a channel whose
participants list it is not in. The single `or` is the opposite:
`kind != "human" or who != leader` dies unless the caller is **both** a human
**and** the named leader, so `require_leader:831` is the one gate where the flag
is not sufficient. So **the wide-open shape is the one the tree uses 22 times,
and the strict shape once** — and the sentence this replaces, which called `and`
"the strict join … a gate that still bites" and `or` "the true master key", had
each label on the wrong operator. What the count actually measures is that the
exemption is *broader* than "master key" suggested, not narrower.
*(A falsifier caught this by counting each node's enclosing expression instead of
its text; the AST block above and the end-to-end measurements at the top of this
section both survive unchanged.)*

**And the mail gate is the widest one, because mail is not addressed to a
channel.** `gate.conversation_view` does not ask whether the viewer leads
anything, and it never reads a channel's `leader` field at all — `grep -n leader
aimboard/gate.py` returns five lines, two of them prose (`:21`, `:153`), and the
only *comparison* is `:159`:

    kind = (state["registry"].get(viewer) or {}).get("kind", "")
    is_leader = kind == "human"
    …
    if not is_leader and viewer not in (sender, to):   # :191
        withheld += 1

So the exempt set is not the closed set of leaders of live channels. The live
registry holds **six** registered agents — `claude-session1`, `claude-session2`,
`codex`, `codex-orangement`, `human`, `synthesizer-v0` — and exactly one typed
`human`; the seat named `human` is factually the leader of all five channels
(`barrier-v0`, `dev`, `hello`, `s2-scratch`, `s2-scratch2`), which is why the
hole has cost nothing so far. **Nothing in the code makes that coincidence
true**, and this is the paragraph that says so out loud rather than one that
asserts it holds. *(This said "five registered agents"; the file holds six, and
the table below is five *seats*, which is a different set — one of the six,
`claude-session2`, is in the registry and in no table here.)*

Measured live, one `/api/state` per seat, same second, against a store of
**251** conversation records (the store is `outbox/`, and it grows one record
per message — this table is a snapshot, and the *structure* is what does not
move: `human` reads all of it and is withheld nothing, the two `codex` seats
read 207 and 67 from the same store in the same second, and a seat that is
party to nothing reads 0):

| seat | kind | `conversation.is_leader` | mail read | `withheld` | `mail read − withheld` |
|---|---|---|---|---|---|
| `human` | `human` | **true** | **251** | 0 | 251 |
| `codex` | `codex` | false | 207 | 48 | 159 |
| `claude-session1` | `claude` | false | 189 | 65 | 124 |
| `codex-orangement` | `codex` | false | 67 | 189 | −122 |
| `claude-session2` | `claude` | false | 0 | 255 | −255 |
| `synthesizer-v0` | `claude` | false | 0 | 255 | −255 |

**The last column is there because it is negative, and that is a finding rather
than arithmetic.** `withheld` is not the count of mail this seat was denied — it
is one counter serving the log, the rooms and the mail together, so the store
size it is "withheld from" is the whole store and not this seat's share. A reader
who takes `mail + withheld` as the store size gets 453 for `codex` against a
store of 251. *(The earlier version of this table gave `withheld` as 0/46/65/186/
252 and a store of 249; every number moved with the store, which is the point
§4.6 makes one section later.)*

The sentence this table replaces read *"`human` reads **237** mail rows where
`codex` reads 200 and `claude-session1` reads 175"*. Those three numbers are
stale and they are also **the wrong quantity**. 237 is `mail + withheld` — the
whole store as it stood then — so the old sentence compared a full view against
partial ones and called the difference a leak size. Worse, it named `codex`,
whose two seats read **206** and **67** from the same store in the same second:
the identity is not enough to predict what a seat reads, which was the fact
worth stating and the one the old sentence hid.

(`withheld` and *mail withheld* differ by 3–4, and the mechanism is not "gated
channels". `withheld` is one counter that `gate.conversation_view` increments in
three places — `:168` for a gated **public-log message** the viewer did not send,
`:179` for hidden **rooms**, `:192` for mail — so the residue is gated messages
in `channels/*/log.jsonl`. Measured at this snapshot: gated log messages per seat
are `codex` 4, `claude-session1` 3, `codex-orangement` 5, `synthesizer-v0` 4,
`claude-session2` 4, and hidden rooms are **0 for every seat** because no room
exists in the live tree. So `codex`'s `withheld` 48 = mail 44 + log 4, and
`synthesizer-v0`'s 255 = mail 251 + log 4. Every seat is gated on the same **5**
channels — the channel count is constant and explains none of the variation.
*(This paragraph used to say the residue "is the count of gated *channels*, which
carry no records of their own", and to give the range as "0–4". Both are wrong
and they are wrong in opposite directions: the count is constant at 5, and the
residue reaches 5 on the seat with the most gated log messages. `:168` was never
named.)*

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
participates in **no** channel, on one served root in one second:

| seat | `/api/state` tasks | `withheld_tasks` | `/rpc` `ListTasks` (whole store) | `rpc \ board` |
|---|---|---|---|---|
| `synthesizer-v0` | 107 | 73 | **180** | **73** |
| `claude-session1` | 148 | 32 | 148 | 0 |
| `codex` | 131 | 49 | 131 | 0 |
| `human` | 180 | 0 | 180 | 0 |

(**180/180 distinct** is the whole store, and it is the number that matters: the
non-participant's `/rpc` view *is* the board's own `human` view. The earlier
version of this section printed `71` and `179 returned, 178 distinct`. The 71 is
one draft stale — it is **73** now — and the `179/178` was an artefact of the
default `pageSize`, not the gate: `ListTasks` with no params returns **50** rows
and a non-empty `nextPageToken` for every seat, so the "179" was whatever
`pageSize` the earlier probe passed. Every printed number here is re-derived at
one `pageSize` (`500`) so the rows count what the gate lets through and not what
the paginator happens to hand back. §4.6 exists because counts like this one
move; this section exists because a *page size* moved one.)

Every one of the 73 is a draft. The board counts them and withholds them; `/rpc`
serves them, on the same port, to the same caller, in the same second.
`aimboard/a2a.py:794` spells the stranger test as
`if viewer not in channel.get("participants", []): return True` — *a stranger is
not a participant, so show them everything* — where `gate.walled_off` spells the
same membership test as the reason to **shut them out**
(`aimboard/gate.py:26`). Two functions, one condition, opposite verdicts. (The
line the doc gave for the owner/creator union, `:794`, is the stranger return;
the union itself is `:796`, `return viewer in (task.get("owner"),
task.get("created_by"))`.)

**The listing doubles its own boundary row, and that is a third disagreement.**
`list_tasks`'s cursor is the last id of the previous page:
`next_token = page[-1]["id"]` (`a2a.py:980`), and the next page starts at
`ids.index(page_token)` (`a2a.py:977`). So the boundary task is served **twice**,
once as the last of one page and once as the first of the next — measured, with
`pageSize=5` on the live board: page 1 is
`T-0248, T-0247, T-0246, T-0245, T-0244` and page 2 begins `T-0244`, so the two
pages together hold 9 distinct ids over 10 rows. A client that paginates without
deduplicating reads one card twice per page boundary. *(Both citations were off
by three and five lines in the earlier draft; `:972` is blank.)*

**What crosses the wire is narrower than "the card", and the narrowing is worth
stating precisely.** `a2a_task` (`aimboard/a2a.py:836`) publishes `id`,
`status{state,timestamp}`, and `metadata.aim` — `visibility`, `owner`,
`priority`, `milestone`, `blocked_by`, `estimate`, `start`, `due`, `accept`,
`tags` — plus, only when `includeArtifacts=true`, the acceptance condition as an
artifact. It publishes **no `title` and no `body`**: `aimboard/a2a.py` never reads
`task["title"]` on that path. That claim survives contact with the falsifier, but
only because of an accident worth naming: **`_event_text` (`a2a.py:735`) reads
`event.get("title", "")` for a `created` event, and `_task_messages` (`:696`) is
wired to `historyLength` — so a `history` key would carry created-titles across
the wire if the fold ever populated it. It does not: `fold.fold_tasks` writes no
`history` field, so every `history[]` returns empty today, and the no-title
property holds by that absence, not by the reading the sentence gives.** With
`includeArtifacts=true` the acceptance text does cross in `description` and
`parts[].text`. So the leak is `id` plus the planning metadata, which is still a
draft disclosure — `metadata.aim.visibility` says `"draft"` in so many words,
and `owner` says whose. Measured on the live board: everything the board
withholds is served by `/rpc` (`rpc \ board = 71`, `board \ rpc = 0`), and all 71
carry `metadata.aim.visibility = "draft"`.

## 4.3 Row 14 and the finding behind it

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
one more than the project's own rule allows."* The three **agree on the union**;
that is not where the divergence is.

The version of this section that stood here claimed the three did not agree —
*"`a2a.py` and `bin/aim` take the union (owner **or** creator), `gate.py` takes
owner only"* — and a falsifier broke it, and the break is the finding. Measured:

- `gate.py:69-70`: `viewer not in (task.get("owner"), task.get("created_by"))` —
  **the union, spelled exactly as the other two.** `git diff 7def563 HEAD --`
  `aimboard/gate.py aimboard/const.py` is empty, so this is the tree the section
  was written against, not drift.
- `a2a.py:796`: `return viewer in (task.get("owner"), task.get("created_by"))` —
  the union. *(The line this cited, `:794`, is the stranger return three lines
  above; the union is `:796`.)*
- `bin/aim:_visible_to`: `task.get("owner") == who or task.get("created_by") ==
  who` — the union.

So the rule's three definitions agree on its verb (owner or creator), and the
falsifier's deeper claim was that the *rule* is still triplicated — the pattern
the section sells — but the specific sentence was a make-or-break mechanism for
a verdict the section had already reached, and the mechanism was wrong. What
survives: **three definitions of the same predicate still exist and nothing
checks them against each other except a comment and a test that reads a function
chain in `bin/aim`.** That is a real single-owner violation with agreement; it is
not a disagreement, and the difference is load-bearing because **the paragraph
immediately below** is where the codebase *does* disagree — it is not §4.3, and
the earlier draft pointed there. (§4.3 is the plan-file dedup, which has nothing
to do with the visibility predicate; the divergence is in the next paragraph of
this section.)

**The divergence this section missed runs the other way, and a falsifier found
it with the same tool (§4.2's).** Two `plan/plan.json` rows — `T-0018`, `T-0027`,
both `owner: codex`, `visibility: draft`, `status: dropped`, carrying **no
`channel` and no `context_id`** — behave differently on the two sides of this
exact rule. Measured on the live board in the same second:

    /api/state?as=claude-session1  ->  board sees 148, withheld 30
    /rpc?as=claude-session1         ->  150, including T-0018 and T-0027
    rpc \ board                     =  {T-0018, T-0027}

The board hides them because `gate.gate_channel` (a participant in none of the
five channels) resolves the fallback to `barrier-v0`, walled off, `owner !=
viewer` → hidden. `/rpc` serves them because `list_tasks` resolves the channel:
`by_id.get("")` is `{}`, `{}["phase"]` is `None`, and `None not in
DIVERGENCE_PHASES` is `True` at `a2a.py:792` → visible. **The board judges a
card with no channel by the *fallback channel's* phase; `/rpc` judges it by
*nothing*, which is open.** Two functions answer the same owner-based question
with opposite verdicts — exactly the shape this section claimed did not exist —
and §4.4 never mentioned it. The two rules are two definitions of *"what phase
governs a card that names no channel"* and neither one is derivable from the
other.

This is the document stating its own rule and then the code having three owners
of the rule it names, plus a fourth difference in *how each resolves a
channel-less draft*. It is the cleanest instance of the pattern in Part IV,
because the rule being broken is *the rule about rules* — and the falsifier who
reached this section found that the section's own crown example was one of the
false statements it was meant to catalogue.

## 4.5 Row 16: a missing flag silently becomes an identity [V]

`AGENTS.md:9` gives the board command verbatim, and it includes the flag:

    aimboard serve --port 8777 --refresh 0 --allow-write --as human

Drop the `--as` — natural, when you *are* the human and it looks redundant — and
`_writer()` (`aimboard/cli.py:495-505`) falls back:

    return args.viewer or (load_fabric(root, [], <today>)["channels"][0]["leader"])

`["channels"][0]` is the first element of `load_fabric`'s channel list, which is
`list_channels`'s `sorted(...)` (`aimboard/fabric.py:117`, called at `:219`) — so
it is the **first channel by name among those that have a `manifest.json`**, and
its `leader` is whatever that manifest says. Neither recency nor importance is
consulted anywhere on the path. Measured on a throwaway root with two channels,
created in *reverse* alphabetical order so that the alphabet and the creation
order disagree, and a board started with `--allow-write` and **no** `--as`:

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

**And the fallback is an unguarded index, which makes the empty root a dead board
rather than a read-only one [V].** `_writer` (`cli.py:505`) and `_viewer`
(`cli.py:493`) both end in `["channels"][0]["leader"]`, and `channels` is `[]` on
a root with no channel — so the failure is not confined to write mode. Measured
on a root holding `registry.json` and nothing else:

    $ aimboard serve --root <empty> --port 8802          # read-only, no --allow-write
    $ curl -s -w '\nHTTP %{http_code}\n' <board>/api/state
    {"error": "the server could not answer", "path": "/api/state",
     "detail": "list index out of range"}
    HTTP 500

The same 500 comes back with `--allow-write`. **The CLI renderers already guard
exactly this** — `cli.py:41-43` and `:85-87` both print `aimboard: no channels
under <root>` and return 2 — so the guard exists in the tree and `serve`, the
surface a browser reaches, is the one place it was not applied. A board for a
project that has not opened its first channel yet is a 500, not an empty page.

And the misattribution is silent in the one place a human would look: the flag's
own help text reads *"(the identity this server was started as (`--as`, default
the channel leader))"* (`cli.py:1044`), where "the channel leader" means
`channels[0].leader` and nothing on screen names it. The measured write identity
was `otherhuman`; the banner said `the channel leader`.

## 4.6 Row 17: the ledger is counted by `class`, and `class` is not a refusal field [V]

README §3 states the vocabulary in the present tense, twice:

> `class` is `barrier`\|`form`\|`unrecorded` (`_record_refusal` in `bin/aim`)

> a refusal ledger — intent, not just outcome | `channels/<ch>/ledger.jsonl`

`aimboard/api.py:231` repeats it as the machine's answer — `refusal_classes()`
returns exactly those three and is published as `refusal_classes` at `:490`,
which `web/src/panes/HelpPane.vue:344` renders as **the** token table.

Measured over **every tracked `ledger.jsonl`** — `channels/*/ledger.jsonl` *and*
`.dbg/channels/c/ledger.jsonl`, which the earlier version of this caption left
out of its glob while calling the result "every `channels/*`" — **at the
committed revision `7def563`**, derived with `git show <rev>:<path>` rather than
from a working tree, so these are numbers anyone can re-derive:

| | rows | |
|---|---|---|
| all tracked ledger rows | **363** (358 in `channels/*`, 5 in `.dbg`) | |
| `event == "refusal"` | **280** | `barrier` 152 · `form` 126 · `unrecorded` 2 |
| not a refusal, **carrying a refusal class** | **36** | `task_published_during_divergence` 35 + `channel_member_added` 1 |
| carrying `class: "record"` — **not in the vocabulary** | **33** | every `event: "push"` |
| carrying no `class` at all | 14 | 9 in `channels/*`; 5 more in `.dbg`, which predates the field |

**These numbers move, and that is the shape of the finding.** Section 4.6 has now
been measured several times, and only one of the printed triples is reproducible:
a first draft read 352 / 276 / 343; the verifier re-counted 354 / 276 / 345; at
`7def563` it is **358 / 280 / 349** in `channels/*` (363 / 280 / 354 including
`.dbg`). The head sentence of Part V carried a *third* history — "an earlier pass
printed 137 `barrier` and a later one 148" — and neither number exists at any
commit of the store: the `barrier` count over all tracked ledgers runs
**109** (`94a8e34`) → **109** (`9fc4d7d`) → **152** (`7def563`) → **155**
(`d7130fc`). 137 and 148 were working-tree readings of an uncommitted store, so
they are unrecoverable rather than merely stale — the same defect the paragraph
below names.

**The refusal class split *has* moved, and by more than a count of messages.**
`barrier` 109 → 152 is 43 rows, and a message an agent sends is not a refusal —
a refusal is a verb refusing. The structural counts are the ones that have not
moved: 36 non-refusal rows carrying a refusal class, 33 `push` rows carrying
`record`, 9 no-class rows in `channels/*`.

**The first two of those three triples are not re-derivable, and that is a
distinct defect from being stale.** `git show 9fc4d7d:channels/hello/ledger.jsonl`
holds **269** rows with **229** refusals, and at that revision only four ledgers
are tracked at all — not 352 with 276 — because the committed store lags the
working tree the numbers were read from: `channels/` is tracked by convention and
committed in release commits, so an uncommitted session's rows are in the ledger
and in none of the git objects. The third
triple *is* reproducible (`git show 7def563:...` → exactly 358 / 280 / 349,
blob-for-blob), which is why the table above carries a revision and the sentence
does not. **A number measured off a working tree and printed without its source
is not a weaker snapshot than one measured at a commit — it is a different kind
of claim**, and the two triples at this section's own head are of the first kind
while the table they introduce is of the second.

So `class` is not what makes a row a refusal, and a reader who counts either one
for the other is off by a figure that looks like a measurement. Over the whole
tree at `7def563`: `grep -c '"class": "barrier"'` returns **188**, and the
refusals *of that class* number **152** — 36 rows apart. Count every class-bearing
row as a refusal and the total is 349 against the true 280 — 69 rows apart. Both
numbers are the kind that gets quoted without a second look. (The two gaps are
themselves stable across all three measurements: 36 and 69, unchanged, while
every total around them grew.)

**The 36 rows are not noise. They are the mechanism README §3 asks for.** The
comment above the writer (`bin/aim:2373-2381`) says so outright:

> Publishing during a divergence phase is the one deliberate act that exposes a
> work item to a peer while the barrier is supposed to be closed … a leak is not
> a refusal, and it is not a `task.published` line, it is its own event class.

So the tool invented a row that is *shaped like a refusal* so the ledger could
answer "did anyone lean on the barrier", and gave it the barrier class on
purpose. The cost is that the class no longer means one thing: `class: barrier`
today covers *a request the phase refused* (152) and *an act the phase permitted
that you then performed while shut* (35) — opposite verdicts under one token.

**And the pane that exists to show them can never show them.** `BarrierPane.vue`
draws its table from `channel.refusals`, which the board fills at
`aimboard/api.py:372` out of `ch["refusals"]`, which is `fabric.py:265` —
`[r for r in ledger if r.get("event") == "refusal"]`. The 35 divergent
publications are in the ledger, carry `class: barrier`, and are filtered out
one layer below the pane. Measured on `hello` at `7def563`, the channel where all
of this lives:

| rows in `channels/hello/ledger.jsonl` | **353** | |
|---|---|---|
| `class: barrier` | **190** | caught by `grep` |
| `event: refusal` | **280** | what the pane receives |
| both — the refusals a reader calls `barrier` | **154** | the intersection |
| **neither** — non-refusals not marked `barrier` | **37** | *(this row used to read "151 — neither of the above", which is the intersection, not the complement; the complement is 353 − 190 − 280 + 154)* |

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
`class` is a field 349 of the 358 rows under `channels/*` carry at `7def563` —
363 and 349 if the `.dbg` root is counted, which §4.6 now does — and the word
for a row whose class is `barrier` is not "refusal".** *(One revision later the
live `hello` alone is 353 rows and 349 class-bearing; the figure is arithmetic
at a tree and a second, which is §4.6's finding one section down.)*

---

# Part IV-b — The objects, and what owns each

An object counts as first-class here only if it has a store, a writer, and a
**gated** reader. A field is not an object.

**The gated-reader column in this table was wrong for four of its fifteen rows,
and the error has one cause, so it is stated once rather than four times: a
reader counts as gated here only if it *does something different depending on who
is asking*.** *(The sentence read "seven" and then enumerated four — a count and
its own list, disagreeing two lines apart, which is §4.1's defect in a different
column. The four are the ones named below; no fifth or sixth instance was ever
produced by a re-derivation, so the honest number is the enumerated one.)*
`aim status`, `aim verify`, `aim card` and `aim friction`'s read
mode were all named as gates. Measured: `status` (`:3875`) and `verify` (`:4202`)
take no `--as` at all and call `resolve_actor` nowhere, so they print any
channel's phase, seals, digests and counts to anyone with filesystem access;
`card`'s own docstring (`:3914`) says *"A read: no lock, no ledger, no refusal"*
and explains that an AgentCard is the public description of an agent by design;
and `friction` (`:4042`) *is* gated — `who not in m["participants"] and kind !=
"human"` → `cls="barrier"` — which is a reader the row did not name, while naming
`verify`, which is not one. `bin/aim:56` is `PHASE_RULES = {` — a constant dict,
not a reader, so that cell is a category slip rather than a miscitation.

| object | store | writer | gated reader | verdict |
|---|---|---|---|---|
| **agent** | `registry.json` | `register` `bin/aim:959` | **none** — `card` `:3913` is ungated *by design*, and says so in its own docstring | first-class, **and its reader is deliberately open** |
| **session** | a free-text field | `register --session` | **none** | not an object |
| **channel** | `manifest.json` | `new-channel` `:1030` | **none** — `status` `:3875` takes no `--as` | first-class **and world-readable on the box** |
| **project** | — | — | — | missing; channel is nearest (`design/17` §2) |
| **task** | `channels/<ch>/tasks.jsonl` | `task new` `:1934` | **three owners**, §4.4 — and on the read side, `_visible_to` (`bin/aim:2079`) and `gate.visible_tasks` (`:52`) both gate | first-class, contested |
| **message** | `log.jsonl`, `private/`, `outbox/` | `say` `:1121`, `push` `:3288` | `inbox` `:1398`, `conversation_view` `gate.py:145` | first-class, three stores under one word |
| **receipt** | the push record's own fields | `confirm` `:3497` | `outbox` — gated on the caller's own inbox | first-class, narrow |
| **seal** | `seals/<a>.json` | `seal` `:1354` | `synthesis-input` `bin/aim:1610` (leader + synthesizer); `status`/`verify` show digests to anyone | first-class **with one real gate and two ungated readers** |
| **barrier phase** | `manifest.barrier` | `advance` `:1450` | the write side (`require_leader` `:830`, `advance`'s edge check `:1450`); the read side is `PHASE_RULES`, a **table**, not a reader — the same sentence the intro above makes about `:56`, so the two agree and a reader who saw them as contradicting twelve lines apart was reading a row that had already been corrected | first-class |
| **refusal** | `ledger.jsonl` | every `die` `:309` | **none** — `verify` is ungated and the payload's `refusals` key is unscoped (measured: **285** rows for every viewer, including a stranger) | first-class, **append-only and fully public** |
| **room** | `rooms/<id>.jsonl` | `room new` `:2822` | `visible_rooms` `gate.py:133` — **a real gate**, reached from the payload at `conversation.rooms` (`views/chat.py:44`) | first-class |
| **friction** | `friction.jsonl` | `friction --add` `:4011` | `friction` `:4042` — gated on membership, and the payload also carries it unscoped (`channels[].friction`) | first-class, narrow, **and published anyway** |
| **milestone** | `plan/plan.json` | **none** | `fold.report_data` | **read-only seed** |
| **channel kind/state** | derived | **none** | **none** | **computed, read by nothing** |
| **project** | — | — | — | **missing**, and §2.1 is what missing costs |

`rooms` is the row that moved the most: the first draft's verdict was
*"first-class in the CLI, **absent from the JSON payload**"*, and it is present —
`conversation.rooms`, built by `visible_rooms`, which is a genuine gate on draft
rooms in a sealed channel. The claim was true of the *per-channel* object (no
`rooms` key there) and false of `/api/state`, and the row did not say which one
it meant.

Measured live, one line of evidence for the "read by nothing" rows: all five
channels return `kind` and `state` nowhere in the payload, and
`grep -rn "CLAIM:\|RELEASED:"` over `bin/aim aimboard/ web/src/` is empty.

*(A note on the last row of this table and the first: `project` appears twice,
once for "missing; channel is nearest" and once for "**missing**, and §2.1 is
what missing costs". That is an editing artifact rather than a claim — two
drafts of one row, both kept. Left visible because the table is the argument and
a reader should see that it was assembled, but it is one object, not two.)*

**Fifteen rows, one shape: a rule that reads as enforced and is only written
down.** That is the same failure the barrier was built to catch, one level up —
and it is the reason the SOP has to carry the three marks rather than a list of
steps. Fourteen distinct objects behind the fifteen rows (`project` is listed
twice).

*(This sentence said "seventeen rows", and a falsifier counted the table above
it: fifteen data rows, fourteen distinct objects. "Seventeen" is the size of the
**ranked Part IV table**, which is a different table further up the document — so
the sentence had a correct number attached to the wrong object. The same mistake
appears once more in Part V, quoted there, and between them they are the reason
the last paragraph of this document is about counting rather than about design.)*

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
explained by the shape of the set than one at a time. There are **eleven**
machines in this fabric. Counted from the table's own `mark` column: **five
carry `ENFORCED` as their verdict, two are partial, and four are prose or
absent** — and the sentence and the column only agree because the split is read
at the level of the *verdict* rather than the *word*. Six rows contain the
string `ENFORCED`: rows 1, 4, 5, 6, 7 and **row 2, whose full mark is
"ENFORCED at move, absent at birth"** — a partial machine that names the
enforced half first. Counting the word gives 6/1/4; counting the verdict gives
5/2/4. Both sum to eleven and the table is the same table.
**This is the document's own recurring defect, one paragraph up from its own
census**, so it is stated rather than smoothed: a count taken from a string is
not a count taken from the thing. (An earlier pass counted eight; a reader re-deriving the list from
the code found the two enforced machines the eight missed — room publication
and push‑ack — and the event vocabulary the document already called a ninth.)

| # | machine | store | edges | who may move it | where enforced | mark |
|---|---|---|---|---|---|---|
| 1 | **phase** | `manifest.barrier.phase` | `TRANSITIONS` `bin/aim:46` — **7 edges over 6 phases**, `CLOSED` terminal | leader only (`require_leader:830`) | `advance` checks the edge (`:1450`), and the **phase-boundary guard** is `assert_barrier_defensible` (`bin/aim:556`, called `:1075`, `:1473`) — there is no `_check_rules`/`_check_keys` in the tree | **ENFORCED** |
| 2 | **task status** | `channels/<ch>/tasks.jsonl` | `TASK_FLOW` `:117` — **16 edges over 7 statuses**, `done`/`dropped` terminal | owner, or the `kind=="human"` exemption | `task move:2114` | **ENFORCED at move, absent at birth** |
| 3 | **seal** | `seals/<a>.json` | **not one-way** — measured: a second `seal` by the same agent in the same phase succeeds, overwrites the file, and writes a *second* `seal` ledger row with a different digest. Last-write-wins on disk, both writes on the ledger | any participant | quorum is **file existence** (`:1476`); nothing checks that a seal was written once | **RECORDED, not enforced — and not even one-way** |
| 4 | **membership** | `manifest.participants` | add / remove, both leader-only; both write a ledger row | leader only | `channel add/remove` (`:688`,`:735`) — real barriers, measured | **ENFORCED** |
| 5 | **task visibility** | derived | published ⇄ draft, by hand | owner / leader | three implementations that **disagree** (§4.4) | **ENFORCED, three ways** |
| 6 | **room publication** | `rooms/<rid>.json` (a `room_published` ledger row) | draft → published, **by the room's single attributed voice** — deliberately author-only, and the failure mode is that a second voice removes the author | the room's sole author, or any `kind=="human"` caller | `_load_room_or_die:2758` refuses a reader who is not the author while the phase is in `DIVERGENCE_PHASES`; `cmd_room_publish:2941` (`if kind != "human" and author and who != author`) refuses a bystander opening it | **ENFORCED — and it punishes the author** (see below) |

**Row 6 is enforced, and its enforcement has a failure mode that lands on the
wrong person.** `_room_author:2687` returns `""` when a room has more than one
attributed voice — a deliberate fail-closed choice, and its docstring says so.
But the read gate is `if who != author`, and `who` can never be `""`. So once a
room has two voices, **nobody** can read it — not the author, not the leader —
while `cmd_room_publish`'s `kind != "human"` clause lets a *human stranger* open
it, because the stranger's exemption fires before the author comparison. Measured
on a throwaway root, channel `ch`, `SEALED_DIVERGENT`, `beta`'s draft room `r1`:

    beta room list  (sole voice)   -> r1  1 msg  draft  by beta
    otherh room say (human, NOT leader, NOT participant)  -> rc 0, no refusal row
    beta room list                 -> r1  2 msgs draft  by (unknown)  [withheld from you]
    beta room publish              -> REFUSED: ... and you are not its author.
    otherh room publish            -> rc 0, published DURING SEALED_DIVERGENT

So the row's "author-or-leader" is wrong twice: the leader has no exemption at
all (the leader is not the author, so `who != author` holds), and the *human
stranger* does — `cmd_room_publish`'s own docstring, *"Author-only, plus the
leader"*, describes a rule the code does not implement. The cost today is zero:
no room exists anywhere in the live tree. The cost tomorrow is that the act of a
stranger touching a draft is what makes it unpublishable by its author, and the
ledger records no refusal for the stranger's write.
| 7 | **push delivery** | outbox (`outbox/<peer>/*.json`, fields `ts`/`claimed_at`/`acked_at`) | sent → claimed → acked | the addressee | `:3525` refuses confirming an unread push (`cls="form"`); `aim outbox` exits 4 on an un-acked demanded message | **ENFORCED** — and missing from the earlier eight |
| 8 | **channel kind/lifecycle** | derived | empty → active → dormant | nobody | computed at `aimboard/fabric.py:58`, **dropped by the payload projection** | **PROSE — computed and discarded** |
| 9 | **obligation** (who owes the leader an action) | none | — | — | 5 `@expectedFailure` tests (`tests/test_decisions_have_actions.py:249,263,276,291,313`) | **ABSENT by design, on the record** |
| 10 | **session** | a free-text field | register ⇄ register `--force`, no liveness check | any name | `bin/aim:979` reads `registry.json` and nothing else | **ABSENT** |
| 11 | **event vocabulary** | the `event` field of a **task** row in `tasks.jsonl` | unenforced; the vocabulary lives in one declared list nothing reads | any writer | declared as `TASK_EVENTS` `:127` and **read by nothing**; the fold has branches for eight names and its stray-name counter (`fold.py:120`) fires only for an event with no `created`, never for an unknown name | **PROSE — and the one writer outside the eight drops silently** |

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

The machines are not independent; almost every one is read somewhere, and two of
those reads are the load-bearing ones in the whole system:

    phase  ──read by──▶  task visibility   (DIVERGENCE_PHASES gates drafts)
           ──read by──▶  say routing      (channel_say / private_say)
           ──read by──▶  room publication (a draft in a divergence phase)
           ──read by──▶  seal acceptance  (a seal during COMMIT is a commitment)
    membership ──read by──▶ task visibility (a participant may see their drafts)
               ──read by──▶ mail gate       (a stranger is walled off)
               ──read by──▶ room publication (a non-participant is refused the room)
               ──read by──▶ seal acceptance  (only a participant may seal)
    task status ──read by──▶ obligation     (a `done` card owes nobody an action)
    push delivery ──read by──▶ session      (an ack names *which* session read it, T-0242)

Two reads I expected and did **not** find, measured rather than assumed, because
a relation that is absent is as load-bearing as one that is present: **the task
status machine does not read the phase machine.** `cmd_task_move:2114` reads
`TASK_FLOW` and nothing else — the task machine and the phase machine are
genuinely independent, so a card can be created and closed in `SEALED_DIVERGENT`
with the barrier up. And **the seal machine's only membership read is its own
`:1365`** — `_load_room_or_die`'s participant check at `:2747` is the room
machine's, not the seal's.

**The phase machine is the only one every other machine consults**, which is why
Part IV's row 1 (`fabric.py:281`) and row 7 (`bin/aim:51`, the rule-changing
edge) both cost more than they look: they are defects in the one table four
others read. Measured: `PHASE_RULES` is read at **sixteen** sites in
`bin/aim` — sixteen distinct *lines*, carrying **19 `ast.Name` Load nodes**
(`:1527`, `:1528`, `:1529` and `:1531` are four reads on four adjacent lines, and
`:3883`/`:3890` are two more) — `:142`, `:152`, `:859`, `:1267`, `:1402`,
`:1527`, `:1528`, `:1529`, `:1531`, `:1548`, `:1553`, `:1566`, `:1575`, `:3883`,
`:3890`, `:4134`. They sit in **eight** functions (`_next_opener`, `gate`,
`cmd_say`, `cmd_inbox`, `cmd_advance` — eight of the sixteen — `cmd_status`,
`cmd_search`, and module scope at `:152`). The definition at `:56` is excluded;
a count that does not subtract it reports **seventeen lines**, and one that
counts nodes rather than lines reports **twenty**.
*(A falsifier corrected this line three ways and the correction is worth keeping
because it is the section's own theme: "counted as `ast.Name` nodes" is not what
16 is — 16 is lines, 19 is Load nodes, 20 is all nodes; 16 is *not* the function
count, which is 8; and the "naive walk reports seventeen" claim is true of lines
and false of nodes. The numbers I had were each attached to the wrong noun.)*
A count of the *text*
gives a different number
every way you slice it — 24 lines mention it, 5 of those in comments and 2 in
docstrings — which is why the count here is of evaluations and not of
occurrences, and the `channel_say` half of it is deliberately
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
| the phase *access* table | `PHASE_RULES`' `read_others`/`channel_say`/`private_say`, `web/src/concepts.js:331` (`PHASE_ACCESS`, same 6 rows, keys renamed `read`/`say`/`private`) | **yes** (verified row by row) |
| terminal set | `TASK_FLOW`'s two empty edges, `const.TERMINAL` (`{done, dropped}`) | **yes** — and the `done/doing/review` colour map in `const.STATUS_COLOR` carries no terminality, so it is not a third copy |

**They all agree, and that is the finding, not the exoneration.** The table above
is seven facts, each written down **two to four times**, in two languages, and
this repo already has the receipt for what happens when one of them lands in only
some of the copies. `TASK_EVENTS` (`bin/aim:127`, the eight event names a card may
carry) is declared and **read by nothing** — `grep TASK_EVENTS` finds the
declaration and no reader — so the store's `tasks.jsonl` carries exactly those
eight and never a stray one (`created 100, moved 249, commented 94, published 35,
assigned 15, dropped 2, linked 1, retracted 1` — 497 rows at HEAD; the vector the
earlier draft printed, `created 97 … commented 91 … dropped 1`, matches **no
single revision**: `created` is 97 at `5529368` and 98/99/100 after, `commented`
is 87/92/93/94 and never 91, so it was assembled from more than one read), while
`ledger.jsonl` next to it
carries `seal`, `phase`, `push`, `refusal`,
`task_published_during_divergence`, `channel_member_added/removed/noop` and
`friction` under the same word *event*. And a **card's** writer is already outside
the eight: `cmd_task_edit` (`bin/aim:2255`, wired `:4613`) emits `"event":
"edited"` at `:2330` into **`tasks.jsonl` itself**, absent from `TASK_EVENTS`,
`aimboard/fold.py` and every renderer — the live store shows only the eight
because no `task edit` has run, which is luck, not mechanism.

**And the drop is silent, which is worse than the name being unknown.** Measured
on a throwaway root: `task edit --priority high` writes the row, prints
`T-0001: priority normal -> high`, and the fold returns
**`tasks_unknown_events = 0` with `priority` still `normal`**. Two independent
silences, and the second is the interesting one — `unknown` (`fold.py:120`) is
incremented only for an event whose **`created` was never seen**, not for a name
the fold has no branch for, and every name outside the eight arrives *after* a
`created` the fold did read. So the fabric has a counter for stray events and
that counter cannot fire on the one stray event the tool can produce. I added an
entry named `totally_made_up` to the same store to check the mechanism rather
than assume it, and it did not move either. The verb reports success, the board
does not move, and the store's own alarm stays at zero: a rule that exists in
prose (`TASK_EVENTS`) and in a reading (`unknown`) and in neither machine.

Scanning every literal `"event": "..."` in `bin/aim` and matching it against the
fold's branches: eighteen names are written *not* into `tasks.jsonl` — `phase`,
`seal`, `push`, `refusal`, `concession`, `friction`, `room_created`,
`room_published`, `workspace_cleared`, `channel_member_*`,
`task_published_during_divergence`, the three `doorbell_*` and `deleted` — and
those are *ledger* events, correctly outside a task fold. **`edited` is the only
one written into `tasks.jsonl` that the fold has no branch for.** That is the
whole defect, and it is one branch.

**Two of the eleven cannot be seen from the page** — and they are not the same
kind of invisible. Row 8, the channel lifecycle, is computed on every
`load_fabric` and dropped by `aimboard/api.py:363`'s projection, which keeps
`id, topic, phase, round, leader, synthesizer, participants, history, sealed,
chain, tasks_recorded, tasks_store_exists, tasks_unknown_events, refusals,
concessions, friction` and **not** `kind`, `state`, `traffic`, `last_activity` or
`idle_days`. Verified against the live payload: all five channels have none of
those keys. So the answer to *"is this channel a real project or scratch, and is
it alive"* exists in the fold, is computed on every page load, and reaches no
reader — not the JSON, not the CLI (`aim status --channel dev` prints the phase,
the leader, the rules and the participants, and no lifecycle), and not the page.
And so does the event vocabulary's *absence of a reader* — no pane answers the
question "did an `edited` ever land", because no pane would know the name.

## IV-c.2 The relations between the categories

*范畴的关系* — the objects and their cardinalities, measured:

    agent  1 ──n  session     (a name may be re-registered with --force; no liveness check)
    agent  n ──n  channel     (participation; a channel may hold zero participants)
    channel 1 ──1  project    (there is no project object; §2.1 is what that costs)
    channel 1 ──n  task       (ids are per-channel; the *board* keys them per-root — the collision)
    task   1 ──1  owner       (a **field**, `str`, on the card — nullable: an unowned card
                               short-circuits two actor rules; measured, 247/247 owner values are strings)
    task   1 ──n  event       (tasks.jsonl is an event log, folded on read)
    agent  1 ──1  seal        (a seal is per **participant per channel**, not per task:
                               channels/hello/seals/{claude-session1,codex,codex-orangement}.json)
    message n ──n  channel    (three stores, and the copy is worse than the word: `say`
                               writes `log.jsonl` + `private/{agent}.jsonl`, `push` writes
                               `outbox/{peer}/*.json`, and only the outbox third carries its
                               own `channel` — the other two are filed by directory)
    refusal n ──1  action     (every die() **with a channel set**; a channel-less verb writes
                               none — `_record_refusal:280` returns early when `_CTX["channel"]`
                               is falsy. A refusal is logged with `agent` already set and
                               `action` spellable — measured: `say` before the channel is
                               resolved writes `action=say, agent=`, after it writes
                               `agent=ghost` — so the dropped fault is naming, not context)
                               (the class on a *refusal* row is `barrier|form|unrecorded`;
                               `class` is not a refusal field — 36 non-refusal rows carry
                               `class: "barrier"` on purpose and 33 `push` rows carry
                               `class: "record"`, which is in no vocabulary)

**Two of these are lossy in the direction a reader would not guess.** `channel
n─n task` loses work silently (§2.1: an id space per channel, merged per root, so
the second project's copy is gone and the survivor is chosen by `sorted()`). And
`task 1─n event` is lossy **on the write side too, not only the read side** — the
stronger version of what this paragraph used to claim. The read side keeps two of
the kinds (`created`, `moved→done`) so the five newest records in the live store
appear on no card; that was measured earlier and it is the tail violation. But
the *fold* — the layer under the renderer — also drops a kind without saying so,
and unlike the renderer it has a counter that was built to notice: `task edit`
writes `edited` (`bin/aim:2330`) into `tasks.jsonl`, the fold has no branch for
it, and `tasks_unknown_events` stays **0** because that counter fires on a
missing `created` and not on an unknown name (IV-c.1 has the measurement). So
`task 1─n event` is not an honest one-to-many with a stated consequence: it is a
relation where **one writer and one reader disagree and neither reports it.**

**The rest are honest one-to-manys with the consequence stated somewhere.** A
nullable owner is what makes two actor rules short-circuit; a per-channel seal is
why the quorum is per participant and not per card; `n─1 action` is why the
refusal class, and not the action, is the thing a reader can count on.

---

# Part V — The judgement

**The core is sound and the ceremony around it is not.** Three things are real:
the phase gate refuses and records refusals (**152 `barrier` + 126 `form` + 2
`unrecorded` = 280 refusal rows** at the revisions `7def563` and `d7130fc`, each
with a reason — but see the paragraph after next: the *class split* is not stable
across commits, and the history this sentence used to carry (137 `barrier`, then
148) is not recoverable at any commit at all); the seal
chain detects tampering after the fact; and
the task-actor rules stop a bystander from submitting another's card **while the
barrier is closed** — measured: a claude non-owner got `REFUSED: 'T-0001' is
owned by 'a' and you are not its owner` in `SEALED_DIVERGENT`. That qualifier is
load-bearing and was missing here: §1.4 records the same actor moving another's
owned card to `done` in `CROSS_EXAMINE` with rc 0, and the *real* second half of
that pair is `cmd_task_new`'s missing membership test — a card is born with no
owner and neither `who not in m["participants"]` nor any other membership check
runs on the create path, so a non-participant can create a card on a channel they
are not in (measured: rc 0). *(This named `insert_actor`, which exists nowhere in
the tree — the real claims are the create-path membership hole and the unowned
short-circuit, both reproduced.)* **The rule is real and it is phase-conditional**,
which is the whole design — the actor rules hold where the barrier holds, and both end
at the same phase boundary. Stated without the qualifier, the sentence claims a
universal the document's own §1.4 falsifies.

**But a count is not a weight, and these 280 rows are not what I read them as.**
Every sentence above this one counted refusals. Classifying them by *what each
row says it refused* — its own `action` field plus its own `reason`, never the
`class` — splits them very differently. By action and class together, at the
`7def563` tree the rest of this document is measured at:

| `action` | rows | `form` | `unrecorded` | `barrier` |
|---|---|---|---|---|
| `task move` | 197 | 112 | 2 | 83 |
| `task list` | 52 | 0 | 0 | 52 |
| `task new` | 11 | 5 | 0 | 6 |
| `advance` | 4 | 2 | 0 | 2 |
| `say` | 4 | 2 | 0 | 2 |
| `friction` | 3 | 3 | 0 | 0 |
| `inbox` | 2 | 1 | 0 | 1 |
| `tension` | 2 | 0 | 0 | 2 |
| `task comment` | 2 | 1 | 0 | 1 |
| `task publish` | 2 | 0 | 0 | 2 |
| `task claim` | 1 | 0 | 0 | 1 |
| **total** | **280** | **126** | **2** | **152** |

**And the same table five rows later, which is the point of §4.6.** This table
said *"Re-derived at HEAD"* and printed the `7def563` numbers — a falsifier caught
it by re-deriving, and the delta is the finding the section is about, committed
against the section. Re-derived again at HEAD, on the working tree, **five** rows
have moved since `7def563`, and one of them is a whole `action` the cross-tab had
no row for:

| `action` | rows | `form` | `unrecorded` | `barrier` |
|---|---|---|---|---|
| `task move` | 197 | 112 | 2 | 83 |
| `task list` | **53** | 0 | 0 | **53** |
| `task new` | 11 | 5 | 0 | 6 |
| `say` | **6** | 2 | 0 | **4** |
| `advance` | 4 | 2 | 0 | 2 |
| `friction` | 3 | 3 | 0 | 0 |
| `inbox` | 2 | 1 | 0 | 1 |
| `tension` | 2 | 0 | 0 | 2 |
| `task comment` | 2 | 1 | 0 | 1 |
| `task publish` | 2 | 0 | 0 | 2 |
| **`search`** | **2** | **2** | 0 | 0 |
| `task claim` | 1 | 0 | 0 | 1 |
| **total** | **285** | **128** | **2** | **155** |

The five new rows are all this document's own author's, and only one is a
divergence-phase refusal at all: two `search` refusals (an action the table above
had no row for, which is the honest reason to re-derive rather than add the
delta by hand), a `task list` draft gate, a `say --kind report` refused as *"only
meaningful in CROSS_EXAMINE"*, and a `say --kind note` refused as *"channel_say
is False"*. So the `barrier` column grew by 3 and the `form` column by 2 across
the five, and the honest reading of *"152"* is that it was a working-tree number
at one second, not a property of the machine. **The number in the
sentence is a measurement at a tree and a second; the number in the table is
too; and a section about how counts move printed one without the other.**

**So of the 152 rows classed `barrier`, 134 are the withholding family and 18
are something else entirely.** The split, by the reason text the tool itself
wrote:

| what the row refused | rows | is it about one agent seeing another's work? |
|---|---|---|
| a peer's card in a divergence phase (the **draft gate**) | **132** — 76 `task move`, 52 `task list`, 2 `task publish`, 1 `task claim`, 1 `task comment` | **yes**, and it is the same mechanism as the barrier: a draft is a position wearing a task title |
| `channel_say is False` — public speech while the phase is closed | **2** | **yes** — this is the barrier proper, refusing a write across it |
| the owner rule on `task move` (submit / approve) | **7** | no — a card's owner, not a phase |
| `task new` publishing while the channel is closed | **6** | no — a creation rule |
| `advance`: *"may not advance the barrier"*, a non-leader | **2** | no — a leadership check that happens to say "barrier" |
| the tension report's reader gate (leader + synthesizer only) | **2** | no — a reader gate on a report, not on a position |
| `inbox`: unknown agent | **1** | no — a form error wearing the wrong class |

**Two of the 152 rows are the barrier the whole system exists for; 132 more are
the same withholding mechanism one step off; and 18 are not about the barrier at
all.** The class token and the thing it names are 150 rows apart on the strictest
reading and 18 apart on the loosest, which is a wider gap than §4.6's 36, in the
same direction and for the same cause.

The table here used to read *"of the 152 rows classed `barrier`, five are the
barrier … the other 147 are the draft gate (128), the owner and publish rules
(16) and `advance` (2)"*, and **128 + 16 + 2 = 146, not 147**. The falsifier
caught the arithmetic, and chasing it caught the classification underneath: the
128 was a keyword count of a range that is really 132, and the "five" was a
hand-picked subset of a family that is 134. Both errors have the same shape as
the one §4.6 records — **a number derived by matching words, and then
arithmetic performed on the number instead of on the thing.**

**And the deeper fact, which no count reaches:** `read_others` is `True` only in
`CROSS_EXAMINE`, `RESOLVE` and `CLOSED`, and **no channel that ever held work has
entered one of those phases.** Eight transitions across the five channels in
`channels/`, in two days of real use, all of them into `SEALED_DIVERGENT` (5),
`COMMIT` (2) or `SYNTHESIS` (1). Every barrier refusal in the table above was
recorded with the barrier *closed*, refusing an act that would have crossed it
early.

*(The scope is stated because the earlier version of this sentence said "no
channel in this repo", and a falsifier found one that had: **`.dbg/channels/c`
is tracked in this repository and sits at `CROSS_EXAMINE`, round 1** — three
phase rows, all written in the same second by `h`. The earlier version also
called it "a debug root with no card and no message in it", and that is false in
the direction that matters: the root holds **two public messages** (`b` asking
*"Name the observation that would have made you drop your first claim."*, `a`
answering with a second draft), two private-log rows and two seals — a two-turn
agent-to-agent contact, in the one phase where `read_others` is true. The barrier
has been crossed, by a script, on a root nobody read, and the contact is real
even though the cards are not. That is a weaker claim about the five real
channels and a sharper one about the census: **the `channels/` glob was never
stated, and the thing it excluded was tracked and visible in every `git show`.**
The census below counts `channels/*`; the repository holds **six** channel
directories.)*

That is the honest version of "the phase gate is real": **the lock is real, there
are 280 recorded attempts to turn it, and the door has never been opened on a
channel with work in it.** The mechanism this repo spent its effort on has never
been exercised on the thing it was built for — agent-to-agent contact after a
committed position — because the run never got past the phase where contact is
what the fabric forbids. What the 280 rows measure is the *pre-barrier*
discipline, which is the half of the design
`design/00` calls contact control. What they cannot measure is contamination
control, which `design/00` says outright is "not enforceable, and arguably not
even measurable", and which is the half nobody has a test for.

*(The first version of this table was built by keyword-matching the reason text
and had two errors: it counted 21 "card id does not exist" against a true 20 and
20 owner/other rows against a true 7, because `illegal transition` is emitted by
**two** verbs — `cmd_advance:1464` speaks in phase names, `cmd_task_move:2116`
speaks in card ids — and a substring test cannot tell them apart. Counting by the
ledger's own `action` field is what makes the split decidable. Every refusal die()
carries `action`; the mapping from that field to a verb is the tool's, not a
reader's judgement.)*

**What is not real is the layer that makes them mean something.** A quorum that a
hand-written file satisfies, a claims schema nothing validates, an exemption any
name can claim, a terminal status a card can be born into, an id space that
merges two projects into one, and an end state nothing asks for — none of these
is a missing feature. Each is a rule that exists in prose and in the readings and
not in the machine.

**Row 11 is the master key.** The others are separate failures of separate
mechanisms; that one is a single condition — `kind == "human"`, declared by the
agent it describes — spelled at the gates that consult a membership test, in the
tool and in the board (§4.1 counts them: 31 comparisons, 24 functions, 1 that
also checks the name, and **seven barrier-path gates that carry no exemption at
all**). Fixing it first is not a preference: it is what makes the other sixteen
measurable, because until it lands, any measurement of "who could reach this" has
an actor who can reach everything a participant could, without being one, and who
left no refusal row while doing it.

**The single highest-value fix after that is not a feature: it is to make the
three marks the contract.** Every step in Parts I and II already carries one.
Where a step reads **PROSE** and the leader believes it is **ENFORCED**, that is
the defect — and there are **four** such marks above, each with a line number and
a command you can re-run: §1.1 step 1 (the `PATH` install), §1.1 step 8 (the seal
that the tool enforces but whose *meaning* nothing reads), and machines 8 and 11
in Part IV-c (the channel lifecycle, computed and dropped by the payload
projection; the event vocabulary, declared in `TASK_EVENTS` and read by nobody).

*(This sentence said "seventeen", and a falsifier counted the tokens: four uses
of `PROSE` as a mark, one of which is the hybrid in step 8, and two of which are
machine rows rather than steps. "Seventeen" was the count of the **ranked Part IV
table**, carried into a sentence about a different table — the same
table-drift that produced "Seventeen rows" over the 15-row objects table in
Part IV-b. The document has two tables that count things and one habit of
quoting the wrong one.)*

**What has to be decided before an end-of-life SOP can be written:** who, or what
recorded evidence, declares a channel finished rather than merely quiet. `CLOSED`
is reachable and nothing asks for it; `README.md` §8 Q4 states the same question
and leaves it open. Until that is answered, the honest SOP ends with *"the
leader decides, and nothing will ask them."*

---

# Part VI — The architecture and the design philosophy: what is actually built, and what it believes

*The leader's list was: 架构、设计哲学、状态机、范畴的关系. The state machines and the
categories are Parts IV-c.1 and IV-c.2. This is the other half — what the shape
of the code is, and what the design says it is for — and it is here rather than
in Part IV because it is a judgement about the whole, not a defect in a row.*

## 6.1 The five layers the design names, and the three that exist

`design/08-solution-shape.md` is the note that answers the leader's own
instruction (*"最终整个项目需要是一整套解决方案：Skills、MCP、tools、services。web
dashboard"*), and it names five layers with a one-line owner for each. Measured
against the tree:

| layer, as `design/08` names it | the directory | what is actually there |
|---|---|---|
| `skills/` — "how an agent knows to use any of this" | **exists**, 2 files | `skills/aim/SKILL.md` and `skills/aim/install.sh` — and `install.sh` answers the note's own complaint, which this row carried forward as a measurement (see below) |
| `protocols/` — "A2A and MCP (adapters, no rules)" | **absent** | the code is `aimboard/a2a.py` (1480 lines) and `aimboard/mcp.py` (204), and both live **inside** what the note calls the services layer |
| `tools/` — "`aim` — the verbs, one implementation" | **absent** | `bin/aim`, 4911 lines, at the repo root |
| `services/` — "the fabric: log, ledger, task store, rooms, gate" | **absent** | `aimboard/`, 25 Python modules |
| `dashboard/` — "the human's view" | **absent** | `web/src`, 40 files and 10833 lines (the `.vue` + `.js` subset; `web/src` whole is 41 files / 11463, and `web/` is 211 files), plus `aimboard/cli.py` as its server |

**The `skills/` row was the one row here doing the thing this document keeps
catching.** It said *"`AGENTS.md` and `skills/aim/SKILL.md`. The note's own
verdict — *'half'* — is generous: neither is installable, versioned or shared."*
Measured:

- The two files in `skills/` are `SKILL.md` and **`install.sh`**. `AGENTS.md` is
  at the repo root and always has been.
- `install.sh` is tracked at this document's own commit
  (`git cat-file -e 4bcb0cb:skills/aim/install.sh` → present), and it does all
  three of the things the sentence says are missing: `--print-version` prints
  the tree revision and both sha256s; a real run puts byte-identical `SKILL.md`
  into `$CLAUDE_HOME/skills/aim/` and `$CODEX_HOME/skills/aim/` from the one
  source and symlinks `aim`/`aimboard` onto PATH; `--uninstall` removes exactly
  those two. Its header names this section's complaint **verbatim** — *"It is not
  installable … not versioned with the tool … and it is written for a reader who
  is already inside the repo"*. That is `design/08 §2`'s own prose about the
  state *before* the script, quoted in this table as a description of the state
  after it.


**So the five-layer picture is a design that was never given the shape it
describes** — and the interesting question is not that the directories are
missing, because a layer is a *rule-ownership boundary* and not a folder. Every
one of the note's ownership claims is measurable, and it is measurable **because**
nothing was split into the directories it named:

- **"The write discipline lives in `bin/aim` and nowhere else."** Measured:
  `grep -rn "append_chained\|def write" aimboard/` returns **0**. Not one module
  under `aimboard/` opens a store for writing. The rule holds, exactly and
  without exception, across 5953 lines of Python that were never supposed to be
  in this layer.
- **"The gate lives in `aimboard/gate.py` and nowhere else."** This one **does
  not hold**, and §4.4 measures the same failure in three places; `gate.py` is
  where the rule is *stated*, and it is re-implemented in `bin/aim:_visible_to`
  and in `aimboard/a2a.py:task_visible`.
- **"Every adapter in `protocols/` either calls `bin/aim` or returns
  `UnsupportedOperation`, and there is no third option."** Measured, and the two
  adapters answer differently: `aimboard/mcp.py` is a **wrapper that shells out** —
  four `subprocess` sites and its own description string, *"Thin MCP wrapper
  around the aim CLI; `bin/aim` remains the only writer."* `aimboard/a2a.py` is
  **not** a wrapper: zero `subprocess`, and it re-implements the visibility rule
  (`task_visible`), the serialiser and the gate rather than calling `bin/aim`.

**The adapter rule is therefore true of one adapter and false of the other, and
the one that violates it is the one that is 7× larger.** That is the architecture
finding this SOP would have missed by reading the design note instead of the
tree: the layer that was supposed to be *"throwaway boundary syntax"* is where a
second copy of the access rule got written, and the layer that was supposed to
own the rule is the one that shells out to a CLI.

The real layering, by weight:

    bin/aim      4911 lines    the verbs, the write discipline, the fold (again)
    aimboard/    5953 lines    the read surfaces: fabric, fold, gate, api, cli, a2a, mcp
    web/src/    10833 lines    the dashboard
    tests/       9531 lines    the suites

## 6.2 The design philosophy, in its own words, and what it does not reach

`design/00-problem.md` states the thesis the whole system is built on, and it is
a distinction the SOP had never quoted until Part V:

> contact control — mechanically enforceable.
> contamination control — *"Not enforceable, and arguably not even measurable."*

That is the honest core of the design: **the thing this fabric can do is decide
who may talk to whom, and the thing it cannot do is decide whose judgement was
formed independently.** The barrier, the phases, the seals and the ledger are all
contact control. The thing the barrier exists to *protect* — independent
positions, formed before anyone saw anyone else's reasoning — is contamination
control, and the design says outright that it is not enforceable.

**Measured against that, the whole system is doing the half it can do, and doing
it well, on a case that never arrived.** Part V records the arithmetic: 280
recorded refusals, 150 of them concerning a peer's draft in a divergence phase,
and **in `channels/` not one channel that held work has ever entered a phase
where the barrier is open** — five channels, every one of them `≤ COMMIT` or
at `SYNTHESIS`, three of the four that hold any tasks (`barrier-v0`,
`hello`, `dev`) at the divergence phases `SEALED_DIVERGENT`/`COMMIT`/`SYNTHESIS`,
and only one (`hello`) at `COMMIT` with a substantial store (491 task rows).
`.dbg/channels/c` is tracked, sits at `CROSS_EXAMINE`, and holds two public
cross-examination messages with `echo_ratio: 0.0` — but **no `tasks.jsonl`**,
so by §1.5's own definition of "held work" it is not a counter-example. So
the contact-control machinery has been exercised 280 times as *refusal* on a
channel with work in it and zero times as *permission* on a channel with work
in it; the case it was built for has never arrived. What that means is not
that the fabric is broken. It means the measured evidence is all pre-barrier,
and the design's own sentence about the other half — not enforceable, arguably
not measurable — is the reason no amount of further measurement here will
close the gap.

This is the part of the leader's question (*"到底如何开始，如何progress，如何人机交互，
如何结束"*) that the code cannot answer, and the SOP should say so plainly rather
than imply it with a census: **the start is `aim init`; progress is the phase
machine; the human's interaction is a read-only dashboard by default with an
opt-in `--allow-write` write path to seven allowlisted commands (four of them
requiring the leader, one of those seven being `advance`); and the end is a
phase (`CLOSED`) that the tool makes reachable and nothing ever asks for.**
Four of those five are machine-enforced. The one that is not is *when to stop*,
and no amount of contact control can make it so. *(The earlier bullet said
"the human's interaction is a read-only dashboard and five leader-only
verbs"; `aim say` enumerates five verbs and `aim channel` four — the count
"five" was a guess, and with `--allow-write` the dashboard is not strictly
read-only — `cli.py:440`'s `writable = {"say", "push", "confirm", "task",
"advance", "request-advance", "reveal"}` is the truth of the sentence, and
`advance` is gated by `require_leader` in `bin/aim` but reachable from the
browser with the flag turned on. The check belongs in the allowlist comment,
not on the wire.)*

## 6.3 What the architecture gets right, stated as measurements

Three structural decisions in this tree are load-bearing and none of them is
stated anywhere as a rule:

1. **The task store is an append-only event log with a fold on read.** `fold_tasks`
   (`aimboard/fold.py:61`) has no writer, recomputes board state from
   `tasks.jsonl` on every load, and has a retraction branch (`:104-121`) rather
   than a delete path. Measured: the *dashboard's* copy of the fold opens no
   store for writing (see §6.1's zero-writer finding), and there is no board
   file anywhere that a renderer mutates. The strongest form of the claim needs
   one caveat: `bin/aim:1666` defines a **second** `fold_tasks`, so "the store is
   a fold on read" is true of two implementations, not of one — and no file in
   the tree is *written* by either. The `edited` event (§IV-c, and T-0246) is a
   whole-**record** bug and not a whole-board one: the fold has no branch for
   that name, so the one card that emits it loses that one field silently while
   its `created`/`moved` branches still fire. (The earlier sentence said
   "whole-board"; the measured effect is one card, and the sentence reached past
   its own evidence.)
2. **The ledger is hash-chained, and the check is a reader, not a writer.**
   `aim verify` walks `prev`/`hash` on every chained file and returns rc 1 on a
   broken chain — measured in §1.2, where a hand-written seal passes the advance
   and is caught afterwards by `verify` (`TAMPER ledger.jsonl:6 content does not
   match its hash`, `chain BROKEN`). It is **not the only** mechanism in this
   repo that *detects* rather than *prevents*; at least four others read and
   never write: `fold.drift` (`aimboard/fold.py:284`, *"Where the plan and the
   store disagree"*); the task-id allocator (`bin/aim:1810-1860`) which calls it
   and so *avoids* the colliding id rather than protecting it; `fabric`'s
   `tasks_unknown_events` (`aimboard/fabric.py:269`) — the count the board
   publishes and, per §4.6, nothing renders; and `bin/aim-doctor`, whose own
   header says the tripwire lives outside the tool it watches. Plus the
   conformance check at `tests/test_a2a_conformance.py:438`, which parses
   `_visible_to` out of `bin/aim`'s source and compares it against
   `a2a.TASK_VISIBILITY_RULE` — the crude check that would have caught the
   disagreement below. The sentence was reaching for "the reader is the only
   *chain* check", which is closer to true and still not what it said.
3. **One writer, many readers, and *one* reader is wrong where the others are
   right.** §6.1's zero-writer finding is the positive half, and it holds.
   The negative half is bigger than §4.4 stated and simpler than it implied:
   the copies do not disagree about the *predicate* — all three spell
   owner-or-creator — and they do not disagree about T-0041's stranger case.
   **They disagree about which phase governs a card that names no channel, and
   the disagreement is not symmetric.** §4.4 measured it on the live board as
   `rpc \ board = {T-0018, T-0027}` — a delta of two. Re-measured at this tree
   against the fabric directly, `gate.visible_tasks`'s hidden count against
   `a2a.hidden_count`'s, over the same 180 tasks:

   | viewer | `gate.visible_tasks` hidden | `a2a.hidden_count` | delta |
   |---|---|---|---|
   | `a` (participant of nothing) | 73 | **0** | 73 |
   | `codex` | 49 | **36** | 13 |
   | `claude-session1` | 32 | **30** | 2 |
   | `human` | 0 | 0 | 0 |

   and end-to-end on a throwaway root with one draft: `GET /api/state?as=c`
   (a registered stranger) → `tasks []`, `withheld_tasks 1`; `POST /rpc?as=c`
   `ListTasks` → `["T-0001"]`. **So the board is not the conservative half and
   `/rpc` is not the leaky one — `/rpc` is the generous one, and the board
   withholds strictly more, for every viewer that is not the leader.** The two
   differ where a card carries no channel: `gate.visible_tasks` resolves it to
   `gate.gate_channel`'s fallback (a real channel's phase), and `list_tasks`
   resolves `by_id.get("")` to `{}`, whose `phase` is `None`, and
   `None not in DIVERGENCE_PHASES` is `True` at `a2a.py:792`. Note that
   `hidden_count` is a pure function over dicts: it asks `task_visible` with
   `by_id.get(task["context_id"] or task["channel"] or "", {})`, so it inherits
   the `{}` default and returns **0** where the board returns 73.
   `hidden_count`'s own docstring says it exists "so the two halves of D17 can be
   asserted against the *same* rule instead of against two rules that happen to
   agree today" — and it is not called by anything in the tree.


## 6.4 The judgement this part adds

**The architecture is a two-verb system wearing a five-layer diagram, and the
diagram is why the rules drifted.** Everything that must be true for the fabric
to work is enforced in `bin/aim`; everything that is *convenient* is a read in
`aimboard/` — *almost*: the dashboard's `POST /api/command` can run `advance`
and `task` from a browser when the server was started with `--allow-write`
(`cli.py:440`, see §6.2), so "convenient is a read" is the design intent and
not the reachable surface. And the five-layer diagram is not a false
description of intent — it is a description of a refactor that did not happen.

The causal sentence this section used to end on — *the access rule crossed from
the writer's layer into a reader's layer and got copied there, and the cost is
exactly §4.4* — is the part the falsifier corrected, and the correction is a
real one. What §4.4 actually measures is not a *copied predicate* but two
**call sites** resolving the same question differently: every copy spells
owner-or-creator the same way; the disagreement is `gate.gate_channel`'s
fallback (a real channel declares the barring phase) against `list_tasks`'s
`by_id.get("") → {}` (no channel means no phase means open), for a card that
names no channel. §4.4 named `T-0018`/`T-0027`; §6.3(3) re-measured it as a
73/0 gap for a stranger on this same root. It is a difference in **one line of
argument**, not a second copy of the rule — which is why §4.4's "one rule, one
owner" verdict needs to be restated as "one rule, three call sites, one gap".
The diagram's cost is real and it is not quite the cost this section used to
name.

**The design philosophy is sound and its reach is stated correctly by its own
author.** `design/00` says contamination control is not enforceable, and the
measurement in Part V confirms it from the other side: the machinery built to
protect independent judgement has never been asked to permit anything, so what it
has proven is that it can say *no*. That is a real result and it is the honest
one to end on — **the part of this system that is checkable is checked, and the
part that matters most is the part its own design says cannot be.**

---