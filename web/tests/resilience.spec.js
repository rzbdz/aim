import { expect, test } from '@playwright/test'

/**
 * T-0184: a render error inside the drawer must not be able to brick the board.
 *
 * The drawer is mounted by the shell and `el-drawer` mounts its overlay before
 * its panel renders. So when anything in the panel throws while rendering, the
 * panel never appears and the overlay stays: a full-screen invisible modal that
 * swallows every click, including the nav, and survives a route change. Measured
 * on the served board before the fix: `drawer 0, overlay 1` for *every* click on
 * *every* work item, `navReachable: false`, and a URL that did not move when the
 * nav was clicked through it. The reader's only way out was a reload, with
 * nothing on screen to tell them so.
 *
 * The test makes the panel throw on purpose. The measured cause was a template
 * reading a name the component never bound (`action.decision` after a rename),
 * which cannot be injected from outside the bundle -- so this injects the same
 * class of defect one layer down, through the API: a record whose `blocked_by` is
 * a string instead of a list. That is not a synthetic shape either; it is the
 * schema drift T-0204 is about. What is being proved is the failure *mode*, and
 * the acceptance codex wrote for it: after a render error,
 * `document.querySelectorAll('.el-overlay').length === 0`, and the nav responds.
 */

const TASK = (id, title, extra = {}) => ({
  id, title, owner: 'codex', status: 'doing', priority: 'normal', milestone: '',
  tags: [], due: '', accept: `acceptance for ${id}`, blocked_by: [],
  visibility: 'published', provenance: 'store only', events: [], comments: [], ...extra,
})

const STATE = {
  digest: 'resilience-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'doing', 'review', 'done'],
  terminal: ['done'],
  phase: 'RESOLVE',
  milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' } },
  register: {},
  tasks: {
    // The panel reads `(task.blocked_by || []).filter(...)`. A string has no
    // `.filter`, so this task throws while the drawer renders it -- after the
    // overlay is already in the DOM.
    'T-0001': TASK('T-0001', 'A record the drawer cannot draw', { blocked_by: 'T-0002' }),
    'T-0002': TASK('T-0002', 'A record it can'),
  },
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
  }))
})

test('a drawer that throws while rendering does not leave a blocking overlay', async ({ page }) => {
  await page.goto('/#/kanban')
  await page.locator('.aim-card[data-id="T-0001"]').click()

  /**
   * The overlay node stays in the DOM, and that is not the defect.
   *
   * `el-drawer` mounts the overlay before the panel, and the panel threw -- so
   * the overlay is still there with `modelValue` false, which is how Element Plus
   * draws a closed drawer: `display: none`, 0x0, `pointer-events` off. Measured
   * on the served build, with the guard: `overlays: 1, display: none, drawers: 0`,
   * and `elementFromPoint(120, 300)` returns the article underneath it.
   *
   * An earlier version of this test asserted `overlays === 0` and failed on a
   * correct board, because it asserted the mechanism instead of the consequence.
   * The consequence is what the reader experiences, and it is two things: nothing
   * is covering the page, and the page underneath still works.
   */
  await expect.poll(() => page.evaluate(() => {
    const overlays = [...document.querySelectorAll('.el-overlay')]
    return overlays.every((el) => getComputedStyle(el).display === 'none')
  })).toBe(true)

  // Nothing is left covering the page: what is at the centre of the viewport is
  // part of the board, not a modal. Without the guard the same measure returns
  // `DIV.el-overlay is-drawer el-modal-drawer`, and the nav cannot be reached.
  const atCentre = await page.evaluate(() => {
    const el = document.elementFromPoint(120, 300)
    return el ? `${el.tagName} ${el.className}` : ''
  })
  expect(atCentre).not.toContain('el-overlay')

  // And the shell is usable: the nav responds, and the route actually changes.
  const nav = page.locator('.el-menu-item').filter({ hasText: 'Gantt' })
  await expect(nav).toBeVisible()
  await nav.click()
  await expect(page).toHaveURL(/#\/gantt/)
  await expect(page.locator('.aim-page h2')).toHaveText('Gantt')
})

test('a record the drawer cannot draw is still reachable, and the next one works', async ({ page }) => {
  // The other half of the rule: closing the drawer keeps the page usable, but the
  // reader also has to be able to open the *next* item. A guard that closed the
  // drawer by wedging the store would pass the test above and be useless.
  await page.goto('/#/kanban')
  await page.locator('.aim-card[data-id="T-0001"]').click()
  await expect.poll(() => page.evaluate(() => {
    const overlays = [...document.querySelectorAll('.el-overlay')]
    return overlays.every((el) => getComputedStyle(el).display === 'none')
  })).toBe(true)

  await page.locator('.aim-card[data-id="T-0002"]').click()
  await expect(page.locator('.el-drawer h3')).toHaveText('A record it can')
})
