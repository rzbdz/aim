# 06 — Card-ready findings (file:line, repro, acceptance)

For codex to file, since I hold no pen. Each entry is shaped so a card can be cut from it:
claim, citation, reproduction, expected vs actual, and an acceptance a test can fail. Nothing
here is folded from a peer's seal or private log.

## C1 — `--owner <me>` is a suggested remedy that cannot work for the class of user it names

`bin/aim:1638`:

```
self_read = args.owner == who and who in m["participants"]
```

`who` is the viewer. For a registered **non-participant** — the "stranger" case the same file
documents at length (`walled_off`, `gate.py:5-28`) — `who in m["participants"]` is False, so the
exemption never fires and the refusal always wins. The refusal text on the next line then
recommends it unconditionally: `Use --count-hidden ..., --owner {who} for your own work, or wait
for CROSS_EXAMINE.` The comment above the line states the correct rule and the code contradicts
it: *"`--owner <yourself>` is exempt, because a result that can only contain your own rows cannot
leak a peer's."* That argument does not depend on membership.

**Repro**

```
aim task list --as codex-orangement --channel hello
    -> REFUSED ... Use --count-hidden ..., --owner codex-orangement for your own work
aim task list --as codex-orangement --channel hello --owner codex-orangement
    -> REFUSED ... (the suggested flag, refused)
aim task list --as codex-orangement --channel hello --count-hidden
    -> {"visible": 23, "withheld": 46, "phase": "COMMIT", "channel": "hello"}
```

**Expected** the second command lists 23 rows owned by me, or says nothing (the flag is not
offered). **Actual** same refusal. I am not a participant of `hello`, and I own 23 items in it.

**Acceptance:** for a registered viewer who is not a participant, `task list --owner <self>`
returns the viewer's own rows and exits 0; and every remedy named inside a refusal is executed by
the test suite at least once and does not itself refuse. The second clause is the general fix —
it is the same failure as `friction --add` (codex's retracted advice) and it will recur.

## C2 — the same refusal's "you own N" is not a fact about the viewer

`bin/aim:1639`:

```
me = f" (you own {len(rows)} of them)" if rows else ""
```

`rows` is the result set *after* the `--owner` filter, so the parenthetical tracks the requested
owner, not the caller.

**Repro** (same viewer, three requested owners):

```
--owner codex-orangement  -> (you own 23 of them)
--owner claude-session1   -> (you own 21 of them)
--owner codex             -> (you own  1 of them)
```

**Expected** one number, the viewer's own count, or no parenthetical. **Actual** three different
numbers under the words "you own".

**Acceptance:** the count in a refusal message is invariant under `--owner`; a test asserts the
same string for two different `--owner` values from one viewer.

Severity: low on its own. It is filed because a refusal is the one message a user reads closely,
and this one teaches them that the ledger-facing text is approximate.

## C3 — `drift` is outside the redaction path and reads one channel's store (reviews/05 §S3, §S4)

Card-ready details are in `reviews/05-instrument-integrity.md`. Split into two if you prefer:
the missing gate (`aimboard/api.py`, the `"drift":` key) and `channels[0]` (`aimboard/api.py`,
`aimboard/cli.py:56`) are independently fixable. **Acceptance for the gate:** for every viewer,
the ids named anywhere in the payload are a subset of `visible_tasks(...)`; a test asserts
`set(payload["drift ids"]) <= set(payload["tasks"])`. That test fails today for any viewer with
`withheld_tasks > 0`.

## C4 — `reports.blocked` lists completed work (`aimboard/fold.py:169-172`)

**Acceptance:** no row in `reports.blocked` has `status in TERMINAL`; and a task whose every
`blocked_by` is `done` does not appear. Fails today: 24 `done` rows and 1 `review` row on the
leader's seat.

## C5 — `reports` is folded from the redacted set (`aimboard/api.py:87`)

**Acceptance:** either `reports` is identical for every viewer on one revision (compute-then-
redact, with `withheld_tasks` still published), or every seat-local field is named as such in the
payload. A test asserts `recorded`/`with_history` have the same value for two viewers with
different `withheld_tasks`. Fails today: 69 / 40 / 23.

## C6 — the leader's *view* carries custody of other participants' seals (reviews/05 §S1)

**Not a card about `?as=`.** `design/06-group-chat.md:73` R1 sanctions `?as=` for reads in
explicit terms ("a legitimate, cheap affordance"), and the fallback default to the channel leader
is what R1 specifies four lines later. Neither is a defect and I withdrew a claim that said
otherwise.

The card is that `may_see_peer_secrets` is `not walled_off(state, channel, viewer)`
(`aimboard/gate.py:31-33`) and `walled_off` exempts `kind == "human"` (`gate.py:24`), so the
leader's seat is the one view in the fabric that carries a privilege over *third parties'* sealed
positions. Measured: `?as=human` → 5 sealed entries with claim arrays; `?as=codex` → 1 (his own,
via `who == viewer`); `?as=codex-orangement` → 0.

**Acceptance:** the set of sealed entries carrying `claims` does not depend on the borrowed `as`,
except for the borrower's own seal; i.e. it is decided by the connection identity (the server's
`--viewer`), not by the query string. A test asserts `payload(as=X)["sealed claims"]` is the same
for two different `X` from one connection.

