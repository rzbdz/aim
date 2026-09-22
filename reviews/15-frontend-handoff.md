# Front-end findings handed to `web/src`'s holder

Author: the new `claude-session1` session (not the one that sealed `4ad12910aed7…`;
that seal records `model: "Opus 5"`, this session runs Sonnet 5). I did not write
any file under `web/` and I am not claiming `web/src` — `codex` holds it, by its
own write-set table at 08:30Z. This file is the handoff so the findings are not
lost with the session that measured them.

Method: read-only. Every item is `file:line` plus what a reader would see. Where
a number is given it was read out of the payload or the source, not estimated.
Items already in `design/11-frontend-audit.md` or `design/12` §1.7 are marked
**[delta]** and only included when I have a fact those documents do not.

---

## Top five, by what they cost the leader

**W1 · A tile that says "needs action" links to a list that cannot contain the
thing it counts.** `OverviewPane.vue` counts `board.unacked.length` (33 live) but
routes to `#/chat?needsMe=1&shape=direct`, and the destination is filtered by
`waitingOnViewer`, which requires `message.to === board.viewer`. Live: 10 of the
33 unacked rows are addressed to `human`; the rest are `codex`'s and
`claude-session1`'s correspondence. So the one number on the page that is *about
the reader* lands on a list the reader cannot act in. The tile's own detail tag
reads "on the record", the same sentence Overdue and Blocked use — three tiles
where the count and the destination *are* the same question, and this one where
they are not. `design/12` found "7 while only 2 are addressed to the viewer";
**[delta]** is the current live pair (33 / 10) and the file:line of the tile.

**W2 · `confirm receipt` renders on mail that is not the viewer's, and its only
outcome is a refusal.** `OverviewPane.vue:431-435` gates on
`message.shape === 'direct' && message.ack_required && !message.acked_at` — there
is no recipient test. Five of the newest conversation rows on the live board are
`codex → claude-session1` with `ack_required: true`. The button POSTs
`['confirm','--msg-id',…]` as the server's writer, the CLI refuses, and the reader
gets `The tool refused this action` printed on a row in the "Latest conversation"
card. Two spellings of one action identity also exist here: the `:loading` key is
`` `confirm:${message.msg_id}` `` while `confirmMessage()` calls
`runAction('confirm', …)`.

**W3 · Work nothing can move is drawn as a "decision for you".**
`OverviewPane.vue:347-358` renders rows from `board.promiseDecisions`
(`owner === 'human' && status === 'ready'` on seed-only items) labelled
**"decision for you"**, whose only control is `open it`. The drawer's panel for a
seed is `Record this work item` plus status buttons, and `canDecide` is
`board.canWrite && taskRecorded` — false for a seed — so every control is
disabled. Live: 106 of 156 tasks carry seed-only provenance. This is
`design/12` §1.1's finding; **[delta]** is the disabled-action chain
(`TaskDecisionDrawer.vue:33-34, 45, 196-246`), which reproduces after the drawer
refactor.

**W4 · The header refresh button is an unlabelled icon, and the pane's copy of
the same button is labelled.** `App.vue:139-141` — no `aria-label`, no text, no
tooltip; a screen reader announces "button". `ChatPane.vue`'s copy is wrapped in
`<el-tooltip content="re-read the record">`. And per `AGENTS.md` the board is
supposed to be current by itself, so the button should not need to exist; when
`load()` fails it sets `board.error` and leaves the page as it was, so the button
can appear to do nothing at all.

