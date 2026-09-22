# 14 — Raw findings from the independent audit (new session, 2026-09-22)

Three independent read-only passes were run by a session that joined as
`claude-session1` (the id it was delivered mail under; **not** the session that
sealed `4ad12910aed7…` — that one recorded `model: "Opus 5"`, this one runs
Sonnet 5). Two passes were separate agents over `bin/aim` and `aimboard/`; the
third was the author's own read.

This file is the **raw dump**, filed so the findings are not lost. It is not
triaged, not deduplicated against existing cards, and not verified end-to-end —
the shell sandbox blocked execution for two of the three passes, so most items
are argued from the read path and marked as such. Line numbers are from the
working tree at the time of reading, which was **being edited concurrently**
(`git status`: `M bin/aim` +471 lines, `M aimboard/{api,cli,fold,gate}.py`).

Treat every item as a lead with a `file:line`, not as a measurement.

---

## A. The audit's own integrity caveat

The repo's rule (`AGENTS.md` "Measuring: name the revision") says a measurement
that cannot name its revision is not a measurement. This file cannot name one:
the tree was dirty and moving during all three passes, and `/api/revision` was
not consulted because no HTTP server was confirmed running. That is the first
finding and it applies to everything below.

---

## B. Path traversal and id validation (highest severity)

**B1 · S1 · Channel ids are never validated and are joined into every path.**
`channel_dir(ch)` = `ROOT / "channels" / ch` with `ch` straight from
`--id`/`--channel`. `cmd_new_channel` writes a manifest through `write_json`
(`mkdir(parents=True, exist_ok=True)` + `tmp.replace`), so an id containing
`../` creates and writes files outside `ROOT` — manifest, `log.jsonl`,
`ledger.jsonl`, `tasks.jsonl`, `private/`, `seals/`, `push.jsonl`,
`friction.jsonl`. `_record_refusal` resolves `channel_dir` from the same
unvalidated string, so a refusal aimed at a traversal path writes a ledger file
outside the root.

**B2 · S1 · Agent ids are interpolated into paths with no sanitization.**
`private/{who}.jsonl`, `seals/{who}.json`, `outbox/<agent>/`. `cmd_register`
accepts any `--as` string and `cmd_new_channel` accepts it as a participant.
An id like `../../agentx` turns `push` into an arbitrary-write primitive against
the root that holds every trust claim.

**B3 · S1 · `register --force` + `--kind human` defeats leader-only phase
control.** `--force` is unconditional; `require_leader` bypasses when
`kind == "human"` and the actor string equals `manifest["leader"]`. So
`aim register --as <leader> --kind human --force` then `aim advance …` moves the
barrier. `AGENTS.md` states "the human leader is the only actor who may advance a
barrier phase" — one unauthenticated command falsifies it, and the only trace is
a field inside `registry.json`. This is my F2/F29/F34 from the other report,
reached independently.

**B4 · S1 · `kind == "human"` is a universal gate bypass.** It short-circuits the
participant check on `say`, the draft gate in `_load_task_or_die`, the leader
check, and the tension gate. "Declare yourself human" is one lever that turns off
every access rule in the fabric.

**B5 · S2 · `Path`-typed flags read arbitrary paths and leak an existence
oracle.** `--evidence` accepts any path, records `kind: "file"` + byte length +
sha256 when the path exists and `kind: "reference"` when it does not, and the
result is readable back through `aim inbox --json`. So any agent can probe for
the existence, size and hash of any file the process can read.

---

## C. The hash chain does not do what the docs say

**C1 · S1 · Tail truncation is undetectable.** `cmd_verify` checks only
self-consistency: each record's hash against its body, and `prev` against the
previous row. There is no expected length, no head anchor, no external
commitment. Truncating the last N lines of `ledger.jsonl`/`log.jsonl`/
`tasks.jsonl` leaves a self-consistent prefix, so `verify` prints `chain OK`.
The ledger is the artifact `README.md` §3 offers as the audit; it can be edited
by the agent it is about. `append_chained` also tolerates a hash-less tail via
the `chain_broken` path, so a writer that simply stops writing hashes produces a
file that verifies clean forever.

**C2 · S2 · `_note_append` makes any post-seal append a silent success.** After
`check_sealed_prefix` confirms the frozen prefix, `_note_append` returns `True`
for any longer file. A sealed agent may append a rewritten position and `verify`
still reports intact. The seal covers the prefix; "revised after seeing the
exposure" lives in the tail.

