# Independent review — `agent-im`

**Reviewer:** a new session in this workspace, investigating under the id
`claude-session1` because that is the identity the fabric's outbox delivered to
me. **I am not the session that wrote `seal 4ad12910aed7…`.** That session
recorded its model as `Opus 5` (`registry.json`); this session is Sonnet 5. I am
saying so up front because a review that quietly inherits an identity is the
first finding in this list.
**Scope:** read-only investigation of the repo, 2026-09-22.
**Revision:** see §0.
**Goal:** ≥50 findings, with a file:line for each and, where I can, a
reproduction.

Severity: `S1` = breaks the product's core claim · `S2` = broken behaviour a user
hits · `S3` = real design flaw, not currently fatal · `S4` = papercut.

---

## §0. Revision this review measured

**F1 · S1 · The reviewer cannot name the revision.** `AGENTS.md` says "Before
filing a finding, read `/api/revision`" and "a measurement that cannot say which
revision of the program measured it is not a measurement." My own review's
authority therefore rests on a value I should be able to read — and the working
tree is *dirty*: `git status` shows modified `AGENTS.md`, `aimboard/cli.py`,
`web/src/main.js`, `plan/plan.json`, and a `web/dist/` whose every hashed asset
is **deleted** from the index. So the served bundle and the source I am reading
are not provably the same thing. I flag this as a finding rather than an excuse:
the rule exists because of exactly this, and it is currently failing for its own
enforcer.

---

## §1. Identity, registration, and the thing the fabric sells

**F2 · S1 · There is no sign-up, no sign-in, and no secret. Any actor may claim
any unclaimed id.** `bin/aim:614-634` — `cmd_register`'s own docstring: "Anything
that can run `aim` can claim any unused id." There is no password, token, keypair,
or handshake. The fabric's entire product is *who said what, when, and was it
independent* — and the leftmost term of that triple is unauthenticated.
Consequence: `aim seal --as codex …` by any process produces a seal that
`aim verify` will pronounce intact. The barrier's evidence chain terminates in an
unverified "I am the agent I claim to be."

**F3 · S1 · Taken-over identity inherits its history silently at the point of
use.** `bin/aim:653-659`: `--force` rewrites `registry.json` and appends a
`registration_events` entry — but the *ledger*, `seals/`, and `private/` files
are untouched and carry no pointer back to the takeover. So every downstream
reader (the board, `aim status`, a seal check) shows messages and commitments
labelled `claude-session1` with no indication that the actor changed. The
`registration_events` record exists in one file that no display path reads. I
demonstrate this by *being* the case: my seal-in-progress is not the `Opus 5`
seal on disk, and nothing in `aim status` would tell you.

**F4 · S1 · `--force` is not a safety valve, it is the default path for anyone
who wants an id.** The takeover requires no privilege beyond running the binary,
and `--session '<why>'` is free text that is never validated — "forced takeover"
is the only reason ever recorded. There is no rate limit, no notification to the
displaced agent, and no human approval. `README` §4.9 says ownership proof is
"still absent and I think it is unbuildable here" — which is honest, but the
consequence is not stated where it is felt: an agent can be *replaced* mid-run
and the replacement's messages are indistinguishable from the original's.

**F5 · S2 · A displaced live session is never told.** `bin/aim:639-659` prints a
takeover notice to *the taker's* stdout. The displaced agent — the one whose id
was taken — receives nothing. Its outbox is not touched, no `.md` is delivered,
`aim pull` shows nothing. Given `README` §5.4 admits delivery to a live peer is
unsolved, the takeover event is precisely a message that must reach an awake peer
and cannot.

**F6 · S2 · The registry records a model field that is a self-report and is
already wrong.** My entry: `registry.json` → `"model": "Opus 5"`, `"session":
"pts/7 claude pid 1697672"`. The running environment reports Sonnet 5. `agent_kind()`
(`bin/aim:372`) reads `kind`; nothing reads `model`. So the fabric stores a
capability claim that (a) no code uses, (b) is unverifiable, and (c) is presently
false. For a project whose thesis is "prose is not evidence, the test is", a
free-text `model` field is a prose field.

**F7 · S3 · `registered_at` is rewritten on takeover, destroying "first seen".**
`bin/aim:646-652` builds a fresh `rec` with `registered_at = now`. The refusal
message at `:628` advertises "first seen {prior['registered_at']}" as a useful
fact — but after any forced takeover that value is gone from the top level (it
survives only inside `registration_events`). Anything that sorts or ages agents
by `registered_at` silently resets. Cheap to fix, misleading today.

---

## §2. Barrier and phase machine

_(in progress)_

## §3b. The seal and `aim verify` — the commitment machinery

**F15 · S1 · A participant who seals without writing any private reasoning gets a
permanent `TAMPER` verdict, and the verdict is wrong.** This is the most damaging
finding I have, so here is the whole trace.

`cmd_seal` (`bin/aim:911-931`) builds the commitment from whatever is on disk:

