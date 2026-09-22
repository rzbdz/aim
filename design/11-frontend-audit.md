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
| components | 2 SFCs | owner avatar and status tag |
| plugins | charts, markdown | ECharts and markdown-it services |
| tests/build | `web/tests`, `web/playwright.config.js`, `web/vite.config.js` | browser regression and production build |

Measured on 2026-09-22: 1,805 lines of front-end source, a production build with
2,267 transformed modules, and a real-browser conversation test passing 1/1.

## 2. The product model the UI must say out loud

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

- `TaskDrawer`: one task detail implementation used by Kanban, Gantt, and items.
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

The falsifier for this audit is the next user-facing concept that cannot be
explained with the six model terms above. That concept needs either a new group
or a redesign, not another card in an existing pane.

## 7. Independent review and reconciliation

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