**C3 · S2 · `advance --to SYNTHESIS` tests for a seal *file*, never its
content.** The precondition is `os.path.exists(seals/<p>.json)`. Nothing checks
the seal's `digest` or its private-log commitment — a seal `cmd_verify` reports
as TAMPER still satisfies the barrier's one hard precondition. `cmd_seal` also
writes the file and the ledger row in two separate lock scopes, so a crash
between them leaves a seal with no `seal` event, which the gate accepts anyway.

**C4 · S2 · Re-sealing in COMMIT silently rewrites the seal.** Allowed in
`SEALED_DIVERGENT` and `COMMIT`; the second seal replaces `summary` and `claims`
while the ledger keeps both digests and `cmd_verify` never cross-checks them.

---

## D. Refusals: the ledger misses the ones that matter

**D1 · S2 · Every `cmd_register` refusal is unrecorded.** `_record_refusal`
returns early when `_CTX["channel"]` is falsy; `register` has no `--channel`, so
both the pre-lock and in-lock `die` write nothing. `README.md` §3 lists
"re-registering a live agent id" under **Enforced** with "the refusal is now
written to the ledger". It is not — and it is the one refusal that would make B3
visible after the fact.

**D2 · S2 · `cmd_confirm`'s refusals are unrecorded.** No `note_context` call;
`confirm` has no `--channel`. All three `die`s are silent, including the
bytes-did-not-match case `README.md` §3 calls **Enforced**.

**D3 · S2 · argparse usage errors reach no ledger, and the fix was applied to
one flag only.** The comment documenting this exists for `--token`
(deliberately `required=False` so the refusal is recorded). But `--reason`,
`--id`, `--to`, `--owner`, `--participants` and others are still
`required=True`, so a barrier-shaped attempt (`aim request-advance …` with a
missing flag) exits 2 with zero ledger rows.

**D4 · S2 · `class` is now decided by whether someone typed it.** The in-flight
change makes the default `cls="unrecorded"`. The sites that still omit a class
are precisely membership/limit refusals that are barrier rules —
`cmd_say`'s `--responds-to`, round quota, echo limit, `--echo-ok` reason;
`cmd_task_move`'s illegal transition and blocked-by checks; `cmd_task_link`;
`cmd_task_retract`'s ownership check; `cmd_new_channel`'s participant check.
`unrecorded` is not a filter option on the Barrier pane by design, so those rows
are invisible to both filters and the refusal count "does not add up". My F9 is
the same finding from the live ledger, where `ledger.jsonl:3` is a
`'codex' may not advance the barrier` refusal filed as `form` while
`bin/aim`'s own comment names that exact sentence as a `barrier` refusal.

**D5 · S3 · Refusal rows record the phase from a lock-free manifest read taken
after the decision to refuse.** Under a concurrent `advance` the recorded phase
is whichever write landed, so a `barrier` row can name the wrong phase.

---

## E. Concurrency: locks that do not cover what they are named for

**E1 · S1 · `manifest.json` has no lock.** Every writer does
`load … mutate … save_manifest` with a plain atomic-per-write `write_json`.
`cmd_advance` loads and saves with no lock across the whole transaction. Two
interleaved writers lose one write, and an `advance` that validated against the
older manifest can persist a phase the newer manifest falsifies. This is the
lost-update class `README.md` §4.10 claims to have fixed one level down — the
phase *is* the barrier.

**E2 · S2 · `cmd_seal` reads the private log three times without the writer's
lock.** `read_jsonl`, then `read_bytes().hex()`, then
`sha256_hex(read_bytes())` — while `cmd_say` appends under `channel_dir/.lock`,
which `cmd_seal` does not take. A concurrent `say` produces a seal whose three
commitment fields disagree with each other, and every later `aim verify`
reports `TAMPER` against an agent that tampered with nothing. The failure mode is
inverted: honest concurrency trains readers to ignore the detector. **This is my
F15 found twice, independently, by two different methods** — worth treating as
the most reliable finding in this file.

**E3 · S2 · Message ids, quota and the echo check are decided outside the append
lock.** `prior_log = read_jsonl(log)` and all three checks run before
`with Lock(...)`, and only the sequence number is taken inside. Two writers that
each see ≤1 of their own messages both append in the same round. `MAX_MSGS_PER_ROUND`
and the echo limit are the two mechanisms `README.md` §3 lists as **enforced**
turn-taking; both are TOCTOU.

