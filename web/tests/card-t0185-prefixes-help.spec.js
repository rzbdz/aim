/**
 * T-0185 -- "The D and R prefixes and the raw phase enums have no way in, and
 * Help has nothing to land on".
 *
 * Card text (`channels/hello/tasks.jsonl`, `created` 2026-09-22T07:12:31.836Z,
 * actor codex) and its `commented` body, acceptance verbatim:
 *
 *   "1. Every rendered T#/M#/D#/R# and every raw phase enum in user-facing text
 *    is inside an <a> whose href resolves to an element id present in the DOM, and
 *    clicking it brings that element into the viewport.
 *    2. Help's identifier rows and its phase rows carry stable ids.
 *    3. A test walks each route, collects every such token in the rendered text,
 *    and fails on any that is neither inside a link nor inside the drawer
 *    control."
 *
 * Revision measured -- `GET http://127.0.0.1:8777/api/revision` on 2026-09-22,
 * before the run below:
 *
 *   fabric 8dad368+dirty
 *   bundle 870b282+dirty, built 2026-09-22T08:40:07.787Z, source "vite build"
 *   stale: true  (the bundle is not built from a clean tree)
 *
 * ---------------------------------------------------------------------------
 * What counts as a token having a way in. Acceptance 1 read literally would fail
 * Help itself, whose job is to *name* the vocabulary: a phase row that linked
 * `SEALED_DIVERGENT` to `#phase-sealed-divergent` would be a row linking to
 * itself. So a token passes if any of these holds, and the exemption is in the
 * test rather than in the assertion:
 *
 *   * it is inside an `<a>` whose `href` is an in-page fragment (`#foo`, not the
 *     router's `#/foo`) that resolves to an element in the DOM;
 *   * it is inside a row or section that itself carries an `id` -- the definition
 *     the token would link to. That is what acceptance 2 is for, and it is why an
 *     unanchored Help row is a failure and not a pass;
 *   * it is inside the drawer's control (`.aim-row-decisions`, or the inspect
 *     button), which acceptance 3 names explicitly.
 *
 * Everything else is the defect the card describes: a token the reader can see
 * and cannot follow.
 *
 * ---------------------------------------------------------------------------
 * VERDICT: FAIL on all three clauses. Measured on the bundle above, viewer
 * `human`, one task (T-0001), two milestones (M1, M2), two decisions (D5, D6) and
 * three risks (R1..R3) in the fixture:
 *
 *   route        tokens  unlinked  broken links
 *   /attention        1         1   0
 *   /items            3         3   0
 *   /plan             2         0   0   (M1/M2 are router links, not anchors)
 *   /barrier          6         6   0
 *   /help            13        13   0
 *   /chat             0         0   0
 *   /kanban           3         3   0
 *   /gantt            1         1   0
 *   /reports          0         0   0
 *
 * and Help's identifier rows carry no `id` at all: `tr :id` is present on the
 * phase rows (`HelpPane.vue:282`) and on the access rows (`:323`), and absent on
 * the identifier rows (`:381`). The four unlinked faults the card names by hand --
 * `D5/D6` in the decisions table, `R1..R3` in the risks table, the phase enums in
 * the barrier refusals, and the refusal rows with no anchor -- are all present.
 *
 * ---------------------------------------------------------------------------
 * RE-MEASURED 2026-09-22 on bundle `001be7a` (`GET /api/revision`, `stale:
 * false`). The verdict table above is history, not current: two of its three
 * clauses pass today, and the numbers in it are not the numbers the walk now
 * reports. What the walk reports is 13 unreachable tokens over FOUR routes --
 * /attention 3 (`T-0001`, `T-0001`, `M1`), /items 2, /kanban 3, /plan 5
 * (`R1 R2 R3 D5 D6`). /barrier and /help are 0 under this fixture.
 *
 * Those 13 split, and the split is the finding:
 *
 *   * SIX ARE THE PREDICATE, NOT THE PRODUCT. `T-0001` is drawn as a control on
 *     all three panes that show it: `TaskLink.vue:74` is a `<button
 *     class="aim-task-link" aria-label="Open work item T-0001">` and the
 *     attention and kanban rows are `article[role="button"]` whose `aria-label`
 *     is `Open task T-0001: …`. The acceptance names `<a>` and `reachable()`
 *     honours exactly two drawer shapes (`.aim-row-decisions`,
 *     `[aria-label^="Inspect task"]`), so a control that opens the drawer by
 *     *any other* name reads as a dead end. The board deliberately chose a
 *     button over an anchor here -- `ItemsPane.vue:470-473` says why (a native
 *     anchor would drag the URL onto the hash and the drawer would never open)
 *     -- so the predicate contradicts a decision the product made on purpose.
 *
 *   * SEVEN ARE REAL AND ARE THE CARD'S OWN SUBJECT: `M1` on /attention and
 *     /kanban (bare interpolations, `OverviewPane.vue:767`, `KanbanPane.vue:453`
 *     -- note /plan and /items link their milestone cells, so the destination
 *     exists and two of the four sites just do not use it), and `R1 R2 R3 D5 D6`
 *     on /plan (`PlanPane.vue:394` is a bare `prop="id"` column and `:408` puts
 *     the decision id in a collapse header, neither addressable). Those seven
 *     have no target anywhere in the product except Help's own `#prefix-r` /
 *     `#prefix-d` rows.
 *
 * And the predicate is too broad in the other direction, which is why its count
 * cannot be read as a defect count: it walks `document.body`, so it sees the
 * `el-popper` subtrees of the filter dropdowns -- invisible `li`/`div` option
 * rows that happen to carry Element Plus's generated `el-id-<n>`, which
 * `atDefinition` accepts as a definition row. Measured on /attention: 0 bad
 * tokens with the pointer still, 1 with a phase chip hovered. A walk whose
 * answer depends on where the mouse is has no stable number, and this test's
 * green (it is `test.fail(true, …)`) says nothing about which of the 13 are
 * real. The seven above are named so the card is not closed on the strength of
 * a count that moves.
 */