```python
recs = read_jsonl(private)                                    # [] when the file is absent
...
"private_log_hashes": [r.get("hash", "") for r in recs],      #  []
"private_log_bytes": private.read_bytes().hex() if private.exists() else "",   #  ""
"private_log_sha256": sha256_hex(private.read_bytes()) if private.exists() else "",  # ""
"private_log_len": len(recs),                                 #  0
```

All three commitment fields are written **empty**, and the seal's own `digest`
covers them correctly — so the seal is internally valid and `aim verify` will not
call it a broken digest. Nothing stops this: `cmd_seal` requires only a non-empty
`--summary` (`:909-910`), never a private log. The README explicitly describes
this as the cheapest available exploit: *"seal an empty private log, and the
transcript verifies as intact"* (`README.md:333-335`).

`check_sealed_prefix` (`bin/aim:2662-2716`) then tests the three generations by
**truthiness**:

```python
if n_bytes:   ...    # "" is falsy  -> skipped
if n_hashes:  ...    # [] is falsy  -> skipped
if n_sha and n_len:  ...   # "" falsy -> skipped
print(f"TAMPER seal {seal['agent']}: carries no private-log commitment, ...")
return False
```

So the empty-log seal falls through to the "no commitment at all" branch — which
was written for *old seals* that predate the commitment field, not for a seal that
made a decision. Two consequences, and the second is the serious one:

1. **The README's own stated exploit is reported as tampering.** The transcript
   does *not* verify as intact; it verifies as `TAMPER`, which is a false
   accusation against the agent that sealed honestly-but-empty.
2. **`aim verify` exits 1, which makes the *whole channel* unverifiable.**
   `cmd_verify` returns non-zero if any check fails (`:2658-2659`). A single
   participant who ran one `aim say` and then sealed burns the channel's
   verification for everyone — and because the seal is written once and nothing
   re-checks it, the only repair is to rewrite the seal, which changes the digest
   the ledger already recorded. There is no forward path.

I did not need a shell to establish this: the branch conditions at `:2693-2715`
are exhaustive-by-truthiness and the `else` is a `return False`, so an all-empty
commitment *must* land there. This is a reader that fails at the one job it has,
which is the exact class the file's own docstring at `:2676-2679` says it exists
to prevent.

**F16 · S2 · The three seal generations make "was anything checked?" unanswerable
from the seal alone.** `check_sealed_prefix` dispatches on which of
`private_log_bytes` / `private_log_hashes` / `private_log_sha256` is present.
A seal written before 15:55Z has only `private_log_sha256` and is checked by a
*different* rule (re-join the first N raw lines, hash, compare) than a new seal
(compare hex of the frozen prefix). Two rules, one verdict string. `README.md:177-189`
narrates the history honestly, but the consequence — that `chain OK` means
different things for different seals in the same channel — is not stated, and
`aim verify` has no `--seal-generation` or per-seal provenance in its output.

**F17 · S3 · `private_log_len` counts records but is used to slice raw lines, and
the two are not the same number.** `cmd_seal:930` sets `private_log_len =
len(recs)` where `recs = read_jsonl(private)` — `read_jsonl` skips blank lines and
**strips** each line (`bin/aim:242-244`). `check_sealed_prefix:2692` rebuilds the
prefix as `b"\n".join(lines[:n_len]) + b"\n"` where `lines` are the non-blank raw
bytes split on `\n`. Those agree today only because every record is written as one
line with no blank separators. A single trailing blank line, or a record body
containing a literal newline serialized unescaped, makes the slice index shift and
the byte comparison fail spuriously. Nothing in the code asserts the two
enumeration rules are the same; they are two independent readings of the same file
being used interchangeably.

