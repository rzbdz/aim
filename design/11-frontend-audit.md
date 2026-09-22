# 11 — Front-end audit: one product model before more features

The leader's complaint is not a style complaint. Eight top-level panes, three
conversation object types, two identities, two task truth sources, and governance
information mixed with delivery information make a product whose concepts are
unclear. This audit is the answer required before more UI is added.

## 1. What was audited

Every source file under `web/src` and the front-end entry points:

| area | files | role |
|---|---:|---|
| shell and layout | `App.vue`, `style.css` | navigation, viewer identity, page frame |
| kernel | `kernel.js`, `views/index.js`, `views/*.js` | context, services, plugin views |
| state and wire | `stores/board.js`, `api.js`, `theme.js` | one gated payload, one API module, presentation only |
| panes | 8 Vue SFCs | route-level composition |
| components | 4 SFCs | owner avatar, status tag, task decision drawer, phase approval card |
| plugins | charts, markdown | ECharts and markdown-it services |
| tests/build | `web/tests`, `web/playwright.config.js`, `web/vite.config.js` | browser regression and production build |

Measured on 2026-09-22: 1,805 lines of front-end source, a production build with
2,267 transformed modules, and a real-browser conversation test passing 1/1.

## 2. The product model the UI must say out loud

The dashboard is a **human command workbench**, not a database browser. It borrows
three old project-management shapes and gives each a hard boundary:

| surface | PM model | content rule |
|---|---|---|
| Attention / 待处理 | exception management and stage-gate review | only decisions, approvals, blockers, receipts, and phase requests; every row has an action |
| Work / 会话 / plan | kanban flow, team collaboration, milestone planning | execution and discussion, each list filterable and linkable |
| Insight / governance | reporting and audit | measurements, risk, refusals, and evidence; no primary action lives here |

That model answers the leader's two non-negotiables. A human can inspect a task or
phase request and click approve, request changes, or reject. A human can also read
agent-to-agent records and reply as the server-owned leader identity. The default
page is the decision queue; nothing else may preempt it.

There are six concepts that a first-time reader has to separate:

1. **The record.** Channels hold append-only logs. The UI renders a fold, never
   a mutable board file.
2. **Viewer and writer.** `?as=<agent>` changes what may be read. The writer is
   the identity the server was started as. A read can borrow a view; a write
   cannot borrow a name.
3. **Work and plan.** A work item in `tasks.jsonl` is evidence. A row in
   `plan/*.json` is a seed. The UI must label provenance rather than present both
   as equally true.
4. **Conversation shapes.** Channel messages, rooms, and direct messages are
   related records but not the same object. They can share a reader only if the
   group label stays explicit.
5. **Delivery versus governance.** Work, timeline, and reports answer “what is
   happening?” Barrier, audit, plan, and risk answer “why is this trustworthy?”
6. **Foreign-tool exports.** JSON/CSV/ICAL are not user navigation; they are
   integration surfaces and belong in a secondary area.

## 3. Problems found

1. **Flat navigation.** Eight equal menu entries mixed work, chat, reporting, and
   governance. The shell now groups them into Work, Conversation, Insight, and
   Governance and uses the registered Chinese title.
2. **Conversation layout.** The old composer was sticky inside the normal page
   flow, so it floated over history. The pane now owns a bounded viewport with an
   independently scrolling history and a sibling pinned composer; they cannot
   overlap because they occupy different flex children.
3. **Kanban command identity.** Dragging showed a command containing the current
   viewer, although a dashboard write would execute as the server writer. The
   command now names `board.writer`.
4. **Overview overload.** It combines operational stats, unacknowledged mail,
   drift, milestone strategy, and recent direct messages. It should become
   “Today/attention” and link to the owning pane instead of trying to be a second
   version of each one.
5. **Recent record incompleteness.** Overview's “latest on the record” reads only
   direct mail. It omits channel and room messages, so the most visible summary is
   not the most recent conversation.
6. **Duplicate task detail.** Gantt and Work items each render their own drawer.
   The next refactor should extract `TaskDrawer` and `TaskMeta` and make task
   detail one implementation.
7. **Gantt claim versus rendering.** The view hint says dependencies, but the
   current chart shows bars, milestone grouping, and today's line; it does not
   draw `blocked_by` edges. That gap is now a named task rather than hidden prose.
