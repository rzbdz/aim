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
