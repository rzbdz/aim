import { expect, test } from '@playwright/test'
import { PHASES, GLOSSARY } from '../src/concepts.js'

/**
 * The board is drawn from a fixed payload for these tests, so an assertion about
 * a filter is an assertion about the filter and not about whatever the live
 * fabric happens to hold today.
 */
const TASK = (id, title, owner, status, priority, milestone, tags, due, accept = '',
              extra = {}) => ({
  id, title, owner, status, priority, milestone, tags, due, accept,
  blocked_by: [], visibility: 'published', provenance: 'seed only (fixture)',
  events: [], comments: [], ...extra,
})

/**
 * A plan seed is a promise and a promise is not work (T-0180).
 *
 * The landing page counts and lists only what is on the record, so a fixture
 * whose items are all seeds tests the attention queue against an empty queue --
 * and an empty queue is a page that looks correct while asserting nothing about
 * the things it draws. `recorded` is what a seed looks like once someone has
 * actually written it down.
 */
const RECORDED = { provenance: 'store only' }

const KANBAN_STATE = {
  digest: 'kanban-filter-fixture',
  statuses: ['backlog', 'doing', 'review', 'done'],
  terminal: ['done'],
  phase: 'RESOLVE',
  milestones: { M1: { id: 'M1', name: 'One' }, M2: { id: 'M2', name: 'Two' } },
  agents: {},
  register: {},
  tasks: {
    // On the record, so the board these tests drive is one a reader can act on.
    'T-0001': TASK('T-0001', 'Alpha', 'codex', 'doing', 'normal', 'M1', ['ui'], '2026-09-20', '', RECORDED),
    'T-0002': TASK('T-0002', 'Beta', 'claude-session1', 'review', 'high', 'M2', ['api'], '2026-09-23', '', RECORDED),
    'T-0003': TASK('T-0003', 'Gamma', 'codex', 'backlog', 'low', 'M1', ['ui', 'api'], '2026-09-24', '', RECORDED),
  },
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
}

/**
 * The shell tests run against a fixed payload too.
 *
 * They used to assert against whatever the live fabric happened to hold, which
 * made them a measurement of today's data wearing the costume of a test about
 * the shell: on a board where every item was in `doing`, "the attention queue
 * opens a task" had nothing to open and the failure looked like a broken
 * drawer. A shell assertion should hold for any board, so it is fed a board
 * chosen to exercise it.
 */
const SHELL_STATE = {
  digest: 'shell-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'doing', 'review', 'done'],
  terminal: ['done'],
  phase: 'SEALED_DIVERGENT',
  milestones: { M1: { id: 'M1', name: 'First milestone', due: '2026-10-01', accept: 'shipped' } },
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' } },
  register: {},
  tasks: {
    'T-0001': { ...TASK('T-0001', 'Alpha needs a decision', 'codex', 'review', 'high', 'M1', ['ui'], '2026-09-20',
                       'the reviewer can falsify this sentence', RECORDED) },
    'T-0002': { ...TASK('T-0002', 'Beta is waiting on Alpha', 'claude-session1', 'blocked', 'normal', 'M1', [], '2026-09-25',
                       '', { blocked_by: ['T-0001'] }), ...RECORDED },
    // A promise: drawn on the page, counted as a promise, never counted as work.
    'T-0003': TASK('T-0003', 'Promised and not yet recorded', 'codex', 'doing', 'normal', 'M1', [], '2026-09-15'),
  },
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: {
    channels: [{ id: 'hello', phase: 'SEALED_DIVERGENT', gated: false, rule: 'fixture',
                 messages: [
                   { from: 'codex', to: 'hello', ts: '2026-09-22T00:01:00.000Z', kind: 'note', body: 'first message' },
                   { from: 'claude-session1', to: 'hello', ts: '2026-09-22T00:02:00.000Z', kind: 'note', body: 'second message' },
                 ] }],
    rooms: [],
    mail: [{ from: 'codex', to: 'human', ts: '2026-09-22T00:03:00.000Z', subject: 'handover',
             body: 'the fixture direct message', msg_id: 'fixture-dm', ack_required: true,
             acked_at: '', claimed_at: '', bytes: 42, state: 'unread' }],
  },
  channels: [{
    id: 'hello', phase: 'SEALED_DIVERGENT', topic: 'fixture channel', leader: 'human',
    participants: ['codex', 'claude-session1'], round: 0, sealed: [], concessions: 0,
    tasks_recorded: 0, tasks_unknown_events: 0,
    chain: { 'log.jsonl': { state: 'OK', records: 2, why: 'fixture' } },
    refusals: [{ ts: '2026-09-22T00:00:30.000Z', agent: 'codex', action: 'read_others',
                 class: 'barrier', phase: 'SEALED_DIVERGENT',
                 reason: 'the channel is sealed, so a peer draft cannot be read yet' }],
    history: [{ at: '2026-09-22T00:00:00.000Z', phase: 'SEALED_DIVERGENT', by: 'human', note: '' }],
  }],
  unacked: [{ msg_id: 'fixture-dm', from: 'codex', to: 'human', subject: '', bytes: 42 }],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: true, as: 'human' },
}