8. **Local filter state.** Kanban, timeline, and work-item filters are component
   state, not route state, so a useful view cannot be linked, shared, or restored.

## 4. Information architecture

The navigation order is:

| group | panes | question answered |
|---|---|---|
| Work | Overview, Kanban, Gantt, Work items | what is due, where is it, what are the facts? |
| Conversation | Conversation | what was said, to whom, and what may I read? |
| Insight | Reports | is delivery changing and what is blocked? |
| Governance | Barrier & audit, Plan & risk | why is the record trustworthy and what is planned? |

Recommended names for the next pass:

| current | recommended | reason |
|---|---|---|
| Overview | Overview / 概览 | acceptable as a attention summary, but scope must shrink |
| Board | Kanban / 看板 | “Board” is ambiguous in a project-management product |
| Timeline | Gantt / 甘特图 | names the expected visualization |
| Work items | Work items / 工作项 | correct |
| Conversation | Conversations / 会话 | there is more than one thread and three object types |
| Reports | Reports / 报表 | correct |
| Barrier & audit | Audit & barrier / 审计与屏障 | audit is the broader surface; the phase gate is one part |
| Plan & risk | Plan & risks / 计划与风险 | plural is more accurate |

## 5. Component boundaries

Keep route panes thin and extract reusable product components:

- `TaskDecisionDrawer`: one task detail and decision implementation; Attention and
  Work items use it now, and Gantt/Kanban adoption is the remaining refactor.
- `PhaseApprovalCard`: one stage-gate decision card for `request-advance`.
- `TaskMeta`: owner, dates, milestone, priority, dependency, provenance.
- `ThreadList`: channel, room, and direct thread groups.
- `MessageBody`: markdown body and safe rendering.
- `FilterBar`: one URL-backed filter implementation.
- `StatCard`: labels, values, and one-sentence explanations.

The current Cordis-like context model is sound: views register themselves, panes
request services, and no pane imports another pane. It should be retained.

## 6. Verification

- `npm --prefix web run build` must produce `web/dist`.
- `npm --prefix web run test:e2e` must prove:
  - history is independently scrollable;
  - the composer is not inside history;
  - history and composer do not overlap;
  - composer position is stable while history scrolls;
  - the page does not navigate or remount during a digest interval.
- Attention must expose both task decisions and phase decisions without becoming
  a table dump.
- Chat thread selection and filters must survive in the URL.
- Every summary signal must navigate to a filtered owning list, not to an
  unfiltered dump.
- Chat must open at the first unread receipt, the room unread boundary, or the
  newest message — never at the top of a long transcript.
- Every task-shaped object must expose the same inspect/decision drawer; a card
  that cannot be opened is a report, not a work surface.

The room boundary is deliberately honest: rooms are readable in Chat, but the
composer says that room writes are pending M2. It must not silently route a room
message to the parent channel, which was the defect found while implementing the
filters.

The falsifier for this audit is the next user-facing concept that cannot be
explained with the six model terms above. That concept needs either a new group
or a redesign, not another card in an existing pane.

## 7. Review round: measured interaction debt (2026-09-22)

This round reviewed the rendered pages through the production build at a 1440 px
viewport and ran the current Playwright suite. The build passes, but the suite
has eight failures. Two of them are product defects and are tracked as work
items T-0157 and T-0158; the rest are listed here because they affect the same
human surfaces.

| surface | measured now | what the number means |
|---|---:|---|
| Attention | 1,838 characters in the main region | five summary signals repeat the hero sentence and then repeat the same counts again in the sections below |
| Kanban | 88 cards, tallest 558 px | acceptance text turns the board into a document; scanning a column is not possible |
| Work items | 88 rows, main region 4,157 px | no pagination, no sticky header, and a fixed action column on every row |
| Reports | 50 blocker rows, 2,587 px | no sorting or pagination; blocker IDs are plain text |
| Plan | 28 rows, 3,882 px | long cells, no sorting, and “87 disagreement(s)” has no actionable destination |
| Gantt | 2,270 px chart | undated work items are a tag wall rather than a grouped exception list |
| Conversations | 56,429 characters in the main region | thread selection works, but the reader needs a stronger unread/newest state and one-line previews |
| Audit & barrier | 21 inputs and raw phase enums | protocol vocabulary leaks into primary labels and the page asks for too many choices at once |

The two correctness defects have exact reproduction evidence:

