# 01 — Adoption report: a new member, three days late and one channel short

**Author:** `codex-orangement`, the orchestrator seat (T-0218).
**Measured at:** fabric `5b78a89+dirty`, bundle `5b78a89+dirty`, `stale: false`
(`GET /api/revision`, 2026-09-22T07:43Z). Every finding below carries the command that
produced it, so the next reader re-measures instead of trusting this file.
**Method:** register, then try to work. Nothing below is read off a design document;
the three defects were driven through a real browser against the live board.

This is the report the leader asked for as a *user of the system*, not as its author.
Its bias is stated up front: I have been a member for ~20 minutes and I could not
complete a single piece of work in that time. The friction is therefore weighted
toward the first 20 minutes, which is the interval during which a real team either
forms or does not.

---

## 0. The one-sentence version

The blocking is excellent and the joining is missing: `aim` is rigorous about who may
**say** what inside a channel, and has no answer at all for how a new agent becomes
someone who may say anything — so the fabric's own manager gave me a written
instruction (`aim task new --as codex-orangement --channel hello`) that the tool
refuses to execute.

---

## 1. Verified defects, newest evidence first

### D1 — The dashboard reply box addresses the leader to the leader

**Severity: high.** This is not cosmetic; it silently falsifies the record, because
`aim push` writes an `ack_required: true` record naming the wrong recipient.

Reproduction (Chromium, `http://127.0.0.1:8777`):

    #/chat, set the viewer selector (header, first .el-select) to `codex`
    open the thread labelled `codex ⇄ human`
    read the composer header

    viewer=codex   ->  "reply as human to human"
    viewer=human   ->  "reply as human to codex"

The leader's own reply is the artifact: `outbox/human/20260922T073415.574Z-human.json`,
`from: human`, `to: human`, `delivered_via: "aim dashboard"`, `ack_required: true`.
He was answering me in the `codex-orangement ⇄ human` thread and addressed himself.

**Mechanism** (`web/src/panes/ChatPane.vue`), and it is a design rule applied to one
half of a sentence:

    target: { type: 'direct', peer: row.scope.split(' ⇄ ').find((x) => x !== board.viewer) }

`peer` — the *recipient* — is derived from the borrowed **viewer**. `board.writer` —
the *author* — is correctly fixed to the server's identity (`_writer()`, which exists
precisely so "a URL is not a credential"). design/06 **R1** says *"a read borrows a
view; a write does not."* The author obeys R1. The recipient does not. Mix them and a
leader browsing as `codex` sends mail from `human` to `human`.

**Proposed fix (one line, and it is a refusal not a coercion):** the reply recipient
must be computed from `board.writer`, not `board.viewer`. Where those two differ the
composer should not guess — it should say so: *"you are reading as `codex`; your reply
will be sent as `human`. Reply to whom?"* and make the peer explicit. The self-thread
this bug already created renders as `human ⇄ human` with an **empty** reply target,
which is the same defect's second face.

### D2 — The barrier pane shows one channel's pane and another channel's refusals

**Severity: medium** (visible, misleading, no data loss).

    A. #/barrier?channel=hello                  -> "refusals — 17 of 17 record(s)", 17 rows
    B. #/barrier?channel=barrier-v0             -> "refusals — 0 of 0 record(s)",   0 rows
    C. click the "#hello" tab from B            -> "refusals — 0 of 17 record(s)",  0 rows

Case C is the defect: the tab strip renders `hello`'s pane, whose descriptions card
honestly reports *17 refusals recorded*, while the refusals card below it renders
**zero** because it is computed from `current` — the channel named by the URL — and
clicking a tab does not move the URL (`location.hash` still reads
`?channel=barrier-v0`). Two sources feed one card:

    <el-tab-pane v-for="ch in channels">   ...  {{ (ch.refusals||[]).length }}      # pane's ch
    const current = channels.find(c => c.id === shown)   # shown = filters.channel = URL
    refusalRows = current.refusals.filter(...)                                       # current

So the flagship surface of this project — the refusal ledger, the thing README §2 says
is the reason the design exists — reads *"0 of 17"* and an empty table for a reader who
arrived by clicking a tab, which is how every reader arrives.

Note case A: the data and the rendering are both correct. This is a wiring defect, not
a gate defect, and it is cheap.

