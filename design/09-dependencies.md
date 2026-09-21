# 09 — Dependencies: survey first, and measure the survey

The leader's rule, verbatim, because the wording is the requirement:

> 所有研发任务的计划架构，你都要担当责任，第一步永远是先调查市面上已有的任何开源组件、
> 框架，尽可能去站在巨人肩膀构建。实在没有符合你的需求，再自己研发。

> 不过我要求必须是 github star 超过 1k 的才能引用。

Two rules, and they pull in opposite directions if you read the second one alone.
"Stand on somebody else's shoulders" says *adopt*; ">1k stars" says *the shoulders
must be load-bearing*. Together they say: **the first step of any task is a survey,
the survey is recorded with numbers, and a dependency that fails the bar is named
as an exception rather than quietly used.**

This note is that record. It is deliberately a ledger and not a policy essay: a
number you cannot re-measure is a claim, and this project has spent its whole
existence separating the two.

## 1. How these numbers were measured

Nothing here is from memory or from a summary. Every count was read from
`github.com/<owner>/<repo>` on **2026-09-21**, by scraping the star count out of
the page rather than the REST API, because the API is rate-limited to 60 requests
an hour unauthenticated and a survey that fails halfway is a survey that gets
filled in from memory.

    for repo in owner/name ...; do
      curl -s -A Mozilla/5.0 "https://github.com/$repo" \
        | grep -o 'aria-label="[0-9,]* users starred this repository"'
    done

`tests/` does not check these numbers: a test that asserts somebody else's star
count is a test that fails when the world changes, which is not a defect. What a
test *can* check is that the ledger exists and names an exception in the open.
The falsifier for the whole note: run the loop above and find a number that
changes a decision below.

## 2. The ledger

| layer | candidate | stars | decision |
|---|---|---:|---|
| dashboard shell | `vuejs/core` | 54,415 | **adopted** — the framework |
| build | `vitejs/vite` | 82,926 | **adopted** |
| build | `vitejs/vite-plugin-vue` | **682** | **adopted — EXCEPTION, see §3** |
| components | `element-plus/element-plus` | 27,778 | **adopted** — tables, cards, forms, tags, dialogs |
| charts | `apache/echarts` | 67,361 | **adopted** — burndown, cycle time, gantt |
| charts | `ecomfe/vue-echarts` | 10,758 | **adopted** — the Vue binding |
| state | `vuejs/pinia` | 14,724 | **adopted** |
| routing | `vuejs/router` | 4,680 | **adopted** — one route per pane, so a pane is linkable |
| drag | `Alfred-Skyblue/vue-draggable-plus` | 4,016 | **adopted** — kanban drag, over `SortableJS/Sortable` (31,181) |
| markdown | `markdown-it/markdown-it` | 21,932 | **adopted** — message bodies |
| markdown | `highlightjs/highlight.js` | 24,996 | **adopted** — code inside them |
| markdown | `sindresorhus/github-markdown-css` | 8,934 | **adopted** — the typography, so we invent none |
| markdown | `markedjs/marked` | 37,178 | surveyed, not adopted: same job, markdown-it won on plugin shape and byte size |
| markdown | `shikijs/shiki` | 13,820 | surveyed, not adopted: better highlighting, ~1MB and an async host; revisit if code reading becomes the point |
| utils | `vueuse/vueuse` | 22,377 | surveyed, not adopted: nothing in the front-end needs it yet |
| kernel shape | `cordiverse/cordis` | 8,712 | **cited, not installed** — the plugin/service container the kernel copies (npm `cordis` 4.0.0-rc.10, the container behind Koishi, `koishijs/koishi` 6,216) |
| chat UI | `advanced-chat/vue-advanced-chat` | 2,081 | **surveyed, NOT YET ADOPTED — see §4** |
| gantt | `frappe/gantt` | 6,124 | surveyed, not adopted: MIT, but it draws from its own task list and knows nothing about the gate or the draft/published split; also see §5 |
| gantt | `dhtmlx/gantt` | 1,853 | surveyed, rejected: GPL or paid, and a licence that reaches into the fabric is not a dependency, it is a constraint on the product |
| A2A | `a2aproject/A2A` | 25,873 | **adopted as the standard** (design/07) |
| A2A | `a2aproject/a2a-python` | 2,151 | candidate for the binding — decision in T-0101 |
| A2A | `a2aproject/a2a-js` | **624** | surveyed, **below the bar**, and would be the natural browser-side client |
| MCP | `modelcontextprotocol/python-sdk` | 24,350 | **adopted** — T-0120 |
| MCP | `modelcontextprotocol/typescript-sdk` | 13,437 | candidate if the dashboard ever speaks MCP directly |
| MCP | `modelcontextprotocol/servers` | 90,515 | surveyed: reference servers, useful as examples, not as dependencies |
| MCP | `modelcontextprotocol/modelcontextprotocol` | 9,265 | adopted as the spec |
| HTTP | `fastapi/fastapi`, `encode/uvicorn`, `pydantic/pydantic` | 102,496 / 10,975 / 28,843 | surveyed for the A2A binding; adopted only if `a2a-python` is, since it arrives with them |