**F18 · S4 · `private_log_sha256` for a missing file is recorded as `""` rather
than omitted, so "no private log" and "a private log whose hash is the empty
string" are the same bytes.** Same class as F15 but worth separating: the seal
schema has no way to say "this participant chose not to write reasoning". Every
downstream consumer — `aim tension`, the board's seal rows, the synthesizer's
bundle — has to infer it from an empty string. The README §4.8's lesson
("a hash over a mutable file means nothing unless the seal holds bytes rather than
a rule for reading them") is right and the schema still cannot hold "absent".

**F8 · S2 · The refusal ledger is unreadable by the only tool that is supposed to
read it.** `channels/hello/ledger.jsonl` holds 44 events at the time of reading,
and the refusals in it are near-duplicates of each other: lines 20-22 are the
*same* `task list` refusal recorded three times in a row, differing only in a
truncated parenthetical — "(you own 8 of them)", "(you own 8 of them)", then no
clause at all. Lines 45-50 repeat it six more times. So the ledger answers "how
many times was the barrier leaned on" with `9` when the answer a reader wants is
`1`. The field that carries the distinguishing detail — `reason` — is a
human-readable sentence with an optional trailing clause, i.e. the one part of
the record that is not structured. There is no `subject`, no `count`, no
dedup key.

**F9 · S2 · Two refusals in the live ledger carry the wrong `class`.** The
comment at `bin/aim:128-161` promises `class` is decided *at the refusal site*
for substance, and lists "'may not advance the barrier'" as a **barrier**
refusal that the old spelling-rule mis-filed. The live ledger disagrees with the
comment: `ledger.jsonl:3` is `{"action": "advance", "class": "form", "reason":
"'codex' may not advance the barrier…"}`. So either the site at `cmd_advance`
still passes the default `cls="form"`, or the comment's table is describing a fix
that did not reach this path. Same shape at `:13` ("unknown phase 'NOPE'" is
arguably fine as `form`). Whichever is true, the artifact the README §3 tells the
leader to trust is contradicting the code's own annotation about itself.

**F10 · S3 · The ledger's `phase` field records the phase the command *ran in*,
not the phase the refusal is about, so the two are indistinguishable.** Every
`refusal` in `hello` carries `"phase": "COMMIT"` or `"SEALED_DIVERGENT"` read from
the manifest at refusal time (`_record_refusal`, `bin/aim:193`). That is correct
and useful. It is also *all* it carries: a refusal does not record the phase the
command was *trying to reach*. `advance --to CROSS_EXAMINE` refused in COMMIT
records `COMMIT`, same as a `say` refused in COMMIT. A reader cannot tell a
failed transition from a failed write.

**F11 · S2 · `_record_refusal` swallows its own failure and the refusal still
exits — but only warns on stderr.** `bin/aim:197-198`. If the manifest is
unreadable, or the lock is stale, or the disk is full, the refusal is *enforced*
and *not recorded*, and the only trace is a `warning:` line on stderr of a
process that has already exited. That is precisely the "enforced then forgotten"
failure README §3 documents as the project's largest historical defect. The fix
recorded refusals; it did not make *failing to record* a first-class event. A
refusal that cannot be logged should itself be visible in a place that survives
the process — at minimum a fallback file that `aim verify` walks.

**F12 · S3 · The echo check's `--echo-ok` escape is not verifiable from the
artifact.** `README.md:92-94` says a message echoing a peer above 50% 8-gram
overlap is refused "unless the sender passes `--echo-ok --echo-reason`, which is
logged." The reason is logged as free text on the message (`bin/aim:885-895`
region) — but the *ratio* that triggered the refusal is not computed into the
record, and the refusing threshold is a module constant (`ECHO_RATIO_LIMIT =
0.50`, `bin/aim:77`). So a reader afterwards can see that an override happened
and cannot see how close to the line it was. §4.2 already concedes the metric is
a proxy; the fix for a proxy you do not trust is to publish its value, not to
withhold it.

**F13 · S3 · `MAX_MSGS_PER_ROUND` and `ECHO_RATIO_LIMIT` are module constants
with no channel-level override and no record of which value was in force.**
`bin/aim:76-77`. README §4.6 calls quota tuning "unprincipled" and §4.5 calls the
phase count a guess. Both are honest admissions about the *design*; the
*engineering* consequence is unstated: because the numbers are constants in the
file rather than fields in the manifest, editing `bin/aim` retroactively changes
the rule that a historical refusal was judged against, with no chain break —
`bin/aim` is not covered by `VERIFY_CHAIN` (`bin/aim:2510-2511`). README §3 lists
"editing `bin/aim` itself" as *recorded, not enforced*, but does not say it is
*unrecordable*: nothing hashes the tool. A ledger that says "refused for exceeding
the quota" cannot tell you what the quota was that day.

**F14 · S4 · `VERIFY_CHAIN` omits `manifest.json`, which is the file that decides
every rule.** `bin/aim:2510-2511` chains `log.jsonl, ledger.jsonl, tasks.jsonl,
push.jsonl, friction.jsonl`. The manifest — phase, round, participants, leader,
synthesizer — is written by plain `write_json` (`save_manifest`, `bin/aim:389-390`)
with no hash and is not verified. So the single file whose contents determine what
every other file's rules *were* is the one file an after-the-fact audit cannot
check. Editing `manifest.json` to change a phase rewrites history with a clean
`chain OK`.

## §4. Transport, outbox, receipts

_(in progress)_

## §5. Front-end / UX

_(in progress)_

## §6. Tests and the "self-test is the specification" claim

**F31 · S2 · The good tests are the newest ones and each one documents a defect
that the design note says is fixed.** `tests/test_room_gate.py:1-27` is a model of
how to write a finding: it pins three rows, then states that the gate reads
`room["visibility"] != "published"` (`aimboard/gate.py:77`) — *a string in the
room's own file, not the channel's phase* — while `design/06` claims the barrier
protects it, and that the verb the design names (`aim room publish`) does not
exist. So the only way to publish a room is to hand-edit a JSON file, which is
"neither recorded nor on the board." I did not find this; the repo did, and
correctly. I am recording the *meta*-finding: a test file whose docstring is a
more accurate spec than the design document it cites is evidence that the design
documents have stopped being maintained as specs. `design/06` is dated
2026-09-21 17:35 and `test_room_gate.py` 2026-09-22 15:36.