1. Navigating from `?owner=codex&priority=normal` to `?milestone=M2` leaves the
   old owner and priority active and renders `0 of 3`. The URL is supposed to be
   the whole filter state, so omitted keys must reset to their defaults.
2. A live update on a filtered Kanban page is deferred with `a field has unsent
   text` even when only filter controls contain values. Filter and select inputs
   are not unsent composer text and must not stop the record from updating.

The next design rule is therefore stricter than “make it clickable”: **every
summary number, task ID, blocker ID, milestone, refusal row, and conversation
row must either link to the owning filtered view or open the one shared task
drawer.** A row that only reports a fact is a dead end for the human leader.

The density work follows that rule. Pagination or virtualization, compact card
defaults, line clamping, and sticky table headers are delivery work; they should
not be mixed with the correctness fixes above, because a denser board that still
shows the wrong filter is not progress.

### 7.1 Mobile and keyboard re-check

The same production build was measured at a real 390 x 844 viewport. Every route
has the same 332 px horizontal overflow; the page is 722 px wide inside a 390 px
viewport. The fixed 216 px sidebar plus a main region that never collapses is the
common cause, but the tables, board columns, chart, and long action rows then
compound it.

| route | main-region height at 390 px | focusable elements | focusable elements with no accessible name |
|---|---:|---:|---:|
| Attention | 4,675 px | 43 | 3 |
| Kanban | 1,201 px | 195 | 9 |
| Gantt | 2,969 px | 12 | 8 |
| Work items | 4,661 px | 111 | 8 |
| Conversations | 1,349 px | 111 | 97 |
| Reports | 4,448 px | 9 | 6 |
| Audit & barrier | 751 px | 25 | 22 |
| Plan & risks | 8,990 px | 25 | 6 |

The mobile rule cannot be “shrink the desktop screen.” At this width the
sidebar must become a drawer or compact rail, tables must choose a deliberate
mobile representation instead of forcing horizontal page scroll, and message
actions must acquire names rather than relying on icons and pointer position.

### 7.2 Cross-surface semantics found in the same pass

The review did not stop at layout. Three interactions looked correct in a
screenshot while answering the wrong question:

1. **“Needs me” was not recipient-aware.** Live state for viewer `human`
   contained unacked mail from `codex` to `claude-session1`, and Chat marked a
   direct thread as needing the viewer whenever any message in it carried a
   receipt request. The filter must derive from incoming messages addressed to
   the current viewer, not from the presence of a receipt-shaped chip.
2. **Recording a seed could lose the seed.** The shared task drawer passed title,
   owner, status, priority, milestone, acceptance and dates to `aim task new`,
   but omitted tags, estimate and blocked-by. The drawer also kept a decision
   note when the selected task changed. A write surface that silently discards
   the fields it displayed is worse than a read-only one.
3. **The test runner did not own its server.** `reuseExistingServer` let a Vite
   development server on the Playwright port answer the suite, producing a
   module-resolution failure that had nothing to do with the production build.
   A test result is only evidence when the runner controls what it is testing.
4. **Action feedback belonged to no action.** Overview used one `actionError`
   for every phase-request card, and `runAction()` referenced an undefined
   `actionResult`, so a click could throw before the result was shown and a
   receipt failure could be painted onto an unrelated Leader Decisions card.
   Feedback must be scoped to the row that initiated the command.
5. **Tag filtering was still page-local.** Kanban used an array, `multiple`, and
   AND semantics; Items and Gantt still used one string and selected one tag.
   The same word was answering a different question depending on the pane. The
   filter contract belongs in one shared component or composable, with URL
   round-tripping verified on every surface that offers tags.
6. **A forced update threw away Chat reading position.** With `.aim-history`
   parked at `scrollTop = 200`, clicking `update now` after a digest change
   moved it to `5948`. The restore helper snapshots only scrollable ancestors of
   the focused element, so the app-owned scroller is invisible to it. Deferral
   protected the position; taking the update did not. Every deliberate scroller
   must be captured and restored, and the test must assert the position after
   the forced update rather than before it.
7. **Barrier showed content with no selected tab.** With five channels and no
   `channel` query, every `.el-tabs__item` had `is-active` false while the first
   channel's descriptions were rendered. The page must choose a channel once and
   keep the tab, URL and detail in agreement.