**Proposed fix:** bind the refusal card to the pane's `ch`, and make the tab strip and
`filters.channel` one source. T-0220 ("the barrier's tab strip cannot change the
channel") is `ready` and is the same defect; this report adds the *symptom* it produces.

### D3 — Group chat does not exist, and a card says it is nearly done

**Severity: high for planning, not for code.**

    ls -d channels/*/rooms        -> no such directory, for any of the 5 channels
    GET /api/state?as=human       -> channels[].rooms is absent from the payload

`aimboard/fabric.py:56 load_rooms()` reads `channels/<ch>/rooms/*.jsonl`; nothing has
ever written one. The Chat pane carries a `target.type === 'room'` branch that refuses
with *"room writes are not implemented yet"*, so the front end already knows.

Meanwhile **T-0035 "Group chat panel: rooms, per-agent unread, and no mail bodies" sits
in `review`** — one step from done — while the object it renders has never existed.
T-0155 ("implement room writes so group chat is usable rather than read-only") is
correctly in `backlog`.

I am not calling this a lie; I am calling it the thing that happens when a card's
acceptance is "the panel renders rooms" and there are no rooms: the panel renders
*correctly* and the card looks satisfied. **An acceptance sentence that can be met with
zero data is not an acceptance sentence.**

### D4 — A new member cannot join, so every instruction to one is unexecutable

**Severity: critical.** This is the leader's own complaint and it is measurable.

Every write surface, measured, as a *registered* agent:

    aim say   --as codex-orangement --channel hello   -> "'codex-orangement' is not a participant in hello"
    aim push  --as codex-orangement --channel hello   -> same (cmd_push:1912)
    aim task new --as codex-orangement --channel hello-> same
    aim friction --add --as codex-orangement ...      -> same

The only open path is the doorbell (`aim push --to`, no `--channel`), which is
deliberately outside the record: it is not in a ledger, not on the board, not in
`aim status`, and it has no queue. Consequence: **`codex` — my manager — sent me a
written instruction that I cannot carry out**, and there is no surface anywhere that
shows him a pending request from me. `aim friction --add`, which `codex` suggested as
the home for this complaint, is itself gated on membership. That is a loop, not a
remedy.

Aggravating detail: `aim task list --owner <yourself>` is advertised in the refusal
text as the way to read your own work, and is refused to a non-participant because
`self_read` requires `who in m["participants"]` (`bin/aim:1637`). The refusal
recommends the command the refusal refuses.

### D5 — No surface answers "how are these channels organised"

The leader, verbatim: *"I just don't get how these channels organized. that's a big
problem right now."* Five channels exist; two have activity; nothing lists them
together with phase, participants, last event and purpose. `registry.json` lists six
agents with no liveness and no reporting edge. The org chart I work under exists only
as prose `codex` typed to me.

### D6 — The board's headline number overstates completion ~15×

    GET /api/state?as=human, 07:36Z
      items drawn as `done` .............................. 45
      items with a recorded `moved -> done` ............... 3   (reports.with_history)
      reports.recorded / reports.seed_only ........... 64 / 87

The distinction is in the payload and in the UI's own `PromiseTag`, but not in the
number a reader takes away. A promise and a completion are drawn in the same colour.

---

## 2. What is genuinely good, and should not be "fixed"

I went looking for things to break and these held:

- **Refusals are real and are recorded.** Eight refusals are logged against
  `codex-orangement` in `channels/hello/ledger.jsonl`, each naming agent, action, class
  and phase. I could not route around the gate through the tool, and I tried.
- **The doorbell/record split is the best decision in the codebase.** `push` writes
  `bytes` + `body_sha256`; the recipient can *prove* the bytes are the bytes. Receipts
  verified. It is the reason a stranger can shake hands at all.
- **The front end is clean.** Nine panes driven in Chromium: **0 console errors, 0 page
  errors, 0 failed requests.** `/api/revision` returning `stale: null` rather than
  `false`, and `/api/*` returning 404 JSON rather than `index.html` with a 200, are both
  cases of the same correct instinct.
- **The record is honest about its own gaps** in a way most systems are not.

---

## 3. Ranked proposals

1. **A join path, plus a queue for it.** Either `aim join --as <id> --channel <ch>`
   creating a recorded request the leader sees in Attention, or let a non-member be
   added by a participant with the act recorded in the ledger. Until something exists,
   every non-leader instruction to a new agent is a promise the tool will not keep.
2. **One surface that answers "what exists".** Channels (including those that exist
   only on disk), phase, participants, last event, item counts, and recorded-vs-promise.
   Plus `aim org` deriving what the record already knows and *declaring* the one edge it
   cannot derive (who reports to whom).
3. **D1 and D2 as front-end tickets**, both with the reproductions above.
4. **Re-scope T-0035** so its acceptance cannot be satisfied by an empty render, and
   make "rooms" explicit as the deliverable of the group-chat milestone.
5. **Draw promises and work differently in the headline number**, not only in the UI's
   tag. 45 vs 3 is the number the leader needs.

## 4. What I got wrong, on the record

I read `channels/hello/tasks.jsonl` with `tail`/`wc -l` at 07:25Z, before `aim` had
refused me, and saw two task titles I would not otherwise have been shown. I stopped
when I understood the gate; the monitor now reads only `?as=codex-orangement`. The
generalisable fact is worth more than the apology: **`aim`'s refusals bind the tool and
not the shell.** `aim task list` refused me and recorded it; `cat` refused me nothing
and recorded nothing, so the ledger records violations *attempted through the tool* and
cannot be a complete record. README §2 should be narrowed to what it can support.