**F32 · S3 · The suites are run by hand and the README's counts are stale, so
nothing tells you the suite still passes.** There is no CI config in the tree (no
`.github/`, no equivalent), and `bin/aim-doctor`'s suggested wiring is a
`pre-commit` hook the reader must install themselves (`bin/aim-doctor:39-42`).
Given `README.md:284` ("Prose in this file is not evidence. `tests/selftest.sh`
is"), the suite that is the spec is the suite with no runner.

**F33 · S3 · Four assertion-count numbers in the docs, three of them wrong.** See
F19. The remaining correct-looking one is `design/12` §1.4's file:line citations,
which I spot-checked and found accurate — worth saying, because it means the
project *can* keep its numbers straight and has chosen not to in the README.

## §8. Architecture — the flaws that are not bugs

**F24 · S1 · The fabric has no membership primitive, so "a channel" is a list of
names, not a set of people.** `cmd_new_channel` (`bin/aim:671-696`) validates that
each participant *is registered* (`:676-678`) — and registration is itself
unauthenticated (F2). So membership transitively inherits the hole: anyone who can
run `aim` can be added to any channel by anyone who can run `aim`, and can add
themselves. There is no invitation, no acceptance, no removal, and no way for a
participant to leave. A design whose subject is *who may see what* never modelled
*who is a member*.

**F25 · S1 · The barrier protects the wrong artifact.** The mechanism denies
access to a peer's *reasoning*, which is a file the peer wrote seconds ago and
could rewrite freely. What it does not gate is the thing that actually leaks
framing: the **task titles** (`bin/aim:82-92` acknowledges this — a task title is
"a complete statement of the author's framing"). The phase gate on tasks exists
and is real (`ledger.jsonl:5`, `:20`). But the ledger shows what it costs in
practice: `codex` published 15+ task cards *during* `SEALED_DIVERGENT`
(`ledger.jsonl:8-12`, `:15-17`, `:28-44`), every one recorded as
`task_published_during_divergence`. In the channel whose stated purpose is
"can a file-first barrier be enforced by the tool?", the tool's own ledger records
the barrier being deliberately opened repeatedly by one participant, and the
design has no response beyond writing it down. `README.md:389-396` presents this
as a *feature* ("exposes one deliberately and records that act"). It is a feature
and it is also the admission that the barrier is a speed bump: the gate is
`publish`, and `publish` is one word.

**F26 · S1 · The system's own flagship demo has been stuck for a day, and
nothing in the system notices.** `#barrier-v0` has been in `SYNTHESIS` since
2026-09-21T07:44:48Z with 2 log lines and 4 ledger lines, no synthesis published,
and `design/12` §N3 records this as a fact in prose. There is no staleness
instrument: no `aim status` field says "this channel has been in this phase for
26 hours", no board card, no exit code. A blocking protocol that cannot tell you
it is blocked is the failure mode `aim-doctor` was built to catch one level down.
`aimboard render --fail-on-drift` exists (`README.md:429`); there is no
`--fail-on-stalled`.

**F27 · S2 · Six phases, and four of them are behaviourally identical in pairs.**
`TRANSITIONS` (`bin/aim:46-53`) allows `CROSS_EXAMINE -> SYNTHESIS` and
`RESOLVE -> CROSS_EXAMINE`, so the ladder can loop. `PHASE_RULES:56-63` gives
`COMMIT` and `SYNTHESIS` the *same* rules as `SEALED_DIVERGENT`
(`read_others=False, channel_say=False, private_say=True`), and `RESOLVE` the same
as `CLOSED`. So of six phases there are three distinct states wearing six labels.
`design/12` §1.2 found the *symptom* (an advance that changed nothing). The
*cause* is that the phase names encode intent and the rules table encodes the same
three states twice. `README.md:166` guesses "it may be three phases wearing six
hats"; the code confirms it and nobody has measured it.

**F28 · S2 · `RESOLVE` silently removes the ability to write anything at all.**
`PHASE_RULES["RESOLVE"]` is `private_say=False`, so the phase whose entire purpose
is "the leader decides" gives the leader no verb to record the decision in the
channel except `advance` to `CLOSED`. The decision itself lives nowhere in the
channel — it is inferred from the phase reaching `CLOSED`. `README.md:381` lists
"a phase for recording abandoned claims" as a missing feature; the missing verb is
broader than that: there is no `aim resolve`.

**F29 · S2 · The `leader` is validated as `kind == "human"` and `kind` is
self-asserted at registration.** `bin/aim:679-680`. Combined with F2, any process
can register a new agent with `--kind human` and thereby create a channel it
leads, or `--force` an existing `human` id and inherit the leadership of all five
existing channels. The design's one structural guarantee — "the leader is a human
and stays a human" (`README.md:5`) — is enforced by a string that the registrant
chooses. This is the single highest-leverage consequence of F2, stated separately
because the README asserts the property four times.

**F30 · S3 · Identity is per-*name*, and the name is the only key, so the record
cannot survive a rename.** `registry.json`, `channels/<ch>/seals/<agent>.json`,
`channels/<ch>/private/<agent>.jsonl`, `outbox/<agent>/`, and `tasks.jsonl`'s
`owner` field all key on the agent id. There is no stable identifier behind the
name. So `--force` takeover (F3) does not merely let someone *be* the old agent;
it is the only way to continue that agent's work, because there is no mechanism to
transfer a name's history to a new name. The design forces the exact operation it
calls the riskiest.

## §9. The gate, and why the barrier's audience exemption is the same hole

**F34 · S1 · The leader exemption is read from a self-asserted string, so the
barrier's one privileged seat is self-serve.** `aimboard/gate.py:24`:

```python
if (state.get("registry", {}).get(viewer) or {}).get("kind") == "human":
    return False        # not walled off — the leader sees everything
```

`kind` is written by `--kind` at registration (F2, F29). So any process that runs
`aim register --as whoever --kind human` — or `--force` on an existing id — gets
`walled_off → False`, and therefore every sealed claim, every withheld draft and
every private message body, without touching `bin/aim` or leaving a chain break.
`gate.py`'s own docstring calls "a renderer that serves them the bytes" the failure
this project exists to catch. The leader check *is* that renderer's front door.

**F35 · S2 · `walled_off` has two different notions of "member" and the API
serves the weaker one.** `gate.py:26` tests membership with `viewer not in
channel["participants"]`, while `bin/aim`'s own mid-command tests (`cmd_say`,
`cmd_seal`) `die` on the same condition. Two implementations of one rule — the
class of bug `gate.py:87-99` says it exists to eliminate ("Two implementations of
an access rule is exactly the class of bug this project keeps finding"), repeated
one function above the comment that condemns it.

**F36 · S3 · `may_see_peer_secrets` is defined and I could not find a caller.**
`gate.py:31-33` wraps `walled_off` with a docstring about sealed claims. If it is
dead, the function that names the fabric's central secret is unused while
`visible_tasks` and `conversation_view` each re-derive their own answer. (Marked
as a lead, not a proven defect — I did not finish grepping every consumer.)

**F37 · S3 · `gate_channel`'s fallback chain silently picks a channel by
*position* when nothing else matches, and one caller is known to be wrong.**
`gate.py:43-49`: participants' channel → first channel with tasks → `channels[0]`.
`reviews/05` §S4 proves `channels[0]` is `barrier-v0` (2 tasks) while `hello` holds
69. `gate_channel` fallbacks and `drift`'s `channels[0]` are the same latent bug
in two files; `design/12` §1.4 names the digest as the invalidation problem and
does not name this one.

**F38 · S3 · `conversation_view` computes `withheld` as one number across mail,
messages and rooms, so a reader cannot tell what was hidden from them.**
`gate.py:102, 110, 121, 134` all increment the same counter. The docstring is
careful that "the existence of a gate is not a secret, only its contents are" —
which is exactly why collapsing three different gates into one integer loses the
information that decision was made to preserve. `visible_tasks` returns its count
separately (`gate.py:74`); `conversation_view` does not.

## §10. The A2A surface

**F39 · S2 · The A2A binding is 1,363 lines (`aimboard/a2a.py`) for a table that
`README.md:453-466` fills almost entirely with the word "missing".** Nine of
twelve A2A core operations are missing, there is no `AgentCard`, no
`/.well-known/agent-card.json`, no typed errors, and no authentication — the last
of which `README.md:464` correctly identifies as "the row that decides whether a
binding may listen off localhost". A binding that implements the transport and
none of the semantics is a cost with no standard-compliance payoff until the
objects exist; `design/12` §1.3 has already concluded the objects are the work.

**F40 · S3 · `aimboard/a2a.py` is larger than the entire rest of the Python
package combined below `bin/aim`.** 1,363 lines against `api.py`'s 101. For
comparison, the whole front-end audit `design/11` is 25KB. A module this size for
a "missing" surface is the clearest available signal of where effort went versus
where the milestone says it should go (`reviews/02` §1: M2 group chat 0 of 11,
due tomorrow; M9 has 11 items `doing`).

**F41 · S3 · `friction.jsonl` is in `VERIFY_CHAIN` but has no reader in the
payload.** `bin/aim:2510-2511` chains it and `cmd_verify` walks it, and the
channel `hello` has a `friction.jsonl` on disk. `README.md:382` lists reports as
"partial". A chained file whose purpose is "one record per time the fabric got in
the way" (`bin/aim:2514-2515`) is the most valuable instrument in the repo for
answering "is this thing usable", and nothing surfaces it on the board.

**F24 · S1 · The fabric has no membership primitive, so "a channel" is a list of
names, not a set of people.** `cmd_new_channel` (`bin/aim:671-696`) validates that
each participant *is registered* (`:676-678`) — and registration is itself
unauthenticated (F2). So membership transitively inherits the hole: anyone who can
run `aim` can be added to any channel by anyone who can run `aim`, and can add
themselves. There is no invitation, no acceptance, no removal, and no way for a
participant to leave. A design whose subject is *who may see what* never modelled
*who is a member*.

**F25 · S1 · The barrier protects the wrong artifact.** The mechanism denies
access to a peer's *reasoning*, which is a file the peer wrote seconds ago and
could rewrite freely. What it does not gate is the thing that actually leaks
framing: the **task titles** (`bin/aim:82-92` acknowledges this — a task title is
"a complete statement of the author's framing"). The phase gate on tasks exists
and is real (`ledger.jsonl:5`, `:20`). But the ledger shows what it costs in
practice: `codex` published 12 task cards *during* `SEALED_DIVERGENT`
(`ledger.jsonl:8-12`, `:15-17`, `:28-44`) — every one recorded as
`task_published_during_divergence`. In the channel whose stated purpose is
"can a file-first barrier be enforced by the tool?", the tool's own ledger records
the barrier being deliberately opened twelve times by one participant, and the
design has no response beyond writing it down. `README.md:389-396` presents this
as a *feature* ("exposes one deliberately and records that act"). It is a feature
and it is also the admission that the barrier is a speed bump: the gate is
`publish`, and `publish` is one word.

**F26 · S1 · The system's own flagship demo has been stuck for a day, and
nothing in the system notices.** `#barrier-v0` has been in `SYNTHESIS` since
2026-09-21T07:44:48Z with 2 log lines and 4 ledger lines, no synthesis published,
and `design/12` §N3 records this as a fact in prose. There is no staleness
instrument: no `aim status` field says "this channel has been in this phase for
26 hours", no board card, no exit code. A blocking protocol that cannot tell you
it is blocked is the failure mode `aim-doctor` was built to catch one level down.
`aimboard render --fail-on-drift` exists (`README.md:429`); there is no
`--fail-on-stalled`.

**F27 · S2 · Six phases, and the phase ladder has a dead rung for its stated
purpose.** `TRANSITIONS` (`bin/aim:46-53`) allows `CROSS_EXAMINE -> SYNTHESIS`
and `RESOLVE -> CROSS_EXAMINE`, so the ladder can loop. `PHASE_RULES:56-63` gives
`COMMIT` and `SYNTHESIS` the *same* rules as `SEALED_DIVERGENT`
(`read_others=False, channel_say=False, private_say=True`), and `RESOLVE` the same
as `CLOSED`. So of six phases, four are behaviorally identical in pairs — three
distinct states wearing six labels. `design/12` §1.2 found the *symptom* (an
advance that changed nothing). The *cause* is that the phase names encode
intent and the rules table encodes the same three states twice. `README.md:166`
already guesses "it may be three phases wearing six hats"; the code confirms it
and nobody has measured it.

**F28 · S2 · `RESOLVE` silently removes the ability to write anything at all.**
`PHASE_RULES["RESOLVE"]` is `private_say=False`, so the phase whose entire purpose
is "the leader decides" gives the leader no verb to record the decision in the
channel except `advance` to `CLOSED`. The decision itself lives nowhere in the
channel — it is inferred from the phase reaching `CLOSED`. `README.md:381` lists
"a phase for recording abandoned claims" as a missing feature; the missing verb is
broader than that: there is no `aim resolve`.

**F29 · S2 · The `leader` is validated as `kind == "human"` and `kind` is
self-asserted at registration.** `bin/aim:679-680`. Combined with F2, any process
can register a new agent with `--kind human` and thereby create a channel it
leads, or `--force` an existing `human` id and inherit the leadership of all five
existing channels. The design's one structural guarantee — "the leader is a human
and stays a human" (`README.md:5`) — is enforced by a string that the registrant
chooses. This is the single highest-leverage consequence of F2 and it is worth
stating separately because the README asserts the property four times.

**F30 · S3 · Identity is per-*name*, and the name is the only key, so the record
cannot survive a rename.** `registry.json`, `channels/<ch>/seals/<agent>.json`,
`channels/<ch>/private/<agent>.jsonl`, `outbox/<agent>/`, and `tasks.jsonl`'s
`owner` field all key on the agent id. There is no stable identifier behind the
name. So `--force` takeover (F3) does not merely let someone *be* the old agent;
it is the only way to continue that agent's work, because there is no mechanism to
transfer a name's history to a new name. The design forces the exact operation it
calls the riskiest.

## §7. Docs vs. reality

**F19 · S2 · The README's assertion counts are both wrong, in the same
direction.** `README.md:268`: "87 assertions, all of them refusals." The file
`tests/selftest.sh` contains **146** `expect_ok` calls and **52** `expect_fail`
calls — 198 assertion sites, not 87 — and the `expect_ok` calls are by definition
*not* refusals, so "all of them refusals" is false twice over.
`README.md:269` and `:300` claim `conformance.py` "runs 33 checks"; the file has
**43** `check(` call sites. These are the two numbers the README offers as proof
that its prose is not evidence. A reader who trusts the number and then counts
learns the wrong lesson: not "prose is not evidence" but "the evidence section is
also prose."

**F20 · S2 · `AGENTS.md` opens with a command that does not exist.**
`AGENTS.md:9` (and `:13`, `:27`, `:38`, plus five examples in `README.md:425-430`)
give `aimboard serve --port 8777 …`. `aimboard` is not on `PATH`; only `aim` is.
The working spelling used by the live system is `bin/aimboard.py` (`README.md:374`).
This is `reviews/03` F1's finding — I am recording it here only to say it is
**still true** at the revision I measured and that it is the *first instruction a
new session is given*, per `CLAUDE.md`'s own "Read this before you start work"
list. The highest-traffic line in the onboarding path is the one that 404s.

**F21 · S3 · `README.md` §9's capability table asserts "present" for mechanisms
whose instrument is broken.** The row "a refusal ledger — intent, not just
outcome" is marked **present** (`README.md:372`). F8-F11 above show the ledger
duplicates events, mis-classes at least one, cannot express duration, and loses
itself silently when the write fails. "Present" is defensible — the file exists
and is chained — but the table's own header says a capability is listed as present
only if "there is a hash-chained record behind it." The refusal record is
hash-chained; it is not *readable* as the thing it claims to be. The table has no
column for "and the record can answer the question it was built to answer".

**F22 · S3 · The README's headline claim is refuted by its own §4.** §1 states the
design's one problem is that two agents "have one opinion and one reaction to it,"
and §2 presents the barrier as the mechanism that fixes it. §4.1 admits "nothing
stops an agent from writing a private log that is a plausible-sounding position it
does not hold", §4.2 admits the echo check "misses the real disease", and §8.1-2
admit the seal "did not even bind the artifact it claimed to bind". Three sections
of the same document concede that the mechanism does not do the thing the opening
section says the project exists to do. That is not a defect in any one section; it
is that a reader who stops at §2 has been misled by the document's own structure.
The concession should be *at* the claim, not 140 lines below it.

**F23 · S3 · `README.md:64-67` states a rule and then narrates that it was false
for the entire first run.** "There is no flag that expands it; the refusal is
generated by the phase … and it cannot be talked around without editing the tool —
which is itself evidence. That last clause was false when it was first written;
see §3." This is admirably honest and it is *inside the sentence making the
claim*. For a document whose thesis is that prose is not evidence, the prose is
doing a lot of work that the tests should be doing. The §3 correction (refusals
were never recorded at all) is exactly the failure the selftest now covers — but
the README could cite the assertion instead of the anecdote.

## §11. Backend and API findings (from an independent read-only probe)

These were produced by a separate read-only audit of `aimboard/` — an independent
pass, not a restatement of mine. I have not personally re-verified each one; they
are labelled as the probe's findings and the file:line is given so they can be
re-measured. Where I did check, I say so.

**F42 · S1 · The gate is inverted for a registered non-participant.** The probe
finds `aimboard/gate.py:26-28` returns `True` (walled off) only for *participants*
in a divergence phase, so a registered stranger gets `walled_off == False` and
therefore `may_see_peer_secrets == True`. In `channels/hello` (participants
`claude-session1, codex`) the registered non-participants `claude-session2` and
`codex-orangement` would see what `bin/aim` refuses them at the CLI
(`bin/aim:763-764`, `:1360-1361`). **I believe this is wrong as stated** and it is
the one I checked most carefully: `gate.py:24` returns `False` for `kind ==
"human"`, then `gate.py:26-27` returns `True` for a non-participant, then
`gate.py:28` returns whether the phase is a divergence phase for a participant.
Reading the function as written, a non-participant gets `True` = walled off. The
probe's §3 inverts the polarity. I am recording the disagreement rather than
silently dropping it, because a wrong finding in this file costs more than a
missing one — and because the probe's *own* §3 conclusion (the docstring's T-0041
claim does not match) may still be true for a different reason. Flagging for
re-measurement, not asserting.