/** Serve the fixed shell board, and hold the digest still so nothing refreshes. */
async function serveShell(page) {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(SHELL_STATE),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: SHELL_STATE.digest }),
  }))
}

const routes = [
  ['attention', 'Attention'],
  ['kanban', 'Kanban'],
  ['gantt', 'Gantt'],
  ['items', 'Work items'],
  ['chat', 'Conversations'],
  ['reports', 'Reports'],
  ['barrier', 'Audit & barrier'],
  ['plan', 'Plan & risks'],
  // Ten, not nine: the org pane registered in `web/src/views/org.js` and rendered
  // at `#/org` from the start, but neither nav key list named it, so it had no
  // rendered entry point. It is in the shell's Governance group now, which is why
  // this list and the menu-item count below both moved by one. The number is not
  // a detail of this file: it is the only assertion that would go red if a pane
  // were ever registered and left unreachable again, so it is kept exact rather
  // than relaxed to `>= 9`.
  ['org', 'Org'],
  ['help', 'Help & concepts'],
]

test('every route is titled in English, and nothing renders a second language', async ({ page }) => {
  for (const [path, title] of routes) {
    await page.goto(`/#/${path}`)
    await expect(page.locator('.aim-page h2')).toHaveText(title)
  }
  // The nav is the shell's own copy of the same names; a menu that disagrees
  // with the heading is the second answer this project keeps finding.
  const menu = await page.locator('.el-menu-item').allTextContents()
  expect(menu.map((item) => item.trim()).sort())
    .toEqual(routes.map(([, title]) => title === 'Attention' ? 'Attention' : title).sort())
  // No CJK anywhere in the drawn document. The check is on the rendered text,
  // not the source, so a label reintroduced anywhere fails here.
  const cjk = await page.evaluate(() =>
    (/[一-鿿]/.exec(document.body.textContent) || [])[0] || '')
  expect(cjk).toBe('')
})

