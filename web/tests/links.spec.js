import { expect, test } from '@playwright/test'

/**
 * T-0159: no dead-end identifiers, no dead-end summary signals.
 *
 * Every assertion here is the same claim in a different place: a thing that looks
 * like it is about a work item has to *be* about that work item, and a summary
 * that says something needs action has to land on the thing that needs it. A
 * count with nothing behind it is worse than no count, because it teaches the
 * reader that the numbers are decoration.
 *
 * The board is fixed so that each surface has something to point at, including
 * one blocker id the board does *not* hold -- the case where a link has to do
 * something sensible instead of being a control that does nothing.
 */

const TASK = (id, title, owner, status, priority, milestone, tags, due, extra = {}) => ({
  id, title, owner, status, priority, milestone, tags, due, accept: `acceptance for ${id}`,
  blocked_by: [], visibility: 'published', provenance: 'seed only (fixture)',
  events: [], comments: [], ...extra,
})

const LINKS_STATE = {
  digest: 'links-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'doing', 'review', 'blocked', 'done'],
  terminal: ['done'],
  phase: 'RESOLVE',
  milestones: { M1: { id: 'M1', name: 'First milestone', due: '2026-10-01', accept: 'shipped' } },
  agents: { human: { kind: 'human', model: '' } },
  register: {},
  tasks: {
    'T-0001': TASK('T-0001', 'Alpha is being worked on', 'codex', 'review', 'high', 'M1', ['ui'], '2026-09-20'),
    'T-0002': TASK('T-0002', 'Beta waits on Alpha', 'claude-session1', 'blocked', 'normal', 'M1', [], '2026-09-25',
                   { blocked_by: ['T-0001', 'T-9000'] }),
  },
  reports: {
    series: [{ date: '2026-09-22', remaining: 2, done: 0 }],
    throughput: [],
    blocked: [{ id: 'T-0002', title: 'Beta waits on Alpha', status: 'blocked', owner: 'claude-session1',
                blocked_by: ['T-0001'] }],
    median_cycle: null, recorded: 2, with_history: 1, seed_only: 0,
  },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift: [{ id: 'T-0001', field: 'status', plan: 'doing', store: 'review' }],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
}

