import { expect, test } from '@playwright/test'

/**
 * The board is drawn from a fixed payload for these tests, so an assertion about
 * a filter is an assertion about the filter and not about whatever the live
 * fabric happens to hold today.
 */
const TASK = (id, title, owner, status, priority, milestone, tags, due, accept = '') => ({
  id, title, owner, status, priority, milestone, tags, due, accept,
  blocked_by: [], visibility: 'published', provenance: 'seed only (fixture)',
  events: [], comments: [],
})

const KANBAN_STATE = {
  digest: 'kanban-filter-fixture',
  statuses: ['backlog', 'doing', 'review', 'done'],
  terminal: ['done'],
  phase: 'RESOLVE',
  milestones: { M1: { id: 'M1', name: 'One' }, M2: { id: 'M2', name: 'Two' } },
  agents: {},
  register: {},
  tasks: {
    'T-0001': TASK('T-0001', 'Alpha', 'codex', 'doing', 'normal', 'M1', ['ui'], '2026-09-20'),
    'T-0002': TASK('T-0002', 'Beta', 'claude-session1', 'review', 'high', 'M2', ['api'], '2026-09-23'),
    'T-0003': TASK('T-0003', 'Gamma', 'codex', 'backlog', 'low', 'M1', ['ui', 'api'], '2026-09-24'),
  },
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
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
  await page.goto('/#/attention')
  await expect(page.locator('.aim-page h2')).toHaveText('Attention')
  await expect(page.locator('.aim-attention-hero h3')).toBeVisible()
  await expect(page.locator('.aim-attention-signals .aim-signal')).toHaveCount(5)
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
  ])
  expect(await page.locator('.el-menu-item').count()).toBe(8)
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