test('the opening page is an attention queue, not a data dump', async ({ page }) => {
  await serveShell(page)
  await page.goto('/#/attention')
  await expect(page.locator('.aim-page h2')).toHaveText('Attention')
  await expect(page.locator('.aim-attention-hero h3')).toBeVisible()
  // Six signals, one per thing the reader can act on: overdue, blocked, review,
  // phase requests, receipts owed, and plan disagreements. The count is asserted
  // rather than the labels because the point of the row is that it is short
  // enough to read -- a seventh signal is a decision about what matters.
  await expect(page.locator('.aim-attention-signals .aim-signal')).toHaveCount(6)
  await expect(page.locator('.el-table')).toHaveCount(0)
  await expect(page.locator('.el-menu-item').filter({ hasText: 'Kanban' })).toBeVisible()
  await expect(page.locator('.el-menu-item').filter({ hasText: 'Gantt' })).toBeVisible()
  const sections = await page.locator('.aim-attention .el-card__header').allTextContents()
  for (const expected of [
    'Work needing you nowsee all',
    'Latest conversationread and reply',
    'Next milestonesfull plan',
  ]) expect(sections.map((section) => section.trim())).toContain(expected)

  const firstTask = page.locator('.aim-attention-row.aim-clickable').first()
  await firstTask.click()
  await expect(page.locator('.el-drawer')).toBeVisible()
  await expect(page.locator('.el-drawer h3')).toBeVisible()
  await expect(page.locator('.aim-action-panel h4')).toHaveText('What the leader can do')
  await expect(page.locator('.aim-action-panel .el-button').first()).toBeVisible()
  await page.keyboard.press('Escape')

  await page.locator('.aim-signal').filter({ hasText: 'Overdue' }).click()
  await expect(page).toHaveURL(/#\/items\?onlyLate=1/)
  await expect(page.locator('.aim-filterbar .el-checkbox__input').first()).toHaveClass(/is-checked/)

  await page.locator('.el-menu-item').filter({ hasText: 'Kanban' }).click()
  await expect(page.locator('.aim-card').first()).toBeVisible()
  await page.locator('.aim-card').first().click()
  await expect(page.locator('.aim-action-panel h4')).toHaveText('What the leader can do')
})

test('conversation history and pinned input never overlap or reload the page', async ({ page }) => {
  await serveShell(page)
  let navigations = 0
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) navigations += 1
  })

  await page.goto('/#/chat')
  await expect(page.locator('.aim-page h2')).toHaveText('Conversations')
  const groups = await page.locator('.el-menu-item-group__title').allTextContents()
  expect(groups).toEqual([
    'Work',
    'Conversation',
    'Insight',
    'Governance',
    'Reference',
  ])
  expect(await page.locator('.el-menu-item').count()).toBe(10)
  await expect(page.locator('.aim-reader')).toBeVisible()
  await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    if (!history) throw new Error('the conversation history is missing')
    const message = document.createElement('article')
    message.className = 'aim-msg'
    message.dataset.testid = 'layout-fixture'
    message.textContent = 'layout fixture'
    const filler = document.createElement('div')
    filler.dataset.testid = 'layout-filler'
    filler.style.height = '2000px'
    history.append(message, filler)
  })
  await expect(page.locator('.aim-msg').first()).toBeVisible()
  const navigationsAfterLoad = navigations

  const layout = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    const composer = document.querySelector('.aim-composer')
    const input = document.querySelector('.aim-composer textarea')
    if (!history || !composer || !input) throw new Error('the conversation layout is incomplete')
    const historyBox = history.getBoundingClientRect()
    const composerBox = composer.getBoundingClientRect()
    return {
      historyOverflow: getComputedStyle(history).overflowY,
      historyCanScroll: history.scrollHeight > history.clientHeight,
      composerInsideHistory: history.contains(composer),
      historyEnd: historyBox.bottom,
      composerStart: composerBox.top,
      composerBottom: composerBox.bottom,
      viewportHeight: window.innerHeight,
      inputVisible: input.getBoundingClientRect().height > 0,
    }
  })

  expect(layout.historyOverflow).toBe('auto')
  expect(layout.historyCanScroll).toBe(true)
  expect(layout.composerInsideHistory).toBe(false)
  expect(layout.historyEnd).toBeLessThanOrEqual(layout.composerStart)
  expect(layout.inputVisible).toBe(true)
  expect(layout.composerBottom).toBeLessThanOrEqual(layout.viewportHeight + 1)

  const pinned = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    const composer = document.querySelector('.aim-composer')
    const before = composer.getBoundingClientRect().top
    history.scrollTop = history.scrollHeight
    return {
      before,
      after: composer.getBoundingClientRect().top,
      scrollTop: history.scrollTop,
      scrollHeight: history.scrollHeight,
    }
  })

  expect(pinned.scrollTop).toBeGreaterThan(0)
  expect(Math.abs(pinned.after - pinned.before)).toBeLessThanOrEqual(1)

  const marker = await page.evaluate(() => window.__aimConversationRegressionMarker = 'still-mounted')
  await page.waitForTimeout(16_000)
  await expect(page.locator('.aim-reader')).toBeVisible()
  await expect.poll(() => page.evaluate(() => window.__aimConversationRegressionMarker)).toBe(marker)
  expect(navigations).toBe(navigationsAfterLoad)
  await page.evaluate(() => {
    document.querySelectorAll('[data-testid="layout-fixture"], [data-testid="layout-filler"]')
      .forEach((node) => node.remove())
  })
})

