# 14 — A2A gaps: one table, read off the code

`design/07` argues that A2A's `Task` and ours are not the same object. This note
does the smaller, harder job: it says exactly which A2A states and capabilities
this fabric cannot express, and which of ours have no A2A counterpart — with a
`file:line` or a command whose result *is* the proof, so every row can be checked
rather than believed.

**It is derived from the code, not from the prose.** `README.md` §10 and
`design/07` were both written before `aimboard/a2a.py` existed, and §10 still
says every operation is *missing*. That is now false: `aimboard/a2a.py` carries
the eleven operations, the nine error codes, the `TaskState` enum and the four
push-config operations, and `aimboard/cli.py` serves them at `POST /rpc`. Where
the prose and the code disagree, this note sides with the code and says so.

## 0. How to read the evidence, and why some rows are commands

`bin/aim` and `aimboard/cli.py` were being edited by other sessions while this
note was written — `bin/aim`'s sha changed twice inside ten minutes, and a fixed
line number was wrong within one edit. So **every row against `bin/aim` or
`cli.py` names a search anchor, not a line number**: `bin/aim § rg -n '^PHASES ='`
means "run that command and the line it prints is the evidence". `aimboard/a2a.py`
was stable throughout and keeps `file:line`.

Recorded at the sha below (re-run `sha256sum`; expect `bin/aim` to have moved):

| file | sha256 (at read time) | evidence form |
|---|---|---|
| `bin/aim` | `1326e1950fdc42386a4c6c2359040d0f7b85d3639bc5284ef0bab451a4f2852e` | search anchor |
| `aimboard/a2a.py` | `2c4f82c01e9a76608062cb7de4601697c4ceae24805ccc04eb76ff7abb5c799b` | `file:line` |
| `aimboard/cli.py` | `756fb505e900d1e2194a63f640457b6ca227eb41322ac27d4183df16451e50e0` | search anchor |

## 1. The table

Direction key: **A2A→ours** = an A2A state/capability this fabric cannot express.
**ours→A2A** = a fabric state/capability A2A has no word for.