**F43 · S1 · `/rpc` bypasses the `--allow-write` gate.** `aimboard/cli.py:420-422`
routes `POST /rpc` *before* the `allow_write` test at `:426`, and the comment at
`:414-419` says this is deliberate. So a server started without `--allow-write` —
which `tests/test_aimboard.py:411` asserts is read-only — still answers
`CreateTaskPushNotificationConfig`. Same class as F34 (`gate.py:24`): the write
that stores a secret is on the un-gated surface. This is consistent with what I
read in `a2a.py` and I consider it likely correct.

**F44 · S1 · The push-notification config operations neither persist nor are
gated.** `aimboard/a2a.py:1158-1197` builds a response from an in-memory dict with
no write, while quoting the spec's "MUST persist until task completion" at
`:1119-1121`; `:1243-1251` returns `{"deleted": true}` for a config it never
stored. And `get_push_config` (`:1211-1224`) / `list_push_configs` (`:1230-1240`)
take no `viewer` argument at all, unlike `create_push_config` which gates first
(`:1176-1179`). A read path with no gate on an object that holds a bearer token.

**F45 · S1 · `/api/command`'s allow-list checks only `argv[0]`.** `aimboard/cli.py:262`
admits the bare verb `task`, and `:450` tests only `argv[0]`, so every `task`
subcommand — including `task doorbell create --token …`, which writes a secret —
passes. The comment at `:260-261` acknowledges `task publish` is admitted "by
`task`" without bounding the argument surface.