import { expect, test } from '@playwright/test'

const PHASES = ['SEALED_DIVERGENT', 'COMMIT', 'SYNTHESIS', 'CROSS_EXAMINE', 'RESOLVE', 'CLOSED']

const task = (id, extra = {}) => ({
  id, status: 'review', provenance: '', owner: 'human', channel: 'hello', priority: 'normal',
  title: `work ${id}`, tags: [], blocked_by: [], events: [], comments: [],
  milestone: 'M1', due: '', start: '', accept: '', visibility: 'published', ...extra,
})

const STATE = () => ({
  digest: 'card-t0185', generated_at: '2026-09-22T03:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'RESOLVE',
  milestones: {
    M1: { id: 'M1', name: 'the first milestone', due: '2026-09-30', accept: 'a sentence' },
    M2: { id: 'M2', name: 'the second milestone', due: '', accept: '' },
  },
  agents: { human: { kind: 'human', model: '' } }, tasks: { 'T-0001': task('T-0001') },
  // The plan's own vocabulary, which is where `D` and `R` come from
  // (`PlanPane.vue:13` reads `board.register`).
  register: {
    decisions: [
      { id: 'D5', decision: 'a decision with a reason', because: 'because', status: 'open' },
      { id: 'D6', decision: 'another decision', because: 'because', status: 'open' },
    ],
    risks: [
      { id: 'R1', risk: 'a risk', mitigation: 'a mitigation', owner: 'human', kill_if: 'if' },
      { id: 'R2', risk: 'another risk', mitigation: 'a mitigation', owner: 'human', kill_if: 'if' },
      { id: 'R3', risk: 'a third risk', mitigation: 'a mitigation', owner: 'human', kill_if: 'if' },
    ],
  },
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  viewer: 'human',
  conversation: {
    viewer: 'human', is_leader: true, rooms: [], mail: [], withheld: 0,
    channels: [{ id: 'hello', topic: 'the channel this is about', phase: 'SEALED_DIVERGENT', gated: false, rule: '',
                 messages: [{ from: 'codex', to: 'hello', ts: '2026-09-22T01:00:00.000Z', kind: 'note', body: 'a message' }] }],
  },
  channels: [{ id: 'hello', topic: 'the channel this is about', phase: 'SEALED_DIVERGENT', gated: false, rule: '' }],
  unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
})

/** Every route the shell registers (`web/src/views/*.js`). */
/**
 * Every route the shell registers (`web/src/views/*.js`), with the heading the
 * shell draws for it.
 *
 * The heading is what `open()` asserts against, because the hash is committed
 * before the lazy pane is: `.aim-main` exists in every frame, so waiting on it
 * is satisfied by the pane the reader is leaving. The strings are the `title` of
 * each `views/*.js`, which is what `App.vue` renders into `.aim-page h2`.
 */
