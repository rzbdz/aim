# Design note 17 — the org, the project, and what the fabric does not have

Written 2026-09-22 for the human leader's question, asked verbatim: *who is in
the team, who may dispatch to whom, who reports to whom, and which project is a
session on?* Those are three questions about the org chart and one about the
project, and the honest answer is that the fabric already holds the objects that
answer them but has **no single surface that states them**. This note writes the
model down, names the command that answers each question **where one exists**,
and says *missing* where none does. A row that says *missing* is a deliverable
here, not a promise; the same rule as `README.md` §9.

## 1. The org is the registry

There is exactly one roster and it is `registry.json`. An org is not a second
file — a second roster is a second thing that can drift from the first, and
`design/08` already pays for one such duplication per concept.

    registry.json
      agents: {
        "<agent id>": { id, kind, model, session, registered_at }
      }

* **who is in the team** — every key of `agents`. The kind vocabulary is closed:
  `claude | codex | human | orchestration | other` (`bin/aim`, the `register`
  parser). `kind` is a *name, not a permission*: every permission comparison in
  the tool is the single negation `kind != "human"`, which is what makes the
  leader the leader and everyone else a participant. `orchestration` was added
  for the seat that dispatches work and writes no code (`design/13` §7); `other`
  is the absence of a name, not a name.
* **adding a member is one recorded act** — `aim register --as <id> --kind <k>
  [--model] [--session]`. Taking over an id that exists is refused unless
  `--force`, and a forced takeover is recorded as a distinct registration event
  with `reason: "forced takeover"` (`cmd_register`, `bin/aim`). Registration is
  the only identity the fabric has, and it is cooperative: anything that can run
  `aim` can claim an unused id.

### 1.1 Dispatch is the participant list, not a second relation

"Who may dispatch to whom" is not stored as an authority graph. It is the
channel's `participants` list in `channels/<ch>/manifest.json`: a participant
may address the other participants of the channel it is in, and a registered
agent that is *not* a participant is a stranger that the tool refuses and
records (`aimboard/gate.py: walled_off` — the barrier and being a stranger are
both refusals, and a renderer that serves a stranger the bytes is a route around
a refusal). Membership changes are leader-only declarations that outlive a
phase: `aim channel add --agent <id>`, `aim channel remove --agent <id>`
(`require_leader` with `what="add a member to the channel"`).

So the fabric has a *set* of permitted correspondents per channel, and no
hierarchy inside it. There is no "A may direct B but not C" and no delegation
tree. Dispatch is flat within a channel; the channel is the boundary.

### 1.2 Reporting is the leader relation, and it is per channel

"Who reports to whom" is the `leader` field of the channel manifest, plus the
optional `synthesizer`. A channel has exactly one leader and `aim new-channel`
refuses a `--leader` whose registered kind is not `human`, so the reporting edge
always terminates at the human team leader. The synthesizer is an appointment
rather than a rank — `aim advance --synthesizer <id>` — and it is what opens the
`SYNTHESIS` phase read rule to that one agent.

The relation is **per channel, not per agent**. An agent in three channels has
three answers to "who do I report to", and today there is no agent-level
reporting line that would give one answer. That is a real gap for a team that
wants an org chart; it is also what keeps the barrier simple, because the
reporting edge and the audience of the record are the same fact.

### 1.3 What answers the three questions today, and what does not

| question | answered by | status |
|---|---|---|
| who is in the team | `aim card --as <agent>` (one agent, as JSON); `aim card --as <anyone> --all` (every registered agent) | **present** as a read of the registry, one agent at a time or all at once. There is no table-shaped "the team" verb. |
| who may dispatch to whom | `aim status --channel <ch>` prints `participants`; `aim channel add/remove` changes it | **present**, per channel. There is no command that answers it *for a named agent across all channels* — that is a `grep` over `channels/*/manifest.json`. |
| who reports to whom | `aim status --channel <ch>` prints `leader` and `synthesizer` | **present**, per channel. There is no agent-level reporting line. |
| all three, for one named agent, without reading JSON by hand | — | **missing**. `aim org --as <agent>` is the verb that would satisfy `T-0231`'s acceptance, and it does not exist. |

The card is the nearest thing to an org surface and it is deliberately a
*public* description of one agent (`design/16` §2): it carries `agentKind`,
`agentModel`, `registeredAt` and the binding facts, and nothing about channels.
`aim card --all` is therefore a roster read and not an org chart.

## 2. Where a session's project lives

**A session's project is the channel it is currently a participant in**, and
that is derived from the store rather than kept in a field. The chain is:

    the session id in the registry entry (`agents[<id>].session`)
      -> the agent id
      -> every `channels/<ch>/manifest.json` whose `participants` names that id
      -> the channel