**My fix is necessary and not sufficient, and the independent review is why I know.**
`walled_off` (`gate.py:24`) returns False for `kind == "human"`, and that is now the *whole* of the
exemption — but F34 of `reviews/independent-review-claude-new-session.md` shows the exemption is
read from a self-asserted string, and its F2 shows any actor may claim any unclaimed id
(`bin/aim:614-634`). So keying `may_see_peer_secrets` on the connection identity only moves the
question to "what attests the connection identity", which is unauthenticated. **C6 and F2 must ship
together**; C6 alone would relabel the hole rather than close it. Recording it here so the card does
not get cut in half.

**Second, separable and one field:** add `read: {"as": <viewer>, "borrowed": <bool>}` to
`/api/state`, mirroring `write.as` from R2. Support is not hypothetical: my own monitor shipped
with `--state .../api/state?as=human` as a default, and I reported that seat's `recorded` and
`with_history` as the project's totals for an hour without noticing. Nothing in the payload would
have told a consumer it had borrowed a seat.

## C7 — a draft room is invisible to its own author (`aimboard/gate.py:77-84`)

`design/06-group-chat.md` §2: a draft room's messages are "readable by **their author** and by the
leader, and by nobody else". `visible_rooms` has no author exemption, unlike `visible_tasks`
(`gate.py:69`), so the author is excluded. Repro: `python3 reviews/07-room-author-probe.py` →
`3/4`, the FAIL being the author row. `tests/test_room_gate.py` pins the peer and leader rows and
not the author row.

**Acceptance:** in a divergence-phase channel, a room with no `visibility` field is readable by its
author, not by the other participant, and by the leader.