const ROUTES = [
  ['/attention', 'Attention'], ['/items', 'Work items'], ['/chat', 'Conversations'],
  ['/kanban', 'Kanban'], ['/gantt', 'Gantt'], ['/plan', 'Plan & risks'],
  ['/barrier', 'Audit & barrier'], ['/help', 'Help & concepts'], ['/reports', 'Reports'],
]

/**
 * Every token in the rendered text that names a work item, a milestone, a
 * decision, a risk or a phase, with what the reader can do about it.
 *
 * Read in the page, by walking text nodes -- a token inside a link and the same
 * token inside a `<b>` are different facts, and `innerText` cannot tell them
 * apart.
 */
const collectTokens = (page, phases) => page.evaluate((phaseNames) => {
  const TOKEN = new RegExp(`\\b(?:[TMDR]-?\\d+|${phaseNames.join('|')})\\b`, 'g')
  const out = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  let node
  while ((node = walker.nextNode())) {
    TOKEN.lastIndex = 0
    let match
    while ((match = TOKEN.exec(node.textContent))) {
      const el = node.parentElement
      const anchor = el?.closest('a')
      const href = anchor?.getAttribute('href') || ''
      // `#/items?milestone=M1` is a router link; `#phase-commit` is an anchor.
      const fragment = href.startsWith('#') && !href.startsWith('#/') ? href.slice(1) : ''
      out.push({
        token: match[0],
        linked: Boolean(anchor),
        fragment,
        // An anchor whose id is in the DOM is a way in; one whose id is not is a
        // link that cannot arrive.
        resolves: fragment ? Boolean(document.getElementById(fragment)) : null,
        // The definition row: an id on the row itself is the thing a link would
        // land on, so a token on it has a way in even though it is not a link.
        atDefinition: Boolean(el?.closest('tr[id], article[id], section[id], li[id]')),
        inDrawer: Boolean(el?.closest('.aim-row-decisions, [aria-label^="Inspect task"]')),
      })
    }
  }
  return out
}, phases)

const reachable = (t) => (t.linked && (t.fragment ? t.resolves : true)) || t.atDefinition || t.inDrawer

/**
 * Land on a route, and be sure it is the route that rendered.
 *
 * The heading is the gate, not `.aim-main`: every pane's frame has `.aim-main`,
 * and the hash is committed before the lazy chunk resolves, so a wait on either
 * alone is satisfied by the pane the reader is leaving. `App.vue` draws
 * `.aim-page h2` from the route's own `title`, and `vue-router` commits only
 * after the chunk has resolved -- so a heading naming this route is this route
 * being on screen. Measured on a cold `/reports`: without this gate the walk
 * collected Help's nine anchors and resolved eight of them as missing.
 */