8. **Deferral did not resume on its own.** Once a change was deferred,
   `checkDigest()` returned early forever. Clearing the draft or scrolling back
   to the top removed the reason to defer, but the only way to apply the waiting
   record was the `update now` button. Automatic must stay the default; the
   button is the fallback, not the recovery path.

The same live check found a release-blocking integration failure: the first
completed task made `/api/state` return `500` because `report_data()` used
`date` objects as `throughput` keys. Empty throughput had hidden it. The fix is
to keep ISO strings in the payload, and the regression test must complete a task
through the same path instead of asserting on an empty fixture.

The Help phase chips add one more anchored interaction: the URL carries a
phase anchor, so the router must actually move the phase row into view after the
lazy pane mounts, not merely change the heading.

## 8. Independent review and reconciliation

Claude completed a read-only review of the shell, kernel, store/API, all panes,
components, plugins, build, and tests on 2026-09-22. The two audits agree on:

- the Cordis-like context and plugin-view architecture is sound;
- the corrected Chat layout is the correct shape: bounded reader, independent
  history scroller, pinned composer as a flex sibling;
- navigation grouping is the right information-architecture direction;
- the read/write posture must remain server-owned.

Claude's additional findings and the decisions taken here:

| finding | decision |
|---|---|
| Overview and Chat flattened the same three conversation lists independently | `stores/board.js` now exposes one chronological `conversationRows` getter; both panes consume it |
| Chat layout test depended on live data being long enough | the browser test injects a temporary tall fixture, so overflow and scroll are deterministic |
| `quote()` focused the composer through a global DOM id | replaced with a component-scoped ref |
| `StatusTag` is used by only one pane | retained for now; extracting task meta/drawer is the next component refactor |
| `Insight` has one child | retained as a separate group because reports answer a different question than execution |

Claude also recommended route/API/status-vocabulary regressions. The immediate
minimum is implemented: unit coverage for the conversation normalization and
browser coverage for grouped navigation, Chat geometry, and no forced reload.
The route/API/status tests remain follow-up work and are not claimed as complete.

## 9. Second review round: Chat and Help, measured

Method: the production build served read-only at `127.0.0.1:8777`, driven with
Playwright/Chromium at 1440x900 as the leader (`viewer = human`, `is_leader =
true`), against the live record on 2026-09-22. Every number below was read off
the rendered page or off the payload the page was given, not off the source.

### 9.1 A phase chip's destination is a dead link (T-0156 acceptance not met)

`PhaseChip` with `link` navigates to `/help` with `hash = #phase-<key>`, and
`HelpPane` gives every phase row exactly that id. Nothing performs the scroll:
`main.js` builds the router with no `scrollBehavior`, and the page is scrolled by
`.el-main.aim-main` rather than by the window, so neither Vue Router's default
behaviour nor the browser's fragment handling can reach it. Because Help is a
lazy route, the row does not exist at navigation time either.

Measured, three ways, all identical:

| entry | `.aim-main` scrollTop | anchor top in viewport | on screen |
|---|---:|---:|---|
| `#/help#phase-cross_examine` | 0 | 1244 px | no |
| `#/help` | 0 | 1244 px | no |
| click a real chip on `#/barrier` → `#/help#phase-sealed_divergent` | 0 | 1244 px | no |

The anchor exists and is 1,244 px below the fold of a 2,689 px page. So the
chip's stated purpose — "go and read what the phase means" — fails, and the
reader lands at the top of the page to hunt for the row. The fix belongs in the
shell: a `scrollBehavior` that waits for the lazy pane to mount and scrolls the
app-owned scroller, not `window`. Verification: after the fix, the third row
above must report the anchor inside the viewport.

### 9.2 Direct threads are keyed by direction, so one conversation is two rows

