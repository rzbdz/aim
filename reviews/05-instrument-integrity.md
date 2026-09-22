# 05 — The gate and the instrument

Author: `codex-orangement` (registered 2026-09-22T07:25:47Z; participant of no channel).
Fabric `81dc58f+dirty` when written, **re-verified at `dbdd04e+dirty`** (bundle built
2026-09-22T08:04:40Z, `stale: false`) — `python3 reviews/05-verify.py` → **12 checks, 11 pass,
1 fail**, every figure unchanged: `reports.blocked` 51 rows (24 done, 6 blocked, 1 review),
`drift` 87 with the same 15 withheld ids, seat totals 69/40/23. Revision-robust across both builds. All numbers re-derived from
`GET /api/state` and `aimboard/*.py` at 07:55Z. Nothing here is quoted from a peer's seal or
private log.

## 0. Disclosure, and a withdrawal

**Withdrawn at 08:05Z, and it was the headline of my first version.** I wrote that "the barrier
does not exist over HTTP" and told the leader that a bystander reads every sealed claim. Then I
read `design/06-group-chat.md:73`, R1:

> **a read borrows a view; a write does not.** `?as=<agent>` answers "whose eyes am I reading
> through" and is a **legitimate, cheap affordance**: the leader wants to see what Claude sees,
> without Claude's session.

`?as=` for reads is deliberate, documented, and reasoned. My framing was wrong. The reader who
wants to check me on this should read R1 first and my first draft second.

That also retracts my "disclosure" from 07:55Z: the six `?as=human` aggregate reads were a
sanctioned affordance, not a use of a hole, and I was wrong to present them as a lapse. What I
actually did wrong was the opposite of what I confessed — I read as the leader **without noticing
that I was**, because a forgotten parameter falls back to that seat and nothing in the payload
says so. That is S1b below.

What survives is narrower and, I think, worse for the design than a hole would be: R1 reasons
about borrowing a *view*, and one seat's view carries a *privilege over other people's closed
material*. R1 has two cases; it needs three.

## S1 — the read-borrowing affordance carries the leader's privilege over other participants' seals

`aimboard/gate.py:31-33`:

```
def may_see_peer_secrets(state, channel, viewer):
    """A sealed channel's claims, and a stranger's, are both out of reach."""
    return not walled_off(state, channel, viewer)
```

and `walled_off` (`gate.py:24-28`) returns `False` immediately for `kind == "human"`. So the
leader's seat is not walled, `secrets` is true, and `channel_payload` (`aimboard/api.py:36`) emits
every participant's `claims`. Measured, counts only:

| `as=` | walled_off | sealed entries carrying claim arrays | whose |
|---|---|---|---|
| `human` | False — leader exempt | **5** | every participant's seals |
| `codex` | True — participant, SYNTHESIS | 1 | his own (`who == viewer`) |
| `codex-orangement` | True — stranger | 0 | — |

So exactly one view in the fabric is not a perspective. "The leader wants to see what Claude
sees, without Claude's session" and "the leader may read Claude's sealed position before
cross-examination" are different powers, and R1's mechanism grants both together, because the
thing that decides is `viewer` and the borrowed viewer is unauthenticated by construction.

The fix is not to remove `?as=` — R1 is right that it is a cheap and legitimate affordance. It is
that `may_see_peer_secrets` should key on the **connection identity** (the server's `--viewer`,
which R1 already establishes as the write posture) and not on the borrowed `as`. Borrowing the
leader's eyes should show the leader's *board*; it should not publish the participants' *seals*.
The test that fails today:

    payload(as="human")             has 5 sealed entries with claims
    payload(as="codex-orangement")  has 0
    => assert payload(as=X)["sealed"]["claims"] does not depend on X unless X is the
       connection identity

## S1b — the unqualified read is the audience seat, and nothing says so

`aimboard/cli.py:312-315`:

```
def _viewer(self):
    if "as=" in (self.path or ""):
        return parse_qs(...).get("as", [args.viewer or ""])[0]
    return args.viewer or (load_fabric(...)["channels"][0]["leader"])
```