**W5 · The Gantt cap reproduces the bug its own comment records.**
`GanttPane.vue:57` — `chartHeight = Math.min(3000, Math.max(320, rows.length * 21 + 130))`.
Past the cap each row is `(3000 - 130) / n` px: 21 px at n=136, **8.9 px at the
live 137 dated items**, 4 px at 300. The comment at `:20-27` records that 8 px a
row was the *first* version of this bug ("the bars were fine and the labels were
unreadable"). There is no row-count control, no y-zoom and no pager.

---

## Scroll and reading position

**W6 · Both scroll guards walk the whole DOM every 2.5 s.**
`stores/board.js:95` and `:125` are `document.querySelectorAll('*')` with a
`getComputedStyle` per already-scrolled element; `main.js:220` runs
`checkDigest()` on a 2.5 s interval. The comment at `board.js:93-94` argues the
`scrollTop <= 2` guard keeps it cheap — it bounds the *style* calls, but the
`querySelectorAll` is unconditional. Live board: 156 tasks across Items (11-column
table), Kanban (7 columns with inner scrollers) and Chat (197 flattened rows).
UNTESTED: I did not profile; I am reporting the call shape and the cadence.

**W7 · `readingInterrupt()` reads a scroller that never moves.**
`board.js:89-92` reads `document.scrollingElement.scrollTop`, but
`style.css:92` (`.aim-main { overflow: auto }`) plus `style.css:58`
(`html, body, #app { height: 100% }`) mean the document never scrolls. Only the
fallback loop at `:95-101` makes the veto work at all — and the string the reader
sees names the wrong object: `App.vue:150-157` prints "the page is scrolled" for a
state produced by `.aim-main`.

**W8 · Three timestamp truncations for one field.** `ChatPane.vue:264`
`slice(0,19)`; the thread list `slice(5,16)` at `:517`; Overview `slice(0,16)` at
`OverviewPane.vue:430` and `:421`; the drawer `slice(0,19)` at
`TaskDecisionDrawer.vue:259,271`. Five sites, three formats, no shared `stamp()`
— even though `theme.js` already holds `days`, `today` and `isOverdue`.

**W9 · `preview()` slices 72 code units of raw markdown.** `ChatPane.vue:265-268`
applies `.replace(/[#*`>|\n]+/g, ' ').trim().slice(0, 72)` to the *markdown*, with
no link-stripping step. A message that is a table previews as pipe soup in the
list and renders as a table in the reader — and this project's own records are
full of tables. The same 72-slice appears twice more on Attention
(`OverviewPane.vue:412,427`) with a different stripping rule, so two panes slice
one fact to one width by two methods.

---

## State and correctness

**W10 · The drawer can hold a task the board no longer has.** `App.vue:19-22` —
`board.tasks.find(t => t.id === id) || taskDrawer.state.task`. The first branch is
live; the second is the object captured at click time. A task that later leaves
`board.tasks` (a seed recorded under a new id; a task withheld when
`board.setViewer` re-loads) renders from a snapshot the store no longer holds,
while the panel's buttons act on `props.task.id`. So "Assign to me" can issue a
command for an id the board does not have, and the error alert prints a refusal
about a task that is not on screen.

**W11 · `actionError` is one ref for every phase-request card.**
`OverviewPane.vue:15`, cleared at `:247`, set at `:251`, bound to every card at
`:325` inside `v-for="request in board.phaseRequests"`. A failed `confirm` on a
conversation row sets it at `:433`, and `PhaseApprovalCard.vue:62-64` then renders
it on every request card above. `actionBusy` *is* scoped by key, so the busy and
error states for one action have different scopes. This is `design/11` §7.2 item 4
(T-0165) and it is still live.

**W12 · The phase-request parsing is done twice, with two fallbacks.**
`stores/board.js:350-367` parses `/^request:\s*([A-Z_]+)\s*->\s*([A-Z_]+)$/` and
filters on `targetPhase && currentPhase === fromPhase`;
`PhaseApprovalCard.vue:14-21` re-runs the same regex and re-derives the same four
fields from `board.doc.channels`. The fallbacks differ — the store's is
`match?.[1] || row.phase || channel.phase`, the card's is
`match?.[1] || props.request.phase || props.request.currentPhase` — so for a
subject that does not match, the two can name different from-phases and only the
card's reaches the screen.

**W13 · Chat's channel badge is dead by construction.** `ChatPane.vue:94` sets
`to: '#' + row.channel` for channel rows, and `:167` is
`message.to === board.viewer`. `'#hello' !== 'human'`, so the badge loop at
`:133-137` computes `unread = 0` for every channel thread and the "N messages
addressed to you" tooltip at `:513-515` never renders. `threadNeedsMe`'s channel
branch (`:176`) uses `thread.unread > 0` as a conjunct, so it is unsatisfiable for
a channel. Live: `#hello`'s newest message is a `kind: "request"` from `codex`
that the leader has not answered, and the pane reports zero. **[delta]** — fixing
only the predicate leaves the row unmarked, because the badge path is dead for the
same reason.

---

## Layout

**W14 · Items has no pagination and no sticky header, over 156 rows.**
`ItemsPane.vue:53-93`. `design/11` §7 measured 88 rows / 4,157 px; live it is 156
rows, so roughly 7,300 px under one heading. `grep -rn "el-pagination\|virtual"
web/src` returns nothing.

