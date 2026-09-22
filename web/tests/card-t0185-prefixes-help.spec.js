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
const ROUTES = ['/attention', '/items', '/chat', '/kanban', '/gantt', '/plan', '/barrier', '/help', '/reports']

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

async function open(page, route) {
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
  await expect(page.locator('.aim-main, .aim-reader, main').first()).toBeVisible()
}

test.describe('T-0185: every identifier in the text has a way in', () => {
  test('the walk: no route renders a token with nowhere to go', async ({ page }) => {
    test.fail(true,
      'T-0185 FAIL (bundle 870b282+dirty, stale): unlinked tokens per route -- /attention 1, '
      + '/items 3 (T-0001, M1, M2), /barrier 6 (every phase enum in the refusal strip), /help 13, '
      + '/kanban 3, /gantt 1. /plan links M1/M2 as router links and is clean. Help\'s identifier '
      + 'rows carry no id at all (HelpPane.vue:381 has no :id, against :282 and :323), so even a '
      + 'link to D7 or R1 would have nothing to land on.')
    const failures = []
    for (const route of ROUTES) {
      await open(page, route)
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
    await open(page, '/help')
    const identifierRows = page.locator('#identifiers tr')
    const phaseRows = page.locator('#phases tr')
    await expect(identifierRows.first()).toBeVisible()
    await expect(phaseRows.first()).toBeVisible()

    const ids = (locator) => locator.evaluateAll((els) => els.map((el) => el.id))
    const ident = await ids(identifierRows)
    const phase = await ids(phaseRows)
    expect(phase.filter(Boolean).length, 'the phase rows are addressable').toBeGreaterThan(0)
    expect(ident.filter(Boolean).length, "Help's identifier rows carry ids")
      .toBe(ident.length)
  })

  test('every phase chip in the panes lands on an element that exists', async ({ page }) => {
    // Acceptance 1's second half. A link that names an id nothing carries is a
    // link that cannot arrive, and it is invisible to a reader until they click.
    const broken = []
    for (const route of ROUTES) {
      await open(page, route)
      const anchors = await page.locator('a[href^="#"]:not([href^="#/"])').evaluateAll(
        (els) => els.map((el) => el.getAttribute('href').slice(1)))
      for (const fragment of anchors) {
        if (!await page.evaluate((id) => Boolean(document.getElementById(id)), fragment)) {
          broken.push(`${route}: #${fragment}`)
        }
      }
    }
    expect(broken, 'in-page links whose id is not in the DOM').toEqual([])
  })
})