test.describe('identifiers and summaries are ways in', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(LINKS_STATE),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: LINKS_STATE.digest }),
    }))
  })

  test('a summary signal lands on the list it counted', async ({ page }) => {
    await page.goto('/#/attention')
    const signals = page.locator('.aim-attention-signals .aim-signal')
    await expect(signals).toHaveCount(6)

    // "Blocked 1" has to land on the blocked item, or the number is decoration.
    await signals.filter({ hasText: 'Blocked' }).click()
    await expect(page).toHaveURL(/#\/items\?status=blocked/)
    // The destination really is filtered, not merely reached: the one blocked
    // item is there and the unblocked one is not. (T-0002's *blocker* cell names
    // T-0001, which is a link rather than a row, so the check is on the rows.)
    const rows = page.locator('.el-table__body tr')
    await expect(rows).toHaveCount(1)
    await expect(rows.first()).toContainText('T-0002')
    await expect(page.locator('.el-table__body tr')).not.toContainText('being worked on')
  })

  test('a summary with nothing behind it is not a control', async ({ page }) => {
    await page.goto('/#/attention')
    const clear = page.locator('.aim-attention-signals .aim-signal.aim-signal-clear')
    // Phase requests and receipts owed are zero on this board; overdue, blocked,
    // review and plan disagreements are not.
    await expect(clear).toHaveCount(2)
    // `.aim-signal-clear` is rendered as a div, not a link: the reader cannot
    // click through to a list that is empty because there is nothing to see.
    for (const tile of await clear.all()) {
      expect(await tile.evaluate((el) => el.tagName)).toBe('DIV')
      expect(await tile.getAttribute('aria-disabled')).toBe('true')
    }
  })

  test('a blocker id opens the blocker task, from the board and from the report', async ({ page }) => {
    // In the items table only the *blocker* cell renders an id as a link, so this
    // selector is unambiguous. There are two things it must get right: it opens
    // the id that was clicked, and it does not also open the row it sits in --
    // T-0002 is the row, and T-0002's blocker is what was clicked.
    await page.goto('/#/items')
    await page.locator('.el-table__body .aim-task-link').filter({ hasText: 'T-0001' }).first().click()
    await expect(page.locator('.el-drawer')).toBeVisible()
    // Clicking a link inside a row must not *also* open the row: the id that was
    // clicked is the one that opens, not the row it happened to sit in.
    await expect(page.locator('.el-drawer h3')).toHaveText('Alpha is being worked on')

    await page.goto('/#/reports')
    await page.locator('.el-table__body .aim-task-link').filter({ hasText: 'T-0001' }).first().click()
    await expect(page.locator('.el-drawer h3')).toHaveText('Alpha is being worked on')
  })

  test('the drawer does not outlive the reading it belonged to', async ({ page }) => {
    // The drawer is mounted by the shell, so it survives the pane it was opened
    // from being torn down. That is what makes one drawer for every surface
    // possible, and it is also how a task ends up floating over a page that has
    // nothing to do with it -- the same defect as a dead-end identifier, one
    // layer up. So leaving the list closes the item.
    //
    // The way out here is back, not the nav: while the drawer is open its
    // overlay deliberately makes the page beneath inert, so the nav cannot be
    // clicked. Back is the route change that does happen underneath it. The
    // history is built by clicking, so this is a reader's history, not two
    // `goto`s to the same document.
    await page.goto('/#/plan')
    await page.locator('.el-menu-item').filter({ hasText: 'Work items' }).click()
    await expect(page).toHaveURL(/#\/items/)
    await page.locator('.el-table__body .aim-task-link').filter({ hasText: 'T-0001' }).first().click()
    await expect(page.locator('.el-drawer h3')).toHaveText('Alpha is being worked on')
    await page.goBack()
    await expect(page).toHaveURL(/#\/plan/)
    await expect(page.locator('.el-drawer')).toBeHidden()

    // Escape is how a modal is meant to be dismissed, and it still is. (A move
    // *inside* a list is a query change on the same path, so it is not a
    // departure and the reader keeps what they opened; that is the other half of
    // this rule and lives in the drawer's own test.)
    await page.goto('/#/items')
    await page.locator('.el-table__row').filter({ hasText: 'T-0002' }).click()
    await expect(page.locator('.el-drawer h3')).toHaveText('Beta waits on Alpha')
    await page.keyboard.press('Escape')
    await expect(page.locator('.el-drawer')).toBeHidden()
  })

  test('a blocker the board does not hold still goes somewhere', async ({ page }) => {
    await page.goto('/#/items')
    // T-9000 is not in the payload. It renders as a link that searches for it
    // rather than as a control that opens nothing at all.
    const missing = page.locator('.el-table__body .aim-task-link-missing').first()
    await expect(missing).toHaveText('T-9000')
    await missing.click()
    await expect(page).toHaveURL(/#\/items\?q=T-9000/)
    await expect(page.locator('.el-table__body')).not.toContainText('T-0001')
  })

  test('a milestone opens the work it is made of', async ({ page }) => {
    await page.goto('/#/plan')
    await page.locator('.el-table__body .aim-task-link').filter({ hasText: 'M1' }).first().click()
    await expect(page).toHaveURL(/#\/items\?milestone=M1/)
    await expect(page.locator('.el-table__body')).toContainText('T-0001')
    await expect(page.locator('.el-table__body')).toContainText('T-0002')
  })

  test('the plan disagreement count opens the disagreements', async ({ page }) => {
    await page.goto('/#/plan')
    await page.locator('.el-alert a').filter({ hasText: 'disagreement' }).click()
    await expect(page).toHaveURL(/#\/attention#drift/)
    const drift = page.locator('#drift')
    await expect(drift).toBeVisible()
    await expect(drift).toContainText('T-0001')
    await expect(drift).toContainText('status')
    // And the id in the drift row is a way into the item the plan drifted about.
    await drift.locator('.aim-task-link').first().click()
    await expect(page.locator('.el-drawer')).toBeVisible()
    await expect(page.locator('.el-drawer h3')).toHaveText('Alpha is being worked on')
  })

  test('the drawer is the same drawer from every surface, and walks back', async ({ page }) => {
    await page.goto('/#/kanban')
    await page.locator('.aim-card[data-id="T-0001"]').click()
    await expect(page.locator('.el-drawer h3')).toHaveText('Alpha is being worked on')
    // The drawer offers the action this item actually has. Alpha is a plan seed,
    // so that is "record it", not the review decisions -- offering a decision for
    // work that has never been recorded is the control that lies.
    await expect(page.locator('.aim-action-panel').first()).toBeVisible()
    await expect(page.locator('.aim-action-panel')).toContainText('Record this work item')
    await page.keyboard.press('Escape')
    await expect(page.locator('.el-drawer')).toBeHidden()

    // Open Beta, follow its blocker into Alpha, then walk back. Closing must
    // return the reader to where they were rather than to a bare board.
    await page.locator('.aim-card[data-id="T-0002"]').click()
    await expect(page.locator('.el-drawer h3')).toHaveText('Beta waits on Alpha')
    await page.locator('.el-drawer .aim-blocker-link').filter({ hasText: 'T-0001' }).click()
    await expect(page.locator('.el-drawer h3')).toHaveText('Alpha is being worked on')
    await page.locator('.el-drawer button').filter({ hasText: 'previous task' }).click()
    await expect(page.locator('.el-drawer h3')).toHaveText('Beta waits on Alpha')
  })

  test('every deep link is reachable by keyboard, and back returns to it', async ({ page }) => {
    await page.goto('/#/plan')
    const link = page.locator('.el-table__body .aim-task-link').filter({ hasText: 'M1' }).first()
    await link.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/#\/items\?milestone=M1/)
    await page.goBack()
    await expect(page).toHaveURL(/#\/plan/)
    await expect(page.locator('.aim-page h2')).toHaveText('Plan & risks')
  })
})