test('chat opens on the unread or newest anchor instead of the top of history', async ({ page }) => {
  await serveShell(page)
  const messages = Array.from({ length: 80 }, (_, index) => ({
    from: index % 2 ? 'claude-session1' : 'codex',
    ts: `2026-09-22T0${Math.floor(index / 30) % 10}:${String(index % 60).padStart(2, '0')}:00.000Z`,
    kind: 'note',
    body: `fixture message ${index}`,
  }))
  const state = {
    digest: 'chat-anchor-fixture',
    statuses: ['backlog'],
    terminal: ['done'],
    phase: 'RESOLVE',
    milestones: {},
    agents: {},
    register: {},
    tasks: {},
    reports: { series: [], throughput: [], blocked: [], median_cycle: null },
    conversation: {
      channels: [{ id: 'hello', phase: 'RESOLVE', gated: false, rule: 'fixture', messages }],
      rooms: [],
      mail: [],
    },
    unacked: [],
    drift: [],
    withheld_tasks: 0,
    write: { enabled: false, as: '' },
  }
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify(state),
  }))

  await page.goto('/#/chat')
  await expect(page.locator('.aim-anchor-message')).toBeVisible()
  const result = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    const anchor = document.querySelector('.aim-anchor-message')
    if (!history || !anchor) throw new Error('anchor layout is missing')
    const historyBox = history.getBoundingClientRect()
    const anchorBox = anchor.getBoundingClientRect()
    return {
      scrollTop: history.scrollTop,
      anchorVisible: anchorBox.top >= historyBox.top - 1 && anchorBox.bottom <= historyBox.bottom + 1,
    }
  })
  expect(result.scrollTop).toBeGreaterThan(0)
  expect(result.anchorVisible).toBe(true)
})