**Also, do not implement the remedy printed at the end of `tests/test_room_gate.py`** ("key the
gate on the channel's phase"). It would delete the `aim room publish` capability that
`design/06` §2 specifies. Reasoning in `reviews/07-room-gate-decision.md`.

## C8 — the T-0110 barrier guard is armed only by a leader declaration (`bin/aim:393-483`)

**Not a bug in the guard.** The guard works: a declared shared workspace refuses a divergence
phase with the reason `design/07` §7 asked for, and names the path and both participants
(`reviews/08-workspace-guard-probe.py`, cases B0/B pass). The card is the arming.

`_workspace_conflicts` reads `manifest.get("workspace")` and nothing else (`bin/aim:416`), and the
only actor who may set it is the human leader (measured: *"'alpha' may not change the channel's
declaration. only the human team leader 'leader' controls phase transitions"*). So the check cannot
fire on an undeclared-but-real overlap — probe case A: both participants edit the same checkout
before sealing, nothing declared, `advance --to COMMIT` **succeeds**.

`channels/hello/manifest.json` has no `workspace` key and is in `COMMIT`, while its participants'
processes run in this tree (`/proc/<pid>/cwd`: 16052, 16714, 40860, 84418 → `/root/tmp`). The
function's own docstring names `hello` as the reason it exists, and it does not fire on `hello`.

**Acceptance:** if `register` recorded a session's working directory, an *undeclared* overlap
between two participants of a divergence-phase channel is refused or at least reported.
Falsifier for the card: an argument that a declaration-based check is sufficient because the
leader is reliably the one who knows. The function's docstring says a participant's word cannot be
trusted on this question; a leader's word is still a word.

## C9 — registry cannot say which project a session is on (evidence for the unplanned feature)

Two live agents run in `/root/workspace/newgate-ext`, a different project, while registered in or
beside this fabric (pids 6199, 66560). `registry.json`'s `session` is free text with no validator
(`"pts/7 claude pid 1697672"`, `"primary-review"`), so `aim` cannot answer "who is on which project
right now" from the record — only `ps` can. This is the demand signal for "multi-session / project
management", which has zero tasks and no milestone.

**Acceptance:** a session is identifiable, attributable to an agent, and located (project/working
directory); and one command answers "which sessions are on which project" from the record.

## C10 — T-0219's acceptance clause 2 would break `aim room publish` (and `aim task publish`)

`T-0219`'s acceptance says: *"the phase gate makes a hand-written 'published' room unreadable during
a divergence phase (tests/test_room_gate.py row 3 flips)"*. Taken literally this makes a published
room unreadable in divergence, so `aim room publish` cannot "open it early" as `design/06` §2
specifies, and the same two lines of code serve rooms (`gate.py:77`) and tasks (`gate.py:68`), so the
rule applied consistently would also contradict `design/05` §1's `aim task publish`.

**Keep the outcome, replace the mechanism: provenance, not phase.** A `visibility` value with no
recorded publish event behind it is inert, in both surfaces. Row 3 still flips — the fixture
hand-writes the field — for the right reason.

**Acceptance (replacement for clause 2):** a hand-written `published` room *and* a hand-written
`published` task are unreadable to a peer during a divergence phase, while a room published through
`aim room publish` is readable from that moment. Full reasoning: `reviews/10-room-publish-provenance.md`.

## C11 — a web regression is riding in the M2 milestone, so M2's progress measure is diluted

`T-0225` ("A route change waits for ten animation frames...", `backlog`, owner `claude-session1`,
tags `regression, web`) is filed with **`milestone: M2`**. M2 is "Group chat: rooms, cursors,
mentions", due 2026-09-23, and its acceptance sentence is *"N agents in one room, ordered, no lost
message under 12 concurrent writers"*. T-0225 has nothing to do with rooms and cannot contribute to
that sentence.

Consequence, and it is the measurable kind: `reports.milestones.M2.total` is the project's own
progress measure (`aimboard/fold.py:175-180`), the Gantt draws it, and the milestone's open count
went 11 → 12 at 08:08Z because of a UI regression. A milestone whose denominator can absorb
unrelated work cannot be used to answer "is group chat going to make its date" — which is the
question the milestone exists to answer, one day before the date.

To be clear about what is *not* wrong: the card itself is exemplary. It carries a reproduction and a
numeric acceptance (median click-to-URL under 1s at CDP x20 throttling, against a measured 44441ms
median today), which is better than most cards I have read here. The finding is the milestone field.

**Acceptance:** a card whose acceptance sentence cannot contribute to a milestone's acceptance
sentence is not in that milestone. A test asserts every task's `milestone` names a milestone whose
`accept` the task could move.

Credit where due: whoever filed T-0225 found a real and severe regression (44 seconds to complete a
navigation) with a measurement rather than a complaint. I am filing against its milestone, not it.

## Not filed, deliberately

The leader/synthesizer parse issue codex asked me to write up with a `file:line`: the rendering is
`bin/aim:2410` (`leader    {m['leader']}   synthesizer {...}`) and the parse site was
`reviews/org/aim-org.py`, which is **mine**, and I already fixed it. The unplaced agents were my
bug, not the tool's. I do not think it should become a card; a human reads that line correctly.
I am recording it here so the trail shows it was considered and dropped rather than forgotten.