async function open(page, route, title) {
  await page.route('**/api/state**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE()),
  }))
  await page.route('**/api/digest**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: 'card-t0185' }),
  }))
  // `domcontentloaded`, not the default `load`: on the bundle served while this
  // file was written (cf1ab42+dirty) the `load` event never fires -- the app
  // mounts in ~1.8s and `load` is still pending 15s later. That is a fact about
  // the bundle, not about this test, and it is recorded here rather than waited
  // out.
  await page.goto(`/#${route}`, { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.aim-page h2')).toHaveText(title)
}

test.describe('T-0185: every identifier in the text has a way in', () => {
  test('the walk: no route renders a token with nowhere to go', async ({ page }) => {
    test.fail(true,
      'T-0185 re-measured 2026-09-22 on bundle 001be7a (stale false): 13 unreachable tokens over four '
      + 'routes, and the split is in this file\'s header. SIX are the predicate, not the product -- '
      + '`T-0001` is a control on all three panes (TaskLink.vue:74 is a `<button class="aim-task-link" '
      + 'aria-label="Open work item T-0001">`, and the attention and kanban rows are '
      + '`article[role="button"]`), but `reachable()` honours only `<a>`, `tr/article/section/li[id]` '
      + 'and the two drawer shapes, so a drawer control under any other name reads as a dead end. '
      + 'SEVEN are real and are the card\'s own subject: `M1` bare-interpolated on /attention '
      + '(OverviewPane.vue:767) and /kanban (KanbanPane.vue:453), and `R1 R2 R3 D5 D6` on /plan '
      + '(PlanPane.vue:394 is a bare prop column, :408 a collapse header). The count is not stable '
      + 'enough to close the card on -- it walks `document.body`, so the filter dropdowns\' hidden '
      + '`el-popper` option rows count as definition rows when Element Plus gives them a generated '
      + '`el-id-<n>`, and a hovered phase chip adds a token. Measured: 0 bad on /attention with the '
      + 'pointer still, 1 hovered. '
      + 'ORIGINAL: unlinked tokens per route -- /attention 1, /items 3 (T-0001, M1, M2), /barrier 6 '
      + '(every phase enum in the refusal strip), /help 13, /kanban 3, /gantt 1. /plan links M1/M2 as '
      + 'router links and is clean. Help\'s identifier rows carry no id at all, so even a link to D7 '
      + 'or R1 would have nothing to land on.')
    const failures = []
    for (const [route, title] of ROUTES) {
      await open(page, route, title)
      const tokens = await collectTokens(page, PHASES)
      const bad = tokens.filter((t) => !reachable(t))
      failures.push({ route, tokens: tokens.length, bad: bad.map((t) => t.token) })
    }
    // Named so the failure is a list of facts. The assertion is the whole table:
    // a route that renders three identifiers and links none of them is the defect
    // the card was filed about, and it is reported per route rather than as one
    // number so a partial fix is visible as progress instead of as a pass.
    expect(failures.filter((f) => f.bad.length), 'routes with a token that has nowhere to go')
      .toEqual([])
  })

  test("Help's identifier rows and phase rows carry stable ids", async ({ page }) => {
    // Acceptance 2. The phase rows have ids and the identifier rows do not, which
    // is what makes the `D`/`R` vocabulary unlandable: the pane that explains the
    // prefixes is the one pane a prefix cannot link to.
    await open(page, '/help', 'Help & concepts')
    // `#identifiers` is the id of the *section card* (`HelpPane.vue` puts it on
    // the `el-card`), so `#identifiers tr` counts the header row too: measured
    // 5 rows and 4 ids, with the 4 being `prefix-t/-m/-d/-r` on the body rows.
    // The header is not an identifier row and the acceptance is about the rows
    // that carry a prefix, so the query is scoped to the table's body. Re-measured
    // 2026-09-22T11:41Z on bundle 59b99a9+dirty (stale false), three runs, green.
    const identifierRows = page.locator('#identifiers tbody tr')
    const phaseRows = page.locator('#phases tbody tr')
    await expect(identifierRows.first()).toBeVisible()
    await expect(phaseRows.first()).toBeVisible()

    const ids = (locator) => locator.evaluateAll((els) => els.map((el) => el.id))
    const ident = await ids(identifierRows)
    const phase = await ids(phaseRows)
    expect(ident.length, 'the identifier table has no body rows, so "every row carries an id" is not measurable')
      .toBeGreaterThan(0)
    expect(phase.filter(Boolean).length, 'the phase rows are addressable').toBeGreaterThan(0)
    expect(ident.filter(Boolean).length, "Help's identifier rows carry ids")
      .toBe(ident.length)
  })

  test('every phase chip in the panes lands on an element that exists', async ({ page }) => {
    // Acceptance 1's second half. A link that names an id nothing carries is a
    // link that cannot arrive, and it is invisible to a reader until they click.
    //
    // How the pair is read matters, and it cost this test a false red. The links
    // are collected in one round trip and then each fragment is resolved in a
    // *second* one, and `open()` waits on `.aim-main`, which every pane's frame
    // has. On a cold route that wait is satisfied by the pane the reader is
    // leaving, so the collect can happen against Help's frame and the resolve
    // against the frame that replaced it -- measured on `/reports`: nine anchors
    // collected (Help's eight sections plus the shell's `#aim-main`), eight of
    // them reported broken, `#aim-main` the only one that still resolved. That is
    // the signature of the race, not of a missing id: Help and its eight sections
    // resolve together or not at all.
    //
    // Both halves are therefore resolved in the same round trip as the collect,
    // and `open()` asserts the route it asked for is the one on screen, so a
    // lagged frame cannot be measured as this route's. Neither change relaxes the
    // assertion: every link still has to name an id that is in the DOM.
    const broken = []
    for (const [route, title] of ROUTES) {
      await open(page, route, title)
      const read = await page.evaluate(() => [...document.querySelectorAll('a[href^="#"]:not([href^="#/"])')]
        .map((el) => el.getAttribute('href').slice(1))
        .map((fragment) => ({ fragment, resolves: Boolean(document.getElementById(fragment)) })))
      for (const { fragment, resolves } of read) {
        if (!resolves) broken.push(`${route}: #${fragment}`)
      }
    }
    expect(broken, 'in-page links whose id is not in the DOM').toEqual([])
  })
})