test.describe('the kanban filter bar', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(KANBAN_STATE),
    }))
  })

  const ids = (page) => page.locator('.aim-card .aim-id').allTextContents()
  const drawn = async (page, query, expected) => {
    await page.goto(`/#/kanban${query}`)
    await expect(page.locator('.aim-card').first()).toBeVisible()
    await expect.poll(() => ids(page)).toEqual(expected)
  }
  /** What a filter control offers. Addressed by its hook, not by its position:
   *  a test that counts select boxes breaks the day someone adds a filter, and
   *  that is a test failing for the wrong reason. */
  const options = async (page, name) => {
    await page.locator(`.aim-filterbar [data-filter="${name}"]`).click()
    const items = page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
    await expect(items.first()).toBeVisible()
    const texts = await items.allTextContents()
    await page.keyboard.press('Escape')
    return texts.map((item) => item.trim())
  }

  test('every filter narrows the board, and each one narrows it differently', async ({ page }) => {
    await drawn(page, '', ['T-0003', 'T-0001', 'T-0002'])
    await drawn(page, '?owner=codex', ['T-0003', 'T-0001'])
    await drawn(page, '?priority=normal', ['T-0001'])
    await drawn(page, '?milestone=M2', ['T-0002'])
    await drawn(page, '?q=Gamma', ['T-0003'])
    await drawn(page, '?onlyLate=1', ['T-0001'])
    await drawn(page, '?owner=codex&priority=normal', ['T-0001'])
  })

  test('a multi-tag filter is an AND, and it survives the URL', async ({ page }) => {
    await drawn(page, '?tag=ui', ['T-0003', 'T-0001'])
    await drawn(page, '?tag=api', ['T-0003', 'T-0002'])
    await drawn(page, '?tag=ui&tag=api', ['T-0003'])

    // The picker and the URL are one state: choosing a second tag must write
    // both, or a copied link loses half the filter.
    await page.goto('/#/kanban?tag=ui')
    await expect.poll(() => ids(page)).toEqual(['T-0003', 'T-0001'])
    const tagSelect = page.locator('.aim-filterbar [data-filter="tag"]')
    await tagSelect.click()
    await page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
      .filter({ hasText: 'api' }).click()
    await page.keyboard.press('Escape')
    await expect.poll(() => ids(page)).toEqual(['T-0003'])
    await expect.poll(() => new URL(page.url()).hash).toContain('tag=ui')
    expect(new URL(page.url()).hash).toContain('tag=api')
  })

  test('the priority list is the board vocabulary, with no invented middle', async ({ page }) => {
    await page.goto('/#/kanban')
    await expect(page.locator('.aim-card').first()).toBeVisible()
    // Both halves matter: the *set* is what the board holds (no invented middle),
    // and the *order* is the canonical one, so the options do not shuffle as the
    // board changes under them.
    const priorities = await options(page, 'priority')
    expect(priorities).toEqual(['high', 'normal', 'low'])
    expect(priorities).not.toContain('medium')
    // A status the board knows and the filters emptied is still a column: the
    // page reports it as empty rather than deleting the workflow stage from the
    // board because a filter hid its cards.
    await page.goto('/#/kanban?priority=normal')
    await expect.poll(() => ids(page)).toEqual(['T-0001'])
    await expect(page.locator('.aim-col')).toHaveCount(4)
    await expect(page.locator('.aim-col').filter({ hasText: 'review' })).toContainText('0')
  })

  test('a route change replaces the filters instead of accumulating them', async ({ page }) => {
    // Each of these is a link someone could paste. The URL names one filter, and
    // the board must show one filter: a pane that only ever sets the keys the URL
    // mentions keeps whatever the last route left behind, and the reader gets a
    // board narrowed by a query they never typed.
    await drawn(page, '?owner=codex&priority=normal', ['T-0001'])
    await drawn(page, '?milestone=M2', ['T-0002'])
    await drawn(page, '?q=Gamma', ['T-0003'])
    await drawn(page, '?tag=api&tag=ui', ['T-0003'])

    // Leaving the route and coming back is the same rule seen from the other
    // side: the nav carries no query, so the pane is rebuilt unnarrowed. A board
    // that came back still filtered would be showing a query the URL no longer
    // holds, which is the failure this whole rule exists to prevent.
    await page.locator('.el-menu-item').filter({ hasText: 'Work items' }).click()
    await expect(page.locator('.aim-page h2')).toHaveText('Work items')
    await page.locator('.el-menu-item').filter({ hasText: 'Kanban' }).click()
    await expect(page.locator('.aim-page h2')).toHaveText('Kanban')
    await expect.poll(() => ids(page)).toEqual(['T-0003', 'T-0001', 'T-0002'])
    expect(new URL(page.url()).hash).toBe('#/kanban')
  })

  test('cards open the current task, not the one that was open before', async ({ page }) => {
    await page.goto('/#/kanban')
    await page.locator('.aim-card[data-id="T-0002"]').click()
    await expect(page.locator('.el-drawer')).toBeVisible()
    await expect(page.locator('.el-drawer h3')).toHaveText('Beta')
    await page.keyboard.press('Escape')
    await expect(page.locator('.el-drawer')).toBeHidden()

    await page.locator('.aim-card[data-id="T-0001"]').click()
    await expect(page.locator('.el-drawer h3')).toHaveText('Alpha')
    // The drawer is showing the task the reader clicked, with the state the
    // board currently holds for it - not a copy captured when the pane mounted.
    await expect(page.locator('.el-drawer')).toContainText('T-0001')
    await expect(page.locator('.el-drawer')).toContainText('codex')
  })

  test('a filter change does not drag the columns out from under a computed', async ({ page }) => {
    await page.goto('/#/kanban?priority=low')
    await expect.poll(() => ids(page)).toEqual(['T-0003'])
    await page.goto('/#/kanban')
    await expect.poll(() => ids(page)).toEqual(['T-0003', 'T-0001', 'T-0002'])
    await page.goto('/#/kanban?priority=low')
    await expect.poll(() => ids(page)).toEqual(['T-0003'])
    await page.goto('/#/kanban')
    await expect.poll(() => ids(page)).toEqual(['T-0003', 'T-0001', 'T-0002'])
  })
})

