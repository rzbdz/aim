# My lane: card briefs, verbatim from the store

Pulled with `aim task list --owner claude-session1 --json` at 16:5xZ. Title, status, acceptance, body.

## T-0160 — Make every dashboard route usable at 390px without page-level horizontal overflow

**status:** doing  **priority:** high  **milestone:** M9

**accept:** At a real 390x844 viewport every route has documentElement.scrollWidth <= clientWidth with no page-level horizontal scroll; the sidebar becomes a drawer or compact rail; tasks/items/reports/plan tables have a deliberate mobile presentation rather than clipped columns; the Kanban board, Gantt chart, Chat reader/composer, and Barrier detail remain usable; every icon-only action has an accessible name; keyboard focus order is visible and sensible; Playwright checks all routes at 390px for overflow and accessible names; desktop E2E remains green

---

## T-0163 — Task drawer must preserve the full seed and must not carry state between tasks

**status:** review  **priority:** high  **milestone:** M9

**accept:** Recording a plan seed preserves title, owner, status, priority, milestone, acceptance, start, due, estimate, tags and blocked-by when the CLI supports them; the drawer resolves the selected task by id from the current board so live updates replace a stale object; decision note and error/result state reset when the selected task changes or the drawer closes; tests create a seed with tags/estimate/dependencies, record it from the drawer, reload and assert every field survives; a second test updates the board while the drawer is open and asserts the drawer shows the current task state

---

## T-0170 — Deferred updates resume automatically once the obstruction is gone

**status:** backlog  **priority:** normal  **milestone:** M9

**accept:** While deferred, the board keeps checking whether the obstruction still exists; when the draft is cleared/sent or the reader returns a scroller to the top and the digest differs, the update applies automatically and the banner disappears; while the obstruction remains, no update interrupts the reader; tests cover draft-cleared and scroll-returned recovery without clicking update now

---

## T-0175 — The palette must be switchable from the UI, and the choice must survive a reload

**status:** backlog  **priority:** low  **milestone:** 

**accept:** A control in the shell flips light and dark, the choice is remembered across reloads, and it is reflected in the URL or a stored preference rather than only in memory. The hook is already in place: every colour is a token in style.css with light values on :root and the original dark values verbatim under html.dark, and Element Plus scopes its own dark variables to that same class. The one part that is not a class flip is the markdown body: github-markdown-css ships light and dark as two unscoped stylesheets that both target .markdown-body, so main.js currently imports only the light one and the toggle needs a decision (scoped override, or a dynamically imported stylesheet) rather than a second unconditional import.

---

## T-0176 — An item that needs a decision must offer the decision, not only the option to record it

**status:** doing  **priority:** high  **milestone:** 

**accept:** Opening a work item that asks for approval reaches Approve / Request changes / Reject in one click, and the row label names the decision rather than the bookkeeping. Today the action panel's first branch is v-if=!taskRecorded, which short-circuits the decision panel: T-0004 (owner human, status ready, title 'Leader: approve the plan; advance hello past SEALED_DIVERGENT') and T-0035 (status review, high) are both plan seeds, so 'What the leader can do' offers only 'Record this work item' and the row button reads 'record it'. The leader asked for exactly this: 'I want the thing that needs approve to be clickable, go to the detail, and approve there'. taskActionLabel has the same ordering, so the list lies in the same way: it tests 'is it recorded' before 'what does it need'.

---

## T-0177 — A channel must say what it is for, and scaffolding must not look like work

**status:** doing  **priority:** high  **milestone:** 

**accept:** The conversation list and the channel header show the channel's topic and its participants, so a reader can tell a transport test from the project. The topic is already in the payload at channels[].topic and is dropped by the conversation view, whose channel objects carry only gated/id/messages/phase/rule. Live evidence for why it matters: the leader was asked to approve a phase transition in 'hello', whose declared topic is 'Transport test: can a Claude Code session and a Codex session reach each other', and which holds 20 recorded tasks; meanwhile 'dev', topic 'aim development: task store, rooms, dashboard', has an empty chain and no task store at all. Four of the five channels are scaffolding (dev, hello, s2-scratch, s2-scratch2, barrier-v0) and none of them says so.

---

## T-0185 — The D and R prefixes and the raw phase enums have no way in, and Help has nothing to land on

**status:** doing  **priority:** high  **milestone:** 

**accept:** See the card body for the acceptance criteria

---

## T-0186 — Help is a 4564px wall with no contents, and never says what any pane is for

**status:** doing  **priority:** high  **milestone:** 

**accept:** See the card body for the acceptance criteria

---

## T-0187 — Help's T row teaches the wrong model of the 115 ids it counts

**status:** doing  **priority:** high  **milestone:** 

**accept:** See the card body for the acceptance criteria

---

## T-0188 — Gantt draws 87 plan promises as work and paints 42 of them done