| # | direction | A2A object / our object | what the code does today | evidence | verdict |
|---|---|---|---|---|---|
| 1 | A2A→ours | `TASK_STATE_FAILED` | never emitted: no fabric status maps to it and no code path returns it | `aimboard/a2a.py:622` (`STATUS_TO_STATE`, no `failed` key); listed in `aimboard/a2a.py:637` (`STATES_WE_CANNOT_EXPRESS`) | **cannot express** |
| 2 | A2A→ours | `TASK_STATE_REJECTED` | never emitted; `dropped` is a withdrawal the owner chose, not a server rejection | `aimboard/a2a.py:637`; `dropped` → `TASK_STATE_CANCELED` at `aimboard/a2a.py:629` | **cannot express** |
| 3 | A2A→ours | `TASK_STATE_AUTH_REQUIRED` | never emitted; with no auth there is no "credential needed" condition to represent | `aimboard/a2a.py:637`; `"authentication": "none"` at `aimboard/a2a.py:218` | **cannot express** |
| 4 | A2A→ours | `TASK_STATE_UNSPECIFIED` | reachable only as the `.get(…, "TASK_STATE_UNSPECIFIED")` fallback for an unknown status; no fabric status *means* "unset" | `aimboard/a2a.py:803` (the fallback in `a2a_task`) | **cannot express** (fallback, not a state) |
| 5 | A2A→ours | `SendMessage` | `UnsupportedOperationError`; `aim push` writes an *outbox* record, which is not an A2A `Message` and has no `contextId`/`role`/`parts` on the wire | `aimboard/a2a.py:1279` (`UNSUPPORTED["SendMessage"]`); `bin/aim § rg -nF 'def cmd_push'` | **cannot express** |
| 6 | A2A→ours | `SendStreamingMessage` | `UnsupportedOperationError` over `text/event-stream` (one event, then close); the card declares `streaming: false` | `aimboard/a2a.py:1277` (`STREAMING`), `aimboard/a2a.py:186`; `cli.py § rg -nF 'def _rpc_POST'` | **cannot express** |
| 7 | A2A→ours | `SubscribeToTask` | same path as row 6 — no subscription, no stream to subscribe to | `aimboard/a2a.py:1277`, `aimboard/a2a.py:1282` | **cannot express** |
| 8 | A2A→ours | `CancelTask` | `UnsupportedOperationError`: `dropped` is a status a task moves to, not a cancel operation a client invokes; unresolved blockers are refused with `TaskNotCancelableError` | `aimboard/a2a.py:1281`; `aimboard/a2a.py:347`; `bin/aim § rg -nF 'def cmd_task_move'` | **cannot express** |
| 9 | A2A→ours | extended Agent Card | `extendedAgentCard: false`; `GetExtendedAgentCard` returns the same card an anonymous caller gets | `aimboard/a2a.py:200`; `aimboard/a2a.py:1322` | **cannot express** |
| 10 | A2A→ours | push-notification *delivery* | the config object is real (four operations, `pushNotifications: true`), but nothing opens an HTTP client to POST to the configured `url`; delivery is `bin/aim-doorbell-hook`, which reads `outbox/` on a session's next turn | `rg -n 'urlopen\|urllib.request\|http.client\|requests' aimboard bin` → only `from urllib.parse import parse_qs` at `cli.py § rg -nF 'from urllib.parse'`; `bin/aim-doorbell-hook:6` | **partial** (object yes, transport no) |
| 11 | A2A→ours | authentication / per-caller authorization | no credential is checked; the surface's identity is the *server's* viewer, selected by the query string, so a caller can ask to be read as any registered agent | `"authentication": "none"` at `aimboard/a2a.py:218`; `cli.py § rg -nF 'def _viewer'` returns `?as=` verbatim | **cannot express** |
| 12 | A2A→ours | `A2A-Version` negotiation / `VersionNotSupportedError` | no header is parsed and the error is never emitted; `PROTOCOL_VERSION` is a constant the card states, not a request the server negotiates | `rg -n 'A2A-Version' aimboard bin` → comments only at `aimboard/a2a.py:36`, `aimboard/a2a.py:322`; `-32009` reserved at `aimboard/a2a.py:251` and unused | **cannot express** |
| 13 | A2A→ours | `Part` variants `raw` / `url` / `data` | every `Part` is constructed with a single `text` key; no binary, URL-referenced or structured-data part | both constructors — `aimboard/a2a.py:669` (history), `aimboard/a2a.py:817` (artifact) — emit `{"text": …, "mediaType": "text/plain"}` | **cannot express** |
| 14 | A2A→ours | `Message.referenceTaskIds[]`, `Message.extensions[]` | never emitted | `rg -c 'referenceTaskIds' aimboard bin` → no matches | **cannot express** |
| 15 | A2A→ours | streaming artifact events (`TaskArtifactUpdateEvent{append, lastChunk}`) | a task exposes one static artifact (the acceptance condition) and no incremental artifact stream | `aimboard/a2a.py:813` (single artifact); `rg -c 'lastChunk\|TaskArtifactUpdateEvent' aimboard bin` → no matches | **cannot express** |
| 16 | A2A→ours | `TaskStatusUpdateEvent` | state is read when asked (`GetTask`/`ListTasks`); no event is ever pushed | `rg -c 'TaskStatusUpdateEvent' aimboard bin` → no matches; reads at `aimboard/a2a.py:837`, `aimboard/a2a.py:889` | **cannot express** |
| 17 | A2A→ours | `TASK_STATE_INPUT_REQUIRED` as "the agent needs *the client* to supply input" | we emit the value, but only by collapsing two different facts into it (rows 25–26); a client told `INPUT_REQUIRED` cannot tell whether to send a decision or wait for a peer's work | `aimboard/a2a.py:626` (`review`), `aimboard/a2a.py:627` (`blocked`) | **lossy** |
| 18 | ours→A2A | phases `SEALED_DIVERGENT … CLOSED` and the enforced gate | no A2A object models a stage at which reading a peer's work is forbidden; registered as extension `sealed-divergence/v1` | `bin/aim § rg -n '^PHASES =\|^PHASE_RULES =\|def gate('`; `aimboard/a2a.py:61` | **no counterpart** |
| 19 | ours→A2A | the seal: summary + claims with `confidence`/`kill_if` + a hash of the frozen private log | A2A has no commitment device and no "reasoning frozen before exposure"; the seal carries `private_log_bytes`/`private_log_sha256`/`private_log_hashes` so later edits are caught | `bin/aim § rg -nF 'def cmd_seal'` and `rg -n 'private_log_bytes'`; `aimboard/a2a.py:61` describes this as an extension | **no counterpart** |
| 20 | ours→A2A | the refusal ledger with `class` = `barrier` \| `form` \| `unrecorded` | A2A defines nine errors and none is "a well-formed request refused because of who was asking"; the binding says so itself | `bin/aim § rg -nF 'def _record_refusal'` and `rg -nF 'def die('`; `aimboard/a2a.py:382` (`NATIVE_ONLY`) | **no counterpart** |
| 21 | ours→A2A | restatement refusal: >50% 8-gram overlap with a peer is refused unless `--echo-ok` | no A2A error or field covers "this message restates a peer" | `bin/aim § rg -n '^ECHO_RATIO_LIMIT'` and `rg -nF 'restates a peer verbatim'` | **no counterpart** |
| 22 | ours→A2A | bounded cross-examination: a fixed `kind` vocabulary and two messages per participant per round | A2A has messages but no round budget and no typed-floor vocabulary | `bin/aim § rg -n '^CROSS_EXAMINE_KINDS\|^MAX_MSGS_PER_ROUND'` and `rg -nF 'already used your'` | **no counterpart** |
| 23 | ours→A2A | planning fields: estimate, due date, dependency edge, milestone, priority | carried outside the core in `metadata.aim.planning`; extension `planning/v1` registers the claim | `bin/aim § rg -n '^TASK_STATUSES\|^TASK_EVENTS'`; `aimboard/a2a.py:71`, `aimboard/a2a.py:822` | **no counterpart** |
| 24 | ours→A2A | `ready` as distinct from `backlog` | both map to `TASK_STATE_SUBMITTED`; A2A has one word for "accepted, not started" and we have two different facts (shaped vs merely filed) | `aimboard/a2a.py:623`, `aimboard/a2a.py:624` | **no counterpart** (A2A's word is coarser) |
| 25 | ours→A2A | `blocked` — waiting on a *peer's work*, with a `--reason` | maps to `TASK_STATE_INPUT_REQUIRED`; A2A has no dependency word, which is what `planning/v1` exists for | `aimboard/a2a.py:627`; `bin/aim § rg -nF 'requires --reason'` (the refusal inside `cmd_task_move`) | **no counterpart** |
| 26 | ours→A2A | `review` — waiting on a *reviewer's decision* | maps to `TASK_STATE_INPUT_REQUIRED`, the same value as row 25 | `aimboard/a2a.py:626` | **no counterpart** |
| 27 | ours→A2A | the transition `review → doing` meaning "changes requested" | A2A models states, not transitions; the meaning of the edge has no field | `bin/aim § rg -n '^TASK_FLOW'` (its comment: `# back to doing = changes requested`) | **no counterpart** |
| 28 | ours→A2A | receipts: a sent message records byte count and `body_sha256`, and the recipient acknowledges the verified bytes | A2A `Task` states do not carry "delivered but unread" or "bytes verified"; extension `receipts/v1` | `bin/aim § rg -nF 'def cmd_push'` and `rg -nF 'def cmd_confirm'` (`body_sha256`, `ack_required`); `aimboard/a2a.py:80` | **no counterpart** |
| 29 | ours→A2A | append-only hash-chained logs + `aim verify` (TAMPER on a broken `prev` or a content mismatch) | A2A `history` is an ordered list with no chain rule and no verify operation | `bin/aim § rg -nF 'def cmd_verify'` (checks `prev`/`hash` per record); written by `append_chained` | **no counterpart** |
| 30 | ours→A2A | retraction as an append (`retracted` event) rather than editing history | A2A has no retraction and no "never edit the chain" policy to violate | `bin/aim § rg -nF 'def cmd_task_retract'` | **no counterpart** |
| 31 | ours→A2A | work items born `draft`, exposed only by `publish`, gated by the phase | A2A task visibility is per-caller authorization only; there is no draft/published axis | `bin/aim § rg -nF 'def _visible_to'` and `rg -nF 'def cmd_task_publish'` | **no counterpart** |
| 32 | ours→A2A | the *withheld count* on the leader's board | the board publishes how many items are hidden; the A2A surface must not, because §3.3.2 forbids distinguishing "not found" from "not authorized" | `aimboard/gate.py:59`; `bin/aim § rg -nF '"withheld": withheld'`; A2A surface emits no count at `aimboard/a2a.py:889`, and `hidden_count` is defined but deliberately never called from the surface (`aimboard/a2a.py:748`) | **conflict, resolved per surface** |
| 33 | ours→A2A | the human leader is an audience, not a participant: `kind == "human"` reads everything | A2A has roles on messages but no "the reader of the record is not a party to it" role | `bin/aim § rg -nF 'def gate('` (leader exempt); `aimboard/a2a.py:710` (`task_visible` human bypass) | **no counterpart** |
| 34 | ours→A2A | `GetTask`/`ListTasks` answer `TaskNotFoundError` for a draft the caller may not see, before any lookup | this one is *compliant*, not a gap — recorded so the table is not one-sided: we implement §13.1's auth-before-lookup rule | `aimboard/a2a.py:837` (`get_task`: gate before lookup), `aimboard/a2a.py:889` | **aligned** |

## 2. The state crosswalk, in the two directions the card names

A2A's nine `TaskState` values against `TASK_STATUSES` (`bin/aim § rg -n '^TASK_STATUSES'`)
and `STATUS_TO_STATE` (`aimboard/a2a.py:622`):

| A2A state | ours | note |
|---|---|---|
| `TASK_STATE_UNSPECIFIED` | — | fallback only (#4); no status means "unset" |
| `TASK_STATE_SUBMITTED` | `backlog`, `ready` | **`ready` has no A2A word of its own** (#24) |
| `TASK_STATE_WORKING` | `doing` | exact |
| `TASK_STATE_COMPLETED` | `done` | exact; but our `done` has a blocker check A2A does not require |
| `TASK_STATE_FAILED` | — | **A2A-only** (#1) |
| `TASK_STATE_CANCELED` | `dropped` | ours is a deliberate withdrawal, not a cancellation |
| `TASK_STATE_INPUT_REQUIRED` | `review`, `blocked` | **both ours-with-no-A2A-word** collapse into one value (#17, #25, #26) |
| `TASK_STATE_REJECTED` | — | **A2A-only** (#2) |
| `TASK_STATE_AUTH_REQUIRED` | — | **A2A-only** (#3) |

In the card's own words: **`ready`, `blocked` and `review` are ours with no A2A
word; `AUTH_REQUIRED`, `REJECTED` and `FAILED` are A2A's with no ours.**
`INPUT_REQUIRED` is the one value we reach only by merging two of ours.

## 3. Where this fabric is ahead, and it is not a consolation prize

Three of the four mechanisms `README.md` §2 builds on the barrier have no A2A
expression at all, and the binding states them in the card rather than hiding
them:

- **The barrier** (rows 18–19): A2A has no phase in which reading is forbidden.
  Its `Task` is created by a server and watched by a client; there is no second
  participant whose independent position must be protected. This is the largest
  semantic difference in the table, and `sealed-divergence/v1`
  (`aimboard/a2a.py:61`) is the entire acknowledgement A2A can carry.
- **Refusals as evidence** (row 20): A2A's nine errors tell a client *why a call
  failed*. Our ledger tells a reader *that someone tried* — the record survives
  in a hash-chained file and `aim verify` (`bin/aim § rg -nF 'def cmd_verify'`)
  makes it tamper-evident. A2A requires nothing of the sort, which is exactly why
  this is a capability and not a conformance gap.
- **Seals** (row 19): a commitment device with a falsifier (`kill_if`) and a
  frozen-prefix hash. There is no A2A object to map it onto, and mapping it onto
  `Message` would lose the property — the commitment is to a *private* log the
  peer cannot read yet.

The two genuine self-criticisms, stated plainly: **the surface cannot
authenticate anyone** (row 11) and **it cannot push** (row 10). Both are the same
kind of finding — the object exists, the thing that makes it a capability does
not — and both are why the card pins reachability to `localhost-only`
(`aimboard/a2a.py:219`).

## 4. Rows that could not be verified

These are marked rather than guessed:

- **`not verified` — "a test asserts every status in the state machine appears
  exactly once" (card T-0205 acceptance).** No such test exists today:
  `rg -n 'TASK_STATUSES|TASK_FLOW' tests/` returns no matches, and
  `tests/test_a2a_conformance.py` pins `TASK_STATES` (the A2A enum) but not the
  two-way mapping. `aimboard/a2a.py:637`'s comment calls the table "the constant
  it can read rather than re-deriving" — the assertion is still owed.
- **`not verified` — the README half of the acceptance line.** `README.md` is
  being edited by another session and is outside this card's write set. As read
  here, its §10 table says every operation is *missing*, which
  `aimboard/a2a.py` (`OPERATIONS` at line 256; seven backed operations in
  `handle_rpc` at line 1286) and `cli.py § rg -nF 'path == "/rpc"'` contradict.
  This note is the checkable replacement; the README row should be updated by
  whoever owns that file, not by this card.

## 5. How to re-check a row

    cd /root/tmp/agent-im
    sha256sum bin/aim aimboard/a2a.py aimboard/cli.py     # compare to §0
    rg -n 'STATES_WE_CANNOT_EXPRESS|STATUS_TO_STATE' aimboard/a2a.py
    rg -n 'UNSUPPORTED|STREAMING' aimboard/a2a.py
    rg -n 'urlopen|urllib.request|http.client|requests' aimboard bin   # row 10: expect only urllib.parse
    rg -n 'A2A-Version' aimboard bin                                   # row 12: expect comments only
    rg -nF 'withheld' bin/aim aimboard/gate.py                          # row 32