test('a phase is said in English, and the enum stays available but secondary', async ({ page }) => {
  await serveShell(page)
  await page.goto('/#/attention')
  const chip = page.locator('.aim-header .aim-phase-chip')
  await expect(chip).toBeVisible()
  // The header says what the phase means for the reader, in words. The protocol
  // value is one hover away, deliberately: it is what you quote in a bug report.
  await expect(chip).not.toContainText('SEALED_DIVERGENT')
  await expect(chip).toContainText('Sealed')
  await expect(page.locator('.aim-header-phase')).toContainText('Positions are being formed in private')
  await chip.hover()
  await expect(page.locator('.el-popper:visible')).toContainText('SEALED_DIVERGENT')

  // The same rule inside the audit page, which is where the enum used to be drawn
  // raw in the tab, the descriptions table, the refusal filter and the history.
  // No surface in the audit page may show a raw phase as its label -- the enum is
  // only allowed where a reader asked for it (a tooltip).
  await page.goto('/#/barrier')
  const tabs = await page.locator('.el-tabs__item').allTextContents()
  expect(tabs.length).toBeGreaterThan(0)
  for (const tab of tabs) {
    expect(tab).not.toMatch(/SEALED_DIVERGENT|CROSS_EXAMINE|SYNTHESIS/)
  }
  expect(tabs.join(' ')).toContain('Sealed')
  const visible = await page.locator('.aim-main').innerText()
  for (const phase of PHASES) expect(visible).not.toContain(phase.key)
})

test('help explains every phase and every concept a chip can link to', async ({ page }) => {
  await serveShell(page)
  await page.goto('/#/help')
  await expect(page.locator('.aim-page h2')).toHaveText('Help & concepts')

  // The anchors the chips link to are the ones the dictionary declares, read from
  // the module itself rather than retyped here. A page that documents five of six
  // phases, or names an anchor the chips do not use, is the drift this catches.
  expect(PHASES.map((phase) => phase.key)).toEqual([
    'SEALED_DIVERGENT', 'COMMIT', 'SYNTHESIS', 'CROSS_EXAMINE', 'RESOLVE', 'CLOSED',
  ])
  for (const phase of PHASES) {
    await expect(page.locator(`#phase-${phase.key.toLowerCase()}`)).toHaveCount(1)
  }
  // Each phase says what it does to the reader, not only what it is called.
  await expect(page.locator('#phase-resolve')).toContainText('You can read everything and say nothing new')
  await expect(page.locator('#phase-sealed_divergent')).toContainText('the tool refuses')

  for (const entry of GLOSSARY) {
    await expect(page.locator(`#${entry.anchor}`)).toHaveCount(1)
  }
  // A concept link goes somewhere real, so the page does not leave the reader with
  // a term they cannot act on.
  await page.locator('#independent-positions a').first().click()
  await expect(page.locator('.aim-page h2')).toHaveText('Audit & barrier')
})

test('a phase chip links to the explanation of that phase, and is reachable by keyboard', async ({ page }) => {
  await serveShell(page)
  await page.goto('/#/attention')
  const chip = page.locator('.aim-header a.aim-phase-chip').first()
  await expect(chip).toHaveAttribute('href', /#\/help#phase-sealed_divergent$/)
  await chip.press('Enter')
  await expect(page.locator('.aim-page h2')).toHaveText('Help & concepts')
  await expect(page.locator('#phase-sealed_divergent')).toBeVisible()
})