Nothing in that path is hand-maintained. A session that stops being a
participant of A and becomes one of B changes its answer at the moment
`aim channel add/remove` records the change, with no edit to any field, because
the field never existed. When the store is read by the board the same answer
comes out the other way round: `aimboard/fabric.py` reads every manifest under
`channels/`, and `gate.gate_channel` picks the channel whose participant list
names the viewer — the project a session is on *is* the gate that applies to it,
which is why the answer is derived and not declared.

Two consequences worth stating plainly:

* The registry's `session` string is free text (`"pts/7 claude pid 1697672"`,
  `"primary-review"`). It is the only link from a live process to an agent id,
  and it is a note, not a key. Deriving the project from the *agent id* is sound;
  deriving it from the *session string* is not, and no verb does.
* An agent in no channel has no project. That is a state the fabric can
  represent and does not currently name — "unassigned" is not printed anywhere.

## 3. A channel is real or it is scratch

`aimboard/fabric.py: channel_kind()` is the rule:

    declared  : manifest["kind"]          (a writer that recorded one)
    otherwise : "scratch" if topic.startswith("scratch") else "project"

The fallback is a heuristic and the source says so. It exists because of a
measured accident: T-0232 found two abandoned `s2-scratch*` channels sitting in
the same flat namespace as real work, and `T-0216` found the reverse case — the
channel named for the development work (`dev`) is empty while every live task
sits in the channel named after a transport test (`hello`). A channel is
therefore described by **two independent facts**, and neither one implies the
other:

| fact | field | values |
|---|---|---|
| what it is for | `kind` | `project` \| `scratch` |
| whether anything happened | `state` (`channel_lifecycle`) | `empty` \| `dormant` \| `active`, derived from traffic and `DORMANT_AFTER_DAYS = 2` |

`empty` means nothing was ever recorded in it, whatever its manifest says;
`dormant` means the newest record is at least two days behind the board's
`as_of`; `active` otherwise. `idle_days` is exposed so a caller with a real
milestone calendar can apply its own threshold instead of the default. Nothing
in `state` is maintained by hand — that is the property that makes it worth
trusting.

`aim status --channel <ch>` is the surface that shows a channel's phase, its
participants and their seal state. It does **not** print `kind` or `state`;
those live on the board payload (`aimboard/api.py`). Hiding scratch channels
from a status listing is therefore **missing** at the CLI: the discriminator
exists in the model, the read that uses it is the board, and no `aim` verb
advertises it yet. That half of T-0232 is a build, not a documentation gap.

## 4. Labels: one dictionary, keyed by token (T-0202)

The convention is already law in two places and this note makes it explicit
because a third renderer would otherwise invent a third answer:

* **Every user-visible word resolves through a concept registry keyed by the raw
  token.** The raw protocol value (`SEALED_DIVERGENT`, `blocked`, `CROSS_EXAMINE`)
  stays canonical and stays available — it is what the record holds and what
  `aim` takes as an argument — and it stops being the *primary* label rather
  than being hidden. Python: `aimboard/const.py` `LABELS` (`"en"`, `"zh"`) keyed
  by the view token. Browser: `web/src/concepts.js` `PHASES`, each concept
  carrying its own `key`, plus the labels the kernel registers per view.
* **A concept says what it does to you**, not what it is called. "Positions are
  sealed" is a description; "you cannot read a peer's reasoning yet, and the tool
  will refuse you if you try" is the sentence that makes it usable. That is the
  documented test for whether a label belongs in the registry.
* **Bilingual means two dictionaries, never a translated identifier.** `zh` and
  `en` are the two locales; adding a third is adding a key set to `LABELS` and
  `concepts.js`, not touching a call site.
* **Every rendered date names its timezone.** A date without a zone is a
  statement the reader cannot audit, which is this project's recurring defect in
  miniature. The store's timestamps are ISO-8601 UTC (`...Z`), and
  `aimboard/fold.py` labels its own bucket grid `"timezone": "UTC"` — that label
  must not be dropped when a value crosses into a view.
* **The calendar in which dates *mean* something is `plan/plan.json`.** Its
  `"timezone": "Asia/Shanghai"` is the single source: a due date, a milestone
  date and an `idle_days` threshold are all read in that zone, so a task due
  "today" is due in the leader's day and not in UTC's. `plan/plan.json` is a
  seed and the store overrides it field by field, but the timezone is the seed's
  to own because it describes the room the leader is sitting in.

The gap this closes is narrow and named: the two dictionaries are not yet
complete (`LABELS` has no key for the panic/refusal vocabulary, and the board
falls back to English for anything it does not know), and the "every date names
its zone" rule is stated here and rendered in the panes inconsistently. The
convention is the deliverable; the sweep is a build.

## 5. Above a task: milestones yes, cycles no (T-0191)

**The ruling: this board has no cycle model, and a cycle object is not being
added today.** Stated as a decision, per the card's acceptance.

What exists above a task is a **milestone**, and only that:

* `plan/plan.json` holds `milestones` (`M0` … `M6`), each with `id`, `name`,
  `due` and an `accept` sentence. A task points at one through its `milestone`
  field (`aimboard/const.py: PLAN_FIELDS`).