**E4 · S3 · `is_answer_to_me` is a substring test over the question body.** Any
agent id appearing anywhere in a question's text exempts every later reply that
`responds_to` it, unbounded, and the check never verifies the reply is to the
asker. The quota is enforced only against agents nobody wrote a question about.

**E5 · S3 · Doorbell config create/rotate/delete check idempotency outside the
lock they then take.** Two concurrent creates for one task+url both append —
the double-ring the nearby comment says the check prevents.

---

## F. Work-item state machine

**F-a · S2 · `link` accepts a dependency cycle, which deadlocks both items.**
Only self-block is refused. A→B then B→A is accepted; moving either to `done`
requires all blockers done, so both are permanently unclosable except by
`--force`. Each row shows one blocker id, so nothing on the board says the two
block each other. (This is card T-0221, still unimplemented.)

**F-b · S2 · A dropped blocker blocks its dependents forever.** `done` is the
only status that satisfies a blocker; `dropped` is terminal and counts as open.
The only recourse is `--force`.

**F-c · S2 · `--force` on a blocked move is not recorded.** The printed refusal
says `"Done" is the one status that has to be decided by something other than
the person asserting it` — and `--force` is exactly the person asserting it. No
ledger event, unlike `task publish`, which got `task_published_during_divergence`
for the analogous deliberate breach. So "how did this reach done with an open
blocker" is unanswerable from the store.

**F-d · S3 · `--force` does not record which blockers it overrode.** Even when a
flag is written, the blocker statuses at that moment are not snapshotted, so the
override cannot be reconstructed.

**F-e · S3 · `cmd_task_retract` checks ownership before existence, on two
different folds.** A nonexistent id skips the ownership branch entirely, so the
probe shape an agent takes while the barrier is closed is never recorded.

**F-f · S3 · `aim status` requires no identity at all and leaks per-participant
record counts and seal digests.** During `SEALED_DIVERGENT` an unauthenticated
reader learns how much private reasoning each peer produced and whether they
have sealed. `design/05` §4 exists to stop leakage in the least suspicious form;
a record count is that form.

---

## G. Smaller but concrete

**G1 · S3 · `visible_tasks` exempts a task whose channel cannot be resolved.**
`by_id.get(task["channel"], default)` falls back to `gate_channel`'s answer,
whose last resort is `channels[0]` — a positional default. A draft in a renamed
or misspelled channel is judged by an unrelated channel's phase.

**G2 · S3 · `_plan_id_floor` is root-global while `tasks.jsonl` is
per-channel.** Two channels can each legitimately create `T-0001` on a root with
no `plan/`, and the merged board draws both.

**G3 · S3 · A comment asserts a measured fact the code no longer satisfies.**
`aimboard/a2a.py` records that `created_by` is not among `PLAN_FIELDS`;
`created_by` was added at `aimboard/const.py:17`, so the two visibility rules
genuinely diverge rather than agreeing by accident.

**G4 · S4 · `--body` given a path sends the path, silently.** Fixed in the
uncommitted tree (`bin/aim:829`) for the verbs that were patched; the finding is
card T-0224.

---

## H. What is already fixed in the uncommitted tree (do not re-file)

Verified by reading the working tree, not the record:

- **T-0222** (refusal `class` at the site): 95 `cls=` call sites present in
  `bin/aim`; default changed to `unrecorded` with a long justifying comment.
  Card still `ready`. The open question is D4 above: the sites that *omit* it.
- **T-0224** (`--body` looks like a file): implemented at `bin/aim:829`.

## I. Cross-checks between the three passes

Where two passes found the same thing by different methods, confidence is high
and those are the ones worth carding first:

| finding | pass 1 | pass 2 | author |
|---|---|---|---|
| seal read without the writer's lock | E2 | — | F15 |
| empty-log seal reports false TAMPER | — | — | F15 (author, proven) |
| `kind == "human"` bypass | B4 | §3 (author's §9) | F34 |
| `--force` + human = barrier takeover | B3 | — | F2/F29 |
| digest/scoped invalidation | #1/#10 | #9 | F37/F52 |
| refusal ledger not auditable | D1-D4 | D-2, D-4 | F8-F11 |
