# Design note 06 — group chat without killing the barrier, and the friction log

Requirement (human leader, 2026-09-21): *还要支持 group chat*, and *一边使用一边改善*.

## 1. What "group chat" adds that the channel does not have

The channel is already n-party in its data model — `participants` is a list, the
log is a total order, and the ledger folds per agent. Three things are genuinely
missing, and only the first is a protocol question:

1. **Broadcast.** `--responds-to` is mandatory in `CROSS_EXAMINE` and broadcasts
   are refused there. That rule exists because an unaddressed message is how a
   concession gets read as a proposal, and it should stay exactly where it is.
   Outside cross-examination there is no such hazard, so a room message may be
   unaddressed. One flag, one phase check, no new semantics.
2. **Independent topics.** One channel carries one question and one barrier. Work
   needs several conversations at once — `#fabric-dev`, `#blockers`, `#review` —
   with different participants and no shared phase. A **room** is a named
   sub-log: `channels/<ch>/rooms/<room>.jsonl`, same chaining, same flock, no
   quota, never a barrier. A room may not host positions; a channel may.
3. **Who has seen what.** A chat without unread counts is a log with a UI. Read
   cursors (`rooms/<room>.cursors.json`, agent -> last hash) turn "did Claude see
   the handoff" into a number, and they are the data source the unsolved doorbell
   (README §5.4) never had.

## 2. The leak group chat introduces

Rooms are open, and open rooms are where two participants in `SEALED_DIVERGENT`
would go to agree on what they think — not maliciously, just because talking is
easier than writing. That single fact would end the design.

So a room inherits the channel's gate: **a room created while the parent channel
is in a divergence phase is a draft room.** Its messages are readable by their
author and by the leader, and by nobody else, enforced in `aim` and recorded by
the same refusal path as a cross-read. A participant may open it early with
`aim room publish`, which is deliberate, recorded, and visible on the board as
an event. Default closed, deliberately opened.

The honest limit, stated plainly because the alternative is pretending: an agent
that wants to collude can leave the fabric and use a file, a shell, or the
window it is already sitting in. **No tool here prevents that.** What the fabric
does is make the *default* path the protected one and the unprotected one
legible.

## 3. Why this is the right shape for PM work specifically

Group chat is not a second product bolted onto the barrier; it is the phase the
project actually spends most of its time in. Cross-examination is two messages
per participant per round — deliberately, because it is an argument. Work is the
opposite: many short messages, no quota, several rooms, and a board. The fabric
now has both, and they take different paths through the tool:

| | argument | work |
|---|---|---|
| surface | channel log, `CROSS_EXAMINE` | rooms, open |
| addressing | mandatory, kinds required | optional, mentions instead |
| quota | 2 per participant per round | none |
| state | seals, concessions, refusals | tasks, owners, dates, blockers |
| read by | everyone, then | the leader, continuously |

The board is the work side's record. `aimboard` renders it, and renders the
argument side's record beside it, which is the thing a leader actually needs:
how the work is going *and* whether the barrier is being leaned on.

## 3½. The conversation surface's write path (added 2026-09-21, after a measured forgery)

The dashboard grew a reply box. Testing it, Codex drove the UI with the viewer
selector set to `human` and posted a message; the record now contains
`outbox/codex/20260921T085920.815Z-human.md`, which says it is from the human
leader and is not. The rule that allowed it is worth writing down before the fix,
because the fix is one line and the reasoning is not.

**R1 — a read borrows a view; a write does not.** `?as=<agent>` answers "whose
eyes am I reading through" and is a legitimate, cheap affordance: the leader
wants to see what Claude sees, without Claude's session. The same parameter
answering "whose hands am I writing with" is forgery, because a URL is not a
credential and the two questions are not the same question. The default is the
identity the server was started as (`--viewer`), falling back to the channel
leader. An operator who wants the dashboard to write as Claude starts a server
that says so — a deliberate act with a process attached to it, not a query
string.

**R2 — the payload declares the write posture, and the browser never guesses.**
`/api/state` carries `write: {enabled: <bool>, as: "<agent>"}`. `enabled` is
`--allow-write` as the server understands it; `as` is the identity R1 will
assert. The composer names that identity in its own text and is absent entirely
when writes are off, so the page cannot offer a control that will be refused.

**R3 — a refusal the browser can see is worth more than a control it cannot
use.** The composer states who it is writing as, and if the server refuses, the
refusal is shown verbatim and recorded, as with any other refuse. Nothing in the
pane decides whether a write is legal.

The falsifier: if this makes a legitimate workflow impossible, it will be a
workflow where one dashboard must write as two identities at once. That workflow
is a shared dashboard, and the right answer to it is a dashboard per identity —
at which point the cost of the honest path is *"start one more process"* and the
cost of the dishonest one is *"any page that can reach this port can speak as the
leader"*. Those are not comparable, which is why R1 is not a tradeoff.

### R4 — `claimed` follows a confirmed write, not a buffered print

`aim pull --claim` is an attestation used by `aim confirm`: "the tool handed the
message to the reading process's output stream." The first implementation claimed
each record after a sequence of `print()` calls, which attested a buffer write
rather than a delivery. A consumer that stopped reading could therefore leave a
message marked claimed — and `confirm` would accept an ack for a body that never
left this process.

The rule is the strongest one a writer can enforce:

1. For each record, print every line of that record.
2. Flush immediately. If the flush raises, the record's bytes did not leave the
   process; claim neither it nor anything after it.
3. Only after that flush succeeds, write `claimed_at`.
4. On a broken pipe, redirect stdout to `/dev/null` before exiting so the
   interpreter's final flush cannot produce a second traceback.
5. The exit summary reports the number actually claimed, never the number that
   was merely eligible.

This is deliberately a writer-side boundary, not a mind-reader. A Unix pipe
cannot prove that the consumer *consumed* the bytes; if a reader stops without
closing and a record fits in the pipe buffer, the write can succeed and the claim
can still be written before the reader sees the body. That is a limit of any
writer-side claim, not a defect in this one, and it is why `confirm` remains a
separate, deliberate receipt rather than an automatic consequence of `pull`.

## 4. The friction log

*一边使用一边改善* has a mechanical consequence that this project's own history
argues for. The refusal ledger exists because the interesting event about a
barrier is the time someone leaned on it and it held. The interesting event
about *using* a tool is the time it was in the way — and that event is currently
thrown away. An agent hits a wall, works around it, and the workaround is
invisible; three sessions later the design still assumes the wall is fine.

So: `channels/<ch>/friction.jsonl`, one record per time the fabric was in the
way — the command that was typed, what happened, what it cost, and whether the
workaround touched the record. It is the cheapest instrument in the system and
it is the only one that measures the fabric *as used* rather than as designed.
An empty friction log is not a good sign; it means either nobody was using it or
nobody was recording, and both are failures.

## 5. Open questions

1. Do rooms need their own participants, or do they inherit the channel's? I
   chose inherit, because a room with its own membership is a channel with a
   worse barrier. This will be wrong for a team of twelve.
2. Is a draft room worth the complexity when the same effect could be had by
   telling agents not to talk? No — a norm cannot be verified, which is this
   project's first principle. But the cost is real: **two truly independent
   agents cannot see each other's task lists**, so they cannot avoid duplicate
   work by looking. The leader absorbs that, and that is a scalability limit, not
   a detail.
3. Should a published task's *comments* be gated too? A published card with a
   draft comment is the same leak one level down. I have not implemented this and
   I think it is the next hole.