**status:** doing  **priority:** high  **milestone:** 

**accept:** See the card body for the acceptance criteria

---

## T-0189 — At 1024 the Gantt timeline collapses to 151px and still truncates 88 labels

**status:** ready  **priority:** high  **milestone:** 

**accept:** See the card body for the acceptance criteria

---

## T-0190 — Plan claims the store wins about 87 disagreements that have no store value

**status:** ready  **priority:** high  **milestone:** 

**accept:** See the card body for the acceptance criteria

---

## T-0192 — Audit & barrier: one heading over 5400px, and the leader's only action is 4000px down

**status:** ready  **priority:** high  **milestone:** 

**accept:** The page states its purpose in one sentence, is ordered barrier-first and evidence-second, its leader action is above the fold, sealed claims are collapsed, and empty sections are one line

---

## T-0210 — plan.json becomes an importer: one authority for work, and a drift list that can be emptied

**status:** ready  **priority:** high  **milestone:** M1

**accept:** after import, /api/state tasks have a single provenance value, drift is empty or every entry names an action, and a test asserts no task is reachable under two provenances

---

## T-0211 — Decisions carry actions[]: no control renders without the exact argv that resolves it

**status:** ready  **priority:** high  **milestone:** M9

**accept:** every Decision and WorkItem in /api/state carries at least one action with a verbatim argv and the viewer already applied; a test walks the payload and fails on a primary control with no argv; T-0004 is approving, not 'open it'

---

## T-0212 — Estimate in hours: estimate_hours, with a unit on every surface

**status:** ready  **priority:** high  **milestone:** M9

**accept:** no surface renders an estimate without a unit; Kanban, Gantt and Items all say h; Gantt bar width derives from hours; the 87 seed estimates are converted by one stated rule recorded in the migration note

---

## T-0214 — Serve the concept registry from the API so no surface invents a label

**status:** backlog  **priority:** normal  **milestone:** M9

**accept:** concepts leave web/src/concepts.js for the payload; a test fails on any identifier the registry cannot explain; every concept has a stable help#concept-<id> anchor

---

## T-0215 — Scope invalidation to the view: a per-query digest instead of one global fingerprint

**status:** backlog  **priority:** normal  **milestone:** M9

**accept:** a write to outbox/ changes no open page's digest; a task that does not match the active filter produces no update line and no scroll disturbance

---

## T-0228 — /api/agents is unreachable: the 404 catch-all is dispatched before the handler that serves it

**status:** backlog  **priority:** high  **milestone:** M2

**accept:** GET /api/agents returns 200 with the registry as the viewer sees it; the 404 body's endpoint list and the dispatch order cannot disagree, and a test asserts every endpoint the 404 body advertises actually answers 200.

---

## T-0229 — The published AgentCard cannot be parsed by the reference implementation

**status:** backlog  **priority:** high  **milestone:** M2

**accept:** the a2a-sdk's own protobuf parse of the output of 'aim card' succeeds: removing or relocating the top-level metadata field makes tests/test_a2a_reference_client.py::test_the_published_card_is_not_a_valid_agent_card invert from asserting a ParseError to asserting a clean parse.

---

## T-0235 — A card's milestone cannot be corrected, so a milestone's denominator absorbs unrelated work

**status:** backlog  **priority:** high  **milestone:** M1

**accept:** There is a verb that changes an existing card's milestone and the change lands in the ledger; T-0225 (a web regression) leaves M2 ('group chat: N agents in one room') so that reports.milestones.M2.total counts only cards whose acceptance moves M2's own sentence

---

## T-0237 — The 404 guard covers /api/ only, so /rpc and the well-known agent card answer the SPA with HTTP 200

**status:** backlog  **priority:** high  **milestone:** M7

**accept:** GET /rpc and GET /.well-known/agent-card.json each either answer their own JSON or return 404/405 with a JSON body; a probe that folds the response as data cannot receive HTML, and a test asserts it for every non-/api path the board serves

---

## T-0239 — reports.blocked hides a card a human marked blocked once its blocked_by edges are done

**status:** backlog  **priority:** normal  **milestone:** M9

**accept:** T-0041 (status blocked, its only blocked_by T-0040 is done) appears in a field that means 'a human said this is stuck' while staying out of reports.blocked; the two signals are separate fields and one test asserts both

---

## T-0243 — A move has no actor rule: any viewer may push any card into review, and any owner may approve their own work

**status:** backlog  **priority:** high  **milestone:** M1

**accept:** bin/aim refuses doing->review unless the mover is the card's owner, or --force is given and recorded with a reason; review->done is refused to the owner (no self-approval); the board's drawer shows 'Send to review' only to the card's owner and shows the review three only to a non-owner; a test drives all three refusals through the CLI and asserts the drawer's buttons for the owner and for a non-owner viewer, and every move event records actor and owner so 'submitted by its author' is answerable from the ledger

---