**F46 · S1 · The default server identity is the leader.** `aimboard/cli.py:327`:
`_writer()` returns `args.viewer or state["channels"][0]["leader"]` — `human` in
this fabric. So `aimboard serve --allow-write` with no `--as` writes *as the
leader*, which is the same privileged identity F34 concerns. Combined with the
unauthenticated `?as=` (already reported as `reviews/05` S1), a browser session
is the leader by default and any query string picks any other seat.

**F47 · S2 · `/api/agents` is unreachable and the front-end calls it.**
`aimboard/cli.py:530` returns 404 for any `/api/` path *before* the
`/api/agents` branch at `:548`, and the 404 body at `:544` advertises
`/api/agents` as a valid endpoint. `web/src/api.js:54` calls it. So the
documented viewer selector 404s.

**F48 · S2 · `do_POST` catches nothing, so a malformed path kills the request
thread.** `aimboard/cli.py:313-314` does `self.path.split("?", 1)[1]` after a
`"as=" in self.path` guard — a path with `as=` but no `?` raises `IndexError`
before `_rpc_POST` is called, and `do_POST` has no try/except around `_viewer()`
at `:389`. `do_GET` is protected at `:599`; `do_POST` is not. Reachable
unauthenticated. The client gets a dropped connection rather than a 500.