The fallback to the leader is exactly what R1 specifies ("The default is the identity the server
was started as (`--viewer`), falling back to the channel leader"), so this is not a coding error.
It is a **read-side** version of the hazard R1 already ruled on for writes. R1's falsifier is that
"the cost of the honest path is *start one more process*" against "any page that can reach this
port can speak as the leader"; for reads the dishonest path is not a forgery, it is a **default**,
and it is invisible. My own `trend.py` shipped with `?as=human` as its default, and I published
that seat's `recorded` and `with_history` as the project's numbers while my monitor sampled a
different seat. Nothing in the payload would have told a consumer that it had borrowed a seat: it
carries `write: {enabled, as}` (R2) and no `read.as`.

Proposed, and it is one field: `read: {"as": <viewer>, "borrowed": true|false}` in `/api/state`,
so a consumer that forgot the parameter can see what it got. Optionally make `--viewer` required
at startup rather than defaulting to `channels[0].leader`.

## S2 — every aggregate is folded from the redacted set, so the same URL reports a different project to each seat

`aimboard/api.py:61-88`:

```
tasks, hidden = visible_tasks(state, viewer, channel)     # 61 hidden
...
"reports": report_data(tasks, state["milestones"], ...),  # folded from the ALREADY-FILTERED dict
```

`report_data` (`aimboard/fold.py:136-182`) takes that dict and derives `recorded`,
`with_history`, `seed_only`, `series`, `throughput`, `median_cycle`, `blocked` and the
per-milestone `done`/`total` from it. Same endpoint, one string changed:

| `as=` | visible | withheld | recorded | with_history | seed_only |
|---|---|---|---|---|---|
| human | 156 | 0 | 69 | 3 | 87 |
| codex | 114 | 42 | 40 | 1 | 74 |
| codex-orangement | 95 | 61 | **23** | **0** | 72 |

The withheld *count* is public on purpose (`gate.py:59-61`: "the existence of a gate is not a
secret, only its contents are"). The aggregate is not. Consequences:

* M3's acceptance is "kanban + gantt + table + panels render **deterministically from real
  state**". This renders deterministically from *the viewer's* state. The Reports pane is a
  different project for each seat.
* The only seat that sees the record is the leader's — i.e. the number is visible to the person
  being reported to and to nobody who could be held to it. For a boss this reads as reassuring
  and is actually blindfolding everyone else.
* **It defeated my own supervision.** I published "opened 69, completed 3, 4% closed" from the
  leader's seat and diffed `recorded` from my own samples. The two numbers in one paragraph did
  not come from one record. That is my error (§6), but the API made it invisible: nothing in
  the payload says which of these it is.

The right shape is compute-then-redact: fold over the full record, then drop the rows you must
not see, and either keep the global totals (they are not secret — the count of a gate is
already published) or label them `visible_to_you`. Today the payload mixes both policies:
`withheld_tasks` and `unacked` (24 for all three seats) are global; `tasks` and `reports` are
local; and `drift` (§3) is global. Three policies in one object.

### S2 in the field: my own monitor missed two completions while it was running

The cleanest evidence for S2 is not the table above; it is my instrument failing.

* **07:40:34Z**, `Reports` pane, viewer `human` (screenshot `.dbg/orchestrator/shot_reports.png`):
  `throughput (last 7 days) = 1`.
* **08:02:07Z**, `?as=human` sampled directly: `throughput = [["2026-09-22", 3]]`.

Two completions were recorded in between. My monitor polled every 20s across that entire interval
and its window line read **`completed +0`** the whole time, because it was reading `with_history`
from my own seat, where the field is structurally 0. The monitor was not unlucky; it was measuring
a different view of the same URL, and nothing in the payload would have told it.

I have fixed it the only way available today: the monitor now also samples `?as=human` and writes it
under a `borrowed` sub-object that is never summed into the viewer's fields, and `trend.py` computes
the window from the borrowed ends when both exist and reports **`completed unknown`** when they do
not — because "I did not sample it" and "nothing completed" are different facts, which is the rule
this project already applies to `/api/revision`.

Note what the fix required: an undeclared identity switch inside my own tooling, plus a label
invented in my own log format, because the payload has `write: {enabled, as}` (R2) and no
`read: {as, borrowed}`. That is S1b's one-field proposal, and this is the concrete cost of its
absence.

## S3 — `drift` is the one payload key that skips the gate

`aimboard/api.py`, in `payload()`, every key is either identity-free or built from
`gate_channel`/`visible_tasks`/`conversation_view`. One is not:

```
"drift": drift(state["seed_tasks"],
               state["channels"][0]["tasks_recorded"] if state["channels"] else {}),
```

`state["seed_tasks"]` is the raw plan, unfiltered. For `?as=codex-orangement`:

* `visible_tasks` withholds 61 task ids from me.
* `drift` names **87** plan ids, **15 of which are in that withheld set**:
  `T-0010 T-0011 T-0012 T-0013 T-0014 T-0015 T-0018 T-0020 T-0021 T-0022 T-0023 T-0024
  T-0025 T-0026 T-0027`.
* The `drift` array is byte-identical for all three seats — so it is not merely under-filtered,
  it is not in the redaction path at all.

Scope, stated honestly: these 15 are **plan-only** — no channel store holds them, so what leaks
is the *plan's* id set and promised status, **not** a withheld store task's title. `visible_tasks`
hides them because `task.get("visibility") or "draft"` defaults to `draft` (`gate.py:68`), so
the gate deliberately treats an unmarked plan item as a draft position and hides it; `drift`
then names it. I am not claiming a title leak. I am claiming that the payload a stranger
receives contradicts the gate's own decision about the same 15 items, and that the decision
about whether plan ids are public was never made — the key simply has no gate on it.

The wrong-direction risk is worse than the leak. `drift` is the *only* flag that would tell the
team the plan and the store have parted; if a reader learns to distrust it, the one instrument
that measures "the plan is a promise" goes quiet.

Fix: pass the filtered task set (and the withheld count) into `drift`, or rename the key to
`plan_drift` and document it as global — but pick one and write it in `design/06`.

## S4 — `drift` compares the plan against one channel's store, chosen by position

Same line. `state["channels"][0]` is `barrier-v0` (order: `barrier-v0, dev, hello, s2-scratch,
s2-scratch2`), which holds **2** recorded tasks. The store holding **69** of the 71 recorded
tasks is `hello`, and it is never consulted. `aimboard/cli.py:56` repeats the same expression,
so the dashboard and the CLI share the assumption.

`fold.py:174` builds the merged task set from **all** channels — so the file knows to union the
stores two lines away from where it forgets to.

Why this is not yet a wrong number: `drift` iterates only over plan seeds, and I verified that
**zero** plan seeds are recorded in any store (87 seeds ∩ 69 recorded = ∅). So `drift`'s answer
is accidentally correct today. It stays correct only until someone records a plan-seeded task
into a channel that is not `channels[0]` — at which point it will report a completed item as
`store: None`, i.e. "the plan says done and the store has nothing", which is a false accusation
about the team from the instrument that is supposed to be the project's honesty check.

Fix: union the stores (as `fabric.py:174` already does), and index by the task's own `channel`.

## N1 — `reports.blocked` lists 24 completed tasks and one in review under a label that says "blocked"

`fold.py:169-172`:

```
if (h["task"].get("blocked_by") or h["task"].get("status") == "blocked")
```

Presence of a dependency, not an unmet one. Leader's seat, 51 rows by status: `done` 24,
`backlog` 14, `blocked` **6**, `ready` 5, `review` 1, `doing` 1. So **24 completed tasks and one
in review are listed under a heading that says "blocked"** — 25 of 51 rows. T-0035 is `review`
and its only blocker, T-0030, is `done`, so it is not blocked in any reading.

**In the rendered UI (screenshot `.dbg/orchestrator/shot_reports.png`, as-of 07:40:34Z, viewer
`human`, revision before the 07:57Z rebuild):** the sidebar header reads `108 open · 4 late ·
**6 blocked**`, and the Reports panel immediately below reads `what is waiting on what — **51 of
51** blocker row(s)`, with `T-0002` and `T-0003` listed and badged `done`. So the same page gives
two counts for "blocked" that differ by 45, and the larger one is titled "what is waiting on
what" while containing items that are finished. Whatever you call the 51, a user cannot reconcile
it with the 6 in the sidebar, and the first two rows tell them the count is not about blocked work
at all. The payload field is named `blocked` (`aimboard/fold.py:169`) and the UI label is "waiting
on"; the mismatch between those two names is the whole bug, and the sidebar's 6 is the number that
answers the question the panel is titled with.

This is the exact panel someone opens to answer "what is stuck". It answers "who has a
dependency", which is everyone. Fix: report `blocked_by` minus satisfied dependencies, and
never list a `done`/`dropped` task as blocked.

## §6 — my own errors in this report's lineage

Same class as the defects above, listed so nobody has to find them for me:

1. `trend.py` defaulted to `--state ...?as=human` while `monitor.py` sampled
   `?as=codex-orangement`. The "4% closed" line and the "+15 opened" line came from two
   different records. I have pinned both to one seat and labelled the seat in the output.
2. Earlier: `\s+` in a regex let an optional group cross a newline and dropped every
   participant after an `unsealed` line `#dev` printed 1 participant instead of 2.
3. Earlier: modelled only `participants`, so my org prototype printed the leader of all 5
   channels and `synthesizer-v0` as "in no channel".
4. Today: I claimed from a `grep SYNTHESIS bin/aim` that `manifest.synthesizer` had no consumer
   and was a dead structural role. It has two consumers (`bin/aim:787`, `:1085`) and the role is
   enforced. Withdrawn in full in §N3. Absence from a name match is not absence.

## §7 — supervision status (unchanged in substance since 07:39Z)

* **M2 group chat, due 2026-09-23 (tomorrow): 0 of 11 started** (10 backlog + 1 ready). `T-0020..T-0026`, `T-0155`
  are `backlog` (8 owned by `claude-session1`), `T-0027` is `backlog` and owned by `codex`.
  `channels/*/rooms` still does not exist for any channel. `/api/flow` still 404.
* **Multi-session / project management: zero tasks, no milestone, in `plan/plan.json`.**
  Not "late" — never scheduled. Acceptance criteria P1-P7 are in `reviews/02` and predate any
  implementation, on purpose.
* **Priority inversion, measurable:** by milestone, `M9` has 11 items `doing` and 12 `done`
  while `M2` has 0 `doing`. One day before M2's due date, the dashboard-as-product workstream
  is moving and the group chat has not been started. This is the leader's own complaint
  ("they are playing their own games") with a number under it.
* `reports.with_history` is 3 (leader) and `throughput` is empty: **no completion has ever been
  recorded in the completion series.** 71 recorded tasks, 0 completed transitions. The board
  draws 45 `done`; those are plan state, not recorded work.

## §8 — what would change my mind

* S1: `?as=` for reads is settled by design/06 R1 and I am not reopening it. What would change my
  mind here is an argument that the leader's exemption from `may_see_peer_secrets` **is** a view
  rather than a privilege — i.e. that "the leader wants to see what Claude sees" was always meant
  to include "and what Claude sealed before cross-examination". If that is the intent, R1 should
  say so, because its reasoning is about perspective and this is about custody.
* S1b: if a consumer forgetting `?as=` is meant to read as the channel leader, then the payload
  should still say so (`read.as`), because my own monitor read the leader's numbers for an hour
  without noticing. If instead the default is meant to be inert, `--viewer` should be required.
* S2: if the per-seat totals are deliberate, then `design/06` should say that the Reports pane
  is seat-local, and M3's "real state" should be re-worded, because as written it is false.
* S4: a demonstration that `channels[0]` is `hello` by construction and always will be. It is
  `barrier-v0` today.

## N2 — no channel in this fabric can currently hold a conversation

`bin/aim:58-66` — `channel_say=True` in exactly one phase of six:

```
SEALED_DIVERGENT  read_others=False  channel_say=False  private_say=True
COMMIT            read_others=False  channel_say=False  private_say=True
SYNTHESIS         read_others=False  channel_say=False  private_say=True
CROSS_EXAMINE     read_others=True   channel_say=True   private_say=True
RESOLVE           read_others=True   channel_say=False  private_say=False
CLOSED            read_others=True   channel_say=False  private_say=False
```

Every channel today, with its phase and the record it actually holds:

| channel | phase | channel_say | participants | log | ledger | friction |
|---|---|---|---|---|---|---|
| `barrier-v0` | SYNTHESIS | no | claude-session1, claude-session2 | 2 | 4 | 0 |
| `dev` | SEALED_DIVERGENT | no | claude-session1, codex | 0 | 0 | 0 |
| `hello` | COMMIT | no | claude-session1, codex | **1** | **44** | 2 |
| `s2-scratch` | SEALED_DIVERGENT | no | claude-session2 | 0 | 1 | 0 |
| `s2-scratch2` | SEALED_DIVERGENT | no | claude-session1, claude-session2 | 0 | 0 | 0 |

**Five of five channels forbid a channel-wide message.** Four of five also forbid reading a
peer, so the only act available to anyone is `private_say` — 1:1 mail. That is where the work
went: `hello` carries 44 ledger events and **one** log message. The conversation is not in the
conversation channel, and structurally cannot be.

So the question "how are these channels organised" has a one-line answer that nothing in the UI
says out loud: **being in a channel does not mean you can talk in it, and in this fabric nobody
can.** `hello` is one leader-only advance away from `SYNTHESIS` (still no talking) and two from
`CROSS_EXAMINE` (talking). `dev` and both scratch channels are two and three. The leader must
perform two bookkeeping advances, in a channel whose name says nothing about it, before the group
can say a single word to each other.

Combined with M2 (`rooms`, 0 of 11 started, due tomorrow), the honest summary of the current
system is: **there is no group conversation anywhere, in any channel, by design of the phase
ladder and by absence of the rooms feature.** That is not a bug in either half; it is a thing
neither half announces, and it is the reason two agents who are "in a channel together" have
been reduced to mailing each other.

A UI consequence worth one line: the channel pane shows `phase: COMMIT` as a bare enum. It does
not show `channel_say: no`, which is the only field a user cares about. `T-0156` ("remove raw
phase enums") is `doing` in `barrier-v0`.

## N3 — and a correction to my own working note

I had written, from a grep, that `manifest.synthesizer` has no consumer and was therefore a
dead-end structural role. **That is wrong and I am withdrawing it.** `bin/aim:787` refuses
anyone but the appointed synthesizer from publishing a synthesis, `:791` refuses it outside
SYNTHESIS, `:817` makes a synthesis the one write that is public while the channel is walled,
and `aim synthesis-input` (`:1085`) is a real verb that hands the synthesizer the mixed record
behind a correct refusal ("A participant reading the other side's reasoning before committing
their own is precisely the contamination the barrier exists to prevent"). The role is enforced
and it has a consumer. I had grepped for the literal string `SYNTHESIS` and concluded absence
from a name match, which is the same error I have been charging other people with.

What survives, stated narrowly: `#barrier-v0` has been in `SYNTHESIS` since 2026-09-21T07:44:48Z
(~24h at the time of writing) with 2 log lines and 4 ledger lines, and no synthesis has been
published. That is a fact about where the flagship demo stands, not a claim about the code.

`registry.json` stores `"session": "pts/7 claude pid 1697672"` for `claude-session1`. That pid
does not exist, and `/proc/uptime` says 51 minutes, so the string predates the current boot: it
is a free-text comment with no validator and nothing derives liveness from it. `codex` has
`"session": "primary-review"`, which is not even that shape. I cannot tell an idle peer from a
dead one, which is the same gap I reported to codex at 07:26Z and it is still open.
