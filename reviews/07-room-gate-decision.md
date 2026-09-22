# 07 — Room gate: a decision, and a bug the current test would enshrine

Author: `codex-orangement`. Evidence at fabric `81dc58f+dirty`, 2026-09-22T08:0xZ. Written after
the leader delegated decision authority ("you take full decision ... shape the project",
`20260922T075734.114Z-human`).

**Re-verified at `dbdd04e+dirty`**: `reviews/07-room-author-probe.py` → **3/4**, the failing row
still the author's. Written against `81dc58f+dirty`.

## 0. First, a correction I owe codex

I told codex that if rooms landed on the phase ladder "the room will inherit the same gate and be
unusable in SYNTHESIS/COMMIT, which is where every channel sits", and asked him to decide whether
a published room bypasses `channel_say`. **`design/06-group-chat.md` §2 answers that, and my
question was already answered before I asked it:**

> So a room inherits the channel's gate: **a room created while the parent channel is in a
> divergence phase is a draft room.** Its messages are readable by their author and by the leader,
> and by nobody else... A participant may open it early with `aim room publish`, which is
> deliberate, recorded, and visible on the board as an event. **Default closed, deliberately
> opened.**

So the design has a third state I did not model: *draft, then deliberately opened*. There is no
"chat-capable phase" question. The room is the work surface, it is closed by default, and opening
it is one recorded deliberate act. My question is withdrawn; the decision below is about the
implementation of §2, not about its shape.

## The decision

**The room gate keeps its phase-independent `visibility` semantics, gains the author exemption,
and the missing half is `aim room` verbs — not a phase check.**

Reasoning, in the order the evidence forced it:

1. **A published room readable by a peer during divergence is the documented feature.** §2 calls
   `aim room publish` "deliberate, recorded, and visible on the board as an event". A rule that
   stopped a published room from being read in divergence would make that verb a no-op. So
   `visible_rooms`' "published → readable" branch is correct as written.
2. **Therefore `tests/test_room_gate.py`'s prescribed remedy is wrong and must not be
   implemented.** Its closing lines say: *"A fix must make the fourth row false by keying the gate
   on the channel's phase, and must record a publish in the ledger."* The second clause is right.
   The first would delete the capability §2 specifies. The test's third row ("THE FINDING:
   visibility 'published' alone lets a peer read a divergence-phase room") is not a leak; it is §2
   working. A test that pins correct behaviour as a finding will get "fixed" by whoever trusts it.
3. **What is actually missing is the verb.** `rg -c room bin/aim` → **0**. `aim room` is not a
   subcommand (the parser lists 24 verbs; none is `room`). `tests/test_room_gate.py`'s own
   docstring says the only way to produce `visibility: "published"` is to hand-write the file,
   "which is neither recorded nor on the board". So §2's deliberate path has no implementation:
   default closed is enforced, deliberately opened is impossible. `channels/*/rooms` exists for no
   channel and `channels[].rooms` is absent from `/api/state`, so `visible_rooms` is currently
   dead code.

## C7 — a draft room is invisible to its own author

New, verified, and not covered by the existing test.

`design/06` §2 requires a draft room's messages to be "readable by **their author** and by the
leader, and by nobody else". `aimboard/gate.py:77-84`:

```
def visible_rooms(state, channel, viewer):
    for room in channel.get("rooms", []):
        if room["visibility"] != "published" and walled_off(state, channel, viewer):
            hidden += 1
            continue
```

`walled_off` is true for a participant in a divergence phase, and there is no author exemption —
so the room's own author is excluded. The same file implements exactly that exemption for tasks
(`gate.py:69`: `... and viewer not in (task.get("owner"), task.get("created_by"))`), which is why
this reads as an omission rather than a policy.

**Reproduction** (`reviews/07-room-author-probe.py`, throwaway `AIM_ROOT`, read-only otherwise):

```
  alpha(author)={'nofield': False, 'typo': False, 'pub': True}
  beta(peer)   ={'nofield': False, 'typo': False, 'pub': True}
  leader       ={'nofield': True,  'typo': True,  'pub': True}
  FAIL  design/06 §2: the AUTHOR can read their own draft room
  3/4 checks passed
```

`tests/test_room_gate.py` checks `beta` and `leader`. It does not check `alpha`. **The row the
design sentence names first is the row the acceptance does not pin.**

**Acceptance:** for a room with no `visibility` field in a divergence-phase channel, the author
reads it, the other participant does not, the leader does. Fails on the first clause today.

**Fix:** the `walled_off` branch gains the same author exemption as `gate.py:69`, keyed on the
room's message author (or a room-level `created_by`).

## Not a defect, recorded so it is not re-litigated

`visible_rooms` ignoring the phase is correct: `visibility` *is* the phase decision, made
deliberately and once, by a participant who chose to open the room early. The phase gate applies
to the *default* (no field → draft → peers excluded), which the first two rows of
`tests/test_room_gate.py` already prove.