## 3. The exception, in the open

`vitejs/vite-plugin-vue` has **682 stars and is in use.** It is the compiler for
every `.vue` file in `web/src`, so the honest statement is not "we happen to use
it" but "the front-end does not build without it".

The rule exists to stop us adopting unproven code. This is the least unproven
dependency in the tree: it is maintained in the `vitejs` organisation by the Vue
core team, it is the officially documented way to compile an SFC, and the class of
dependency the rule targets — a library with one author who may vanish — is not
this one. That is a reason to ask for a ruling, not a reason to skip the rule.

**The ruled alternative, costed, if the leader says the bar is absolute:** drop
`.vue` files and write the nine components as `.js` with `defineComponent` and
template strings (or render functions), and use Vite's Vue build without the SFC
plugin. Cost: about a day, no `<style scoped>`, no SFC tooling, and every future
front-end edit gets more verbose. My recommendation is to keep the exception and
write it here rather than pay that. It is the leader's call and it is one line
away from being made.

`a2aproject/a2a-js` (624) is the same shape of problem on the A2A side and is
**not** in use, so it costs nothing to obey: if the browser needs an A2A client
it will either be written against `bin/aim` (our own binding) or the rule breaks
and gets re-litigated with a number in front of it.

## 4. The conversation surface: what we built, and why

The leader's complaint was that the pane was hand-made and that hand-made is
error-prone, and the complaint was right about the result — the nested-scroller
bug came from hand-rolling a layout primitive. So the survey is recorded here in
full, including the part where we built first and surveyed second.

**Adopted (all >1k):** Element Plus for every control; markdown-it + highlight.js
+ github-markdown-css for the bodies. That is the whole of the rendering path.

**Surveyed and rejected on 2026-09-21: `vue-advanced-chat` 2.1.2 (2,081, MIT).**
It is a real Vue 3 chat component with day separators, avatars, reactions and
file previews — more chat than we have, from a library with a citable number. The
reason it loses is not that it is a library; it is that the thing it would buy is
absent. Its message list is `renderList($props.messages, ...)`, not a virtualized
list, and the runtime measurement is decisive: **5,000 messages render 5,000
message nodes and 77,563 DOM nodes**, in a `#messages-list` scroller whose
`scrollHeight` is 380,994px. It is infinite-scroll pagination, not virtual
scrolling. The packaged ES bundle is 1,064,604 bytes raw / 212,355 gzip, against
the current `ChatPane` chunk's 9,957 bytes raw / 3,881 gzip. Its room model can be
fed server-gated data (the gate stays server-side either way), but it brings its
own markdown parser and its own nested scroller — the exact layout class that
made the conversation page unreadable once already.

**Falsifier:** if a future conversation pane needs reactions, attachments or a
chat-style room switcher more than it needs a readable document, re-run this
benchmark against the then-current version and compare DOM nodes, scroll
container and gzip size. If that version virtualizes while keeping the gate
server-side, the hand-built reader loses and this row changes. Until then, the
current reader is the smaller and more honest component: it renders markdown and
scrolls as a page, and it does not pretend to virtualize.

**Built here, and stays built here:** the gate, the seals, the ledger. Not
candidates for a library. A "chat framework" with its own permissions model would
be a second implementation of the one rule this project exists to keep in one
place, and the project has measured where second implementations lead.

## 5. What "we could not find one" has to mean

Every "we built it ourselves" below is a claim that nothing qualifying existed,
and each carries the observation that would refute it:

* **The gantt.** `frappe/gantt` (6,124) and `dhtmlx` (1,853) both qualify or nearly
  do, and both draw from a task array with drag-to-reschedule. Ours is ECharts —
  an adopted, >1k framework — with custom series on top. The reason is not "ours is
  better": it is that the bars must show draft work differently from published
  work, and that is a fact about the fabric that no gantt library has ever heard
  of. Refuted if frappe/gantt grows a data adapter seam we can implement without
  forking; then the interaction layer (drag a bar to reschedule) is worth adopting
  and our custom series is not.
* **The DnD on the kanban.** Adopted, not built: `vue-draggable-plus`. It never
  writes; it prints the command a human would have typed. That is a design rule,
  not a limitation of the library.
* **The conversation reader.** See §4.
* **The kernel** (`web/src/kernel.js`, `aimboard/kernel.py`). No library was
  surveyed for this because there is nothing to survey: it is twelve lines that
  map a name to a service. The pattern is Cordis-shaped — `cordiverse/cordis`,
  8,712 stars, npm `cordis` 4.0.0-rc.10, the service container behind Koishi
  (6,216) — so the shape is copied from a citable framework rather than invented.
  Cordis itself is not installed: it is a Node framework for long-lived plugins,
  our kernel is per-request on the server (`aimboard/kernel.py`) and per-mount in
  the browser, and adopting it would add a lifecycle we do not have. Refuted if a
  plugin container from the ecosystem turns out to fit; then adopting it is right
  and our twelve lines are wrong, and the cost of finding that out is an afternoon.