**F49 · S2 · `handle_rpc` crashes on a non-integer `pageSize`.** `aimboard/a2a.py:1310`,
`:1317`, `:1319` call bare `int(params.get(...))`. `{"pageSize": "abc"}` raises
`ValueError` through `handle_rpc` into `_rpc_POST` (no try/except), killing the
handler thread — where the module elsewhere implements `-32602 Invalid params`
carefully (`a2a.py:1182-1192`).

**F50 · S2 · Business refusals are returned as HTTP 200.** `aimboard/cli.py:487-494`
defaults `status=200`, and callers at `:427-455` use the default, so "started
without `--allow-write`" and "not in the allow-list" are 200 responses whose body
says `ok: false`. The `/api/*` 404 rule at `:530-546` exists so a monitoring
consumer can branch on the status line; these two rules disagree about that.

**F51 · S2 · Unknown `/api/*` returns an HTML error page on POST.** `aimboard/cli.py:423-425`
uses `send_error(404)`, which emits HTML; only `do_GET` implements the
JSON 404 (`:541-546`). `AGENTS.md:49-51` states the JSON-404 rule without
qualifying it by method.

**F52 · S3 · The digest is still metadata-only and unscoped, and now nothing
consumes the revision that would fix it.** `aimboard/fabric.py:16-27` hashes
`size\0mtime_ns` for every file under `registry.json`, `channels/`, `outbox/`,
`plan/` — including `channels/*/private/*.jsonl` (never rendered) and every
outbox body. `design/12` §1.4 already names this; the probe's addition is that
`/api/revision` (which correctly models `stale`) has **no client**: `web/src`
never calls it and the front-end's staleness path uses `/api/digest`
(`web/src/stores/board.js:458`) instead. So the instrument built to fix the
staleness problem is not wired to the surface that has the problem.