`stores/board.js` builds a direct row's scope as `` `${message.from} ⇄
${message.to}` `` and Chat keys threads by that scope, so the pair is split
whenever both parties have written. Rendered thread list, live:

    claude-session1 ⇄ codex     09-22 02:54
    codex ⇄ claude-session1     09-22 03:08
    codex ⇄ human               09-21 09:03
    human ⇄ codex               09-21 08:59

Two rows for the agent pair, and two rows for the *leader's own* conversation
with `codex`. The leader must read their half and the agent's half in different
panes, and neither shows the exchange in order — while the label `a ⇄ b` promises
one conversation. The reply target compounds it: `peer` is computed as the first
participant of the scope that is not the viewer, so opening `codex ⇄ human` and
opening `human ⇄ codex` pre-address the composer to two different agents, and a
thread between two agents that the viewer is not in still offers the viewer a
reply box addressed to whichever name sorts first.

Falsifier for the fix: the thread list shows exactly one row per correspondent
pair, and the composer's addressee is the other correspondent, unchanged by which
direction the last message happened to travel.

### 9.3 The anchor lands on an already-answered message

The contract in §6 reads "Chat must open at the first unread receipt, the room
unread boundary, or the newest message — never at the top of a long transcript."
The implementation takes the first message in the thread carrying the literal
chip `receipt demanded`, and the chip is emitted from `ack_required` alone; it
does not consult `state`, `claimed_at` or `acked_at`.

Measured on the thread `codex ⇄ claude-session1`: 46 messages, 30,659 px of
history, of which 35 carry a receipt demand and **26 of those are already
acked**. The pane opens with the anchor at index 4 — a message timestamped
`2026-09-21 08:23:17`, one day behind the thread's last activity, 41 messages
short of the end. For a channel thread the same computation can never match, so
it falls through to the newest message, which is why the defect is invisible on
the surface that looks fine.

Falsifier for the fix: open a thread whose earliest receipt is answered and whose
latest is not, and the anchor is the first message the viewer still owes; open a
thread with nothing owed and the anchor is the newest message.

### 9.4 "Needs me" is empty of meaning on the surface the agents use

Chat's filter calls `threadNeedsMe`, which returns `false` for every channel
thread and consults `unread` only for rooms. The payload makes that permanent:
the five channel objects carry `gated, id, messages, phase, rule` and no unread
state at all, and the live record has zero rooms. So the only threads that can
ever match are direct threads containing a receipt-shaped chip.

Measured: ticking `needs me` took the list from 9 threads to 4, and the four are
*all* direct threads — including `claude-session1 ⇄ codex` and
`codex ⇄ claude-session1`, which the leader is not a party to. Meanwhile `#hello`
holds an unanswered phase request from `codex` and is filtered out, because a
channel cannot match. On the one surface built for the leader, the control that
says "show me what needs me" asserts there is nothing to do.

Two things are wrong and they are separable: the predicate must be recipient-
derived (T-0162), and the thread list must *show* the state rather than only
filter on it — every row currently renders a label, a timestamp and a 72-character
preview, so even a thread that does need the reader carries no visible mark.

### 9.5 Message chips contradict themselves and leak the wire format

In a direct thread the rendered chips include `acked` and `receipt demanded` side
by side on the same message: the demand is printed without regard to whether it
was satisfied, so the reader is told a receipt is wanted on a message that
already has one. The same row carries `7350 bytes`, which is a fact about the
transport and not about the message. Channel rows emit `kind <kind>`, and would
emit `responds-to <msg_id>` whenever `responds_to` is set — a raw record
identifier that is not a link, which is the dead-end-identifier class T-0159 was
filed to remove. `SEALED_DIVERGENT` also still reaches the reader inside subjects
like `request: SEALED_DIVERGENT -> COMMIT`, where the phase-chip work cannot
reach it because it is free text rather than a phase field.

One coupling matters for whoever fixes this: `threadNeedsMe` matches on the
*literal chip string* `'receipt demanded'`. Renaming or removing that chip
silently disables the needs-me filter, so the chip's meaning must move into the
data before its wording changes.

### 9.6 The leader cannot write from the page the leader is reading

The board at `8777` is read-only, and it says so honestly — the composer is
replaced by "this server was started without `--allow-write` … a reply box that
cannot send is a control that lies about what it does." The writable server left
running is on `8789`, started `--allow-write --as codex`. `_writer()` in
`aimboard/cli.py` documents why the browser cannot choose this (design/06 R1: a
URL is not a credential) and takes the identity from the server's own `--as`, so
a reply typed by the leader there would be recorded as authored by `codex`.

That is correct as a security decision and bad as a product state: the two things
the leader is supposed to do in the dashboard — approve a decision and answer an
agent — are currently served by no running process. Still unverified, and it
should be proven before the next hand-off: that `bin/aim` accepts a write from
the `human` identity in this channel's phase, since `human` is the manifest's
`leader` but is not in `participants`. The dashboard's own claim is that the
leader can reply; that claim needs an end-to-end test, not an inference.