**W15 · Items' default sort is inert.** `ItemsPane.vue:54` sets
`:default-sort="{ prop: 'id' }"` with **no `order`** — Element Plus applies a
default sort only when `order` is given. The table renders in `board.tasks` order,
which happens to be id-ascending from `stores/board.js:211`, so it *looks* sorted,
the `id` header shows no arrow, and a reader who sorts by `due` has no control
that says how to get back.

**W16 · Kanban invents a channel name for the command it shows.**
`KanbanPane.vue:65` — `task?.channel || task?.context_id || board.channels[0]?.id || 'hello'`.
The drag alert prints that command as "the command that would carry it out". A
task with no channel (a plan seed; live 106 of 156) gets the first channel in the
payload (live `dev`, which is `SEALED_DIVERGENT` with no work in it) or the literal
`'hello'`. `'hello'` is a hardcoded default in three places (`KanbanPane.vue:65`,
`TaskDecisionDrawer.vue:31,46`). A plausible-looking *wrong* command is worse than
none.

**W17 · The Gantt's undated work is a wall of non-clickable raw ids.**
`GanttPane.vue:165-170` — `<el-tag v-for="t in undated">{{ t.id }}</el-tag>`. Live
19 items. Every other id-bearing surface routes through `TaskLink.vue` or
`drawer.open`; this is the one that breaks "every identifier deep-links or
explains itself".

**W18 · Gantt status is colour-only on a canvas.** `GanttPane.vue:72` sets
`itemStyle.color` and `:110-121` removed the per-bar label deliberately. The
legend at `:153-156` is labelled, but the bars are ECharts canvas, so a
screen-reader user gets nothing, and `#94a3b8` (backlog) vs `#9ca3af` (dropped) and
`#f59e0b` (doing) vs `#b45309` are near-identical under common colour-vision
deficiencies. The tooltip names the status — a hover-only affordance.

**W19 · `.aim-accept` has no clamp.** `KanbanPane.vue:128-132` renders the full
acceptance text unless a page-local `compact` checkbox (`:102`) is ticked, and
`style.css:178-179` has no `max-height` or line-clamp. Live acceptance strings run
380-520 characters. `design/11` §7 measured the tallest card at 558 px and put the
fix in T-0161. **[delta]** the `compact` control exists but is page-local (not in
the URL), defaults to off, and is the only density control on the page — so the
board's default state is the 558 px card.

**W20 · Row-click is a control with no name on Items and Reports, and a named one
on Overview and Kanban.** `ItemsPane.vue:53` (`@row-click`) gives a mouse user a
300 px target with no `role`, `tabindex` or `aria-label`, while the keyboard path
is the 86 px `action` column button at `:56-61`. `OverviewPane.vue:372-376` and
`KanbanPane.vue:116-120` do it correctly with `role="button" tabindex="0"
:aria-label`. Three surfaces, one gesture, two implementations.

---

## One fact, two renderings

**W21 · Milestone progress is two different fractions, one of which counts
dropped work as done.** `PlanPane.vue:12-16` filters `board.tasks` and counts
`board.terminal`, which is `['done','dropped']` live.
`OverviewPane.vue:185-188` computes the same milestone over `board.recorded` only.
The two panes therefore show different `done/total` and different `el-progress`
values for the same milestone id on the same payload, and neither says which
fraction it is showing.

**W22 · The estimate field has two names and three unit treatments.**
`KanbanPane.vue:125` renders `{{ t.estimate }}d`; `GanttPane.vue:84` renders
`(${t.estimate}d estimate)`; `ItemsPane.vue:79` renders a bare `est` column with no
unit. `bin/aim` writes `estimate_pts`; `exporters.py:8` exports a CSV column named
`estimate`; `a2a.py:826` maps `estimate_pts`. So the dashboard, the A2A projection
and `board.csv` show one number under two names, and `design/12` §1.7 already has
the unit argument. **[delta]** is the payload carrying *both* keys and the UI
reading only one.

---

## How I would sequence it, if it is mine to suggest

1. **W1 and W2 together** — both are "the tile's count and the destination are not
   the same question", both are in `OverviewPane.vue`, and W1 is the leader's own
   complaint with a number under it.
2. **W13** — one predicate plus one badge path; it is the difference between the
   pane answering "what is waiting on me" and answering zero on the channel that is
   waiting.
3. **W10 and W11** — both are stale-state bugs where the panel acts on an identity
   the screen does not show, which is the class that produces a refusal the reader
   cannot connect to anything.
4. **W5 and W14-W19** — density and layout; they are one contract and should be
   done as one card (this is T-0161's shape).

Everything above is read-only work; nothing in this file required a write to
`web/`, and I have made none.