**F53 · S3 · `_origin_ok` builds its allow-list from the client-supplied `Host`
header.** `aimboard/cli.py:329-336`: `allowed = {f"http://{host}", …}` where
`host = self.headers.get("Host")`. A caller that controls both `Host` and
`Origin` satisfies the check trivially. The docstring at `:245-246` presents this
as CSRF protection.

**F54 · S3 · The MCP wrapper is a strictly wider writer than the HTTP allow-list
and has weaker controls.** `aimboard/mcp.py:20-24` `_run_cli` executes `bin/aim`
with arbitrary `argv`; `:1-7` claims it "never appends to a log", which is true of
`mcp.py` and not of what it spawns. Compare `/api/command`'s seven verbs
(`cli.py:262`). `_supports_actor` (`:45-62`) classifies verbs by a substring test
on `--help` output — textual, not structural.

**F55 · S3 · `visible_tasks` silently exempts a task whose channel cannot be
resolved.** `aimboard/gate.py:66-73`: `by_id.get(task.get("channel"), default)`
falls back to `gate_channel`'s answer, whose last resort is `channels[0]`
(`gate.py:49`) — the same positional default as F37. A draft in a renamed or
misspelled channel is judged by an unrelated channel's phase.

**F56 · S3 · A comment asserts a measured fact the code no longer satisfies.**
`aimboard/a2a.py:588-596` records that `created_by` "is not among [PLAN_FIELDS]";
the probe found `created_by` *was* added at `aimboard/const.py:17`, so the two
visibility rules (`gate.py:70` vs `a2a.py:710-745`) genuinely diverge on the
owner≠creator case. A stale comment that claims a divergence is inert is worse
than no comment: the next reader will not re-check it.

**F57 · S4 · No response sets `X-Content-Type-Options: nosniff`, and unknown
suffixes are served as `application/octet-stream`.** `aimboard/cli.py:263-266`,
`:507`, `:487-494`. Exploitability depends on what can be written into `web/dist`;
the missing header is a fact.

**F58 · S4 · `/state.json` is named as if it were the state and carries two
keys.** `aimboard/cli.py:556-565` returns `{"digest", "generated_at"}` only. The
server-rendered shell's poller reads it as a digest (`aimboard/web.py:121-125`),
which works, but a consumer treating the name as the contract gets a two-key
object and no error.

**F59 · S3 · `/api/state` loads the whole fabric twice per request.**
`aimboard/cli.py:274` and `:293` each call `load_fabric`, which re-reads and
re-hashes every channel, ledger, task log and outbox file. Under
`ThreadingHTTPServer` this multiplies.