* The milestone is drawn: `aimboard/views/timeline.py: render_gantt` groups tasks
  by milestone and draws a diamond per `due`; `aimboard/views/plan.py` and
  `overview.py` read `state["milestones"]` for counts and the next ones due.
* There is **no milestone pane**. `web/src/views/` holds exactly ten views —
  `barrier, chat, gantt, help, index, items, kanban, overview, plan, reports` —
  and milestones are a block inside the Plan pane (`views/plan.js`, key `plan`,
  title "Plan & risks"), not a pane of their own. `grep -ri milestone` over
  `web/src/views/` returns nothing; the only milestone-shaped UI is the timeline
  diamonds and the filter dropdown the HTML views build.
* There is no **epic** and no **project object**: the nearest thing to a project
  is the channel (§2), and a task reaching a channel is `context_id`, not a
  hierarchy.

Why no cycle object, stated rather than deferred: a cycle is a *time box*, and
the only clock this fabric trusts is the event log. `fold.report_data` already
computes `cycle_days` and `median_cycle` from recorded `created` → `moved ->
done` events, so the board answers "how long did work take" from the store
without anyone maintaining a box to put it in. A cycle object would be a second
calendar beside `plan/plan.json`'s milestones, kept true by hand, on a board
whose whole design rule is that nothing above a task is hand-maintained. The
cost of not having it is real and specific: there is no way to state "this is
what we committed to this week", and burndown is therefore drawn against the
plan seed rather than against a commitment. If a cycle is added later it must be
derived — a `starts`/`ends` pair over the merged board — and the honest place to
add it is the Plan pane, which already owns the milestone block, not a new pane.

## 6. The ruling on leader approval (T-0178)

**`require_leader` is called for every advance.** `cmd_advance` opens with
`who, kind = resolve_actor(args)` then `require_leader(who, kind, m)`, and
`require_leader` refuses unless `kind == "human"` *and* `who ==
manifest["leader"]`. There is no bypass: `--force` skips the transition-legality
check and nothing else, and `request-advance` is the agent's recorded way to
*ask*. So an agent cannot move a channel from `SEALED_DIVERGENT` to `COMMIT`;
the refusal is `class: barrier` and lands in `ledger.jsonl`.

The table is what makes some of those approvals inert:

    SEALED_DIVERGENT  read_others=False  channel_say=False  private_say=True
    COMMIT            read_others=False  channel_say=False  private_say=True
    SYNTHESIS         read_others=False  channel_say=False  private_say=True
    CROSS_EXAMINE     read_others=True   channel_say=True   private_say=True
    RESOLVE           read_others=True   channel_say=False  private_say=False
    CLOSED            read_others=True   channel_say=False  private_say=False

`SEALED_DIVERGENT -> COMMIT` and `COMMIT -> SYNTHESIS` change no permission at
all, so the leader's approval there is bookkeeping and the record's own
tamper-evidence is what it buys: the phase history says *when* the team stopped
forming positions. The one edge that ends independence is `SYNTHESIS ->
CROSS_EXAMINE`, the single place `read_others` and `channel_say` open.

**The reading `design/05` supports is Option A: every edge is leader-only.**
`design/05` §1 states the capability table as "roles and permission to act —
**existing** — leader is human and only the leader advances phases", and §2 sets
the same requirement from the outside: a non-leader advance is "refused,
recorded, `class: barrier`". The design's sentence is about the *phase*, not
about the permission diff, and it is the sentence that is currently true and
easy to audit: **only the human moves the phase.** Option B — letting a
participant cross an edge that changes no rule, keeping the leader for the edge
that does — cannot be adopted by re-reading the contract; it changes the
contract, and it costs the one-line invariant that `aim` can be audited against.

What would change if the leader ruled the other way: `require_leader` in
`cmd_advance` would take the destination phase and consult `PHASE_RULES` to
decide whether this particular edge is leader-only; the refusal class would need
a second sentence for "well-formed, non-leader, rule-changing" versus
"well-formed, non-leader, inert"; `aim verify`'s re-walk would still hold because
the phase history keeps `by`; and the Help page's sentence "only the human moves
the phase" would have to become a table of which edges are inert, which is the
tell that Option B is more expensive than it looks. This note does not change
code: the ruling is that the current reading stands and the inert edges are
stated as inert.

## 7. Open, and honestly open

* **`aim org --as <agent>`** — the verb T-0231's acceptance names. The registry
  has the team, the manifests have dispatch and reporting, and no command
  composes the three for one agent.
* **The reporting line for an agent** — today it is per channel; an agent in
  three channels has three leaders. There is no "who do I report to" answer that
  is not scoped to a channel.
* **Scratch filtering at the CLI** — `kind` and `state` exist in the model
  (`aimboard/fabric.py`) and are read by the board; `aim status` prints neither,
  so "hide scratch" is a board behaviour and not a tool behaviour.
* **`unassigned`** — an agent in no channel is a state the fabric can hold and
  never names.
