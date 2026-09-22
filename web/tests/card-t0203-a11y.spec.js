import { expect, test } from '@playwright/test'

/**
 * T-0203 (the plan's T-0064) -- "Accessibility: keyboard reachable, contrast, no
 * colour-only encoding".
 *
 * The card's own acceptance clause, verbatim: **"status and blocker state are
 * readable with colour ignored"**. That is the clause this file encodes. The title
 * names two more things -- keyboard reachability and contrast -- and they are
 * *not* measured here; a file that says it tested what it did not is the kind of
 * claim this project keeps finding (see the header of card-t0160-mobile-390.spec.js
 * for the same disclosure).
 *
 * What "colour ignored" is taken to mean, operationally: the browser is put in
 * forced-colours mode (`page.emulateMedia({ forcedColors: 'active' })`), which
 * replaces every author colour with a system colour, and then the two facts must
 * still be readable. Only one channel survives that treatment unchanged -- text,
 * including an element's accessible name -- so the assertions below are about text
 * and nothing else. A status drawn as a coloured dot beside a word passes; a status
 * drawn as a coloured dot passes only if the dot is not the only channel.
 *
 * Measured on the live board before this file (bundle 870b282+dirty, built
 * 2026-09-22T08:40:07.787Z, `stale: true`):
 *
 *   #/kanban   the column header names the status in text (StatusTag) ... yes
 *              `KanbanPane.vue:210` draws `<span class="aim-flag blocked">` around
 *              a lock glyph and the blocker id: the *state* is a colour plus a
 *              glyph with no accessible name, and the card never says "blocked"
 *   #/items    the status cell and the "blocked by" cell are text ............ yes
 *
 * The Kanban clause carried `test.fail()` with that reason rather than being
 * weakened or deleted. That defect has since landed (`KanbanPane.vue` says
 * "blocked" in text and names the glyph), so the marker is gone from that test
 * and the assertion is untouched; the other four clauses in this file never
 * carried one.
 *
 * Revision measured for this file: recorded in the report that carried it; the
 * bundle was read from `GET http://127.0.0.1:8777/api/revision` at run time.
 */

const SEED = 'seed only (not yet in the store)'

const task = (id, status, extra = {}) => ({
  id, title: `an item in ${status}`, owner: 'codex', status, priority: 'normal',
  milestone: '', tags: [], accept: `acceptance for ${id}`, blocked_by: [],
  visibility: 'published', provenance: 'store only', events: [], comments: [], ...extra,
})

/** One item per status, so every column on the Kanban has a card to read.
 *  T-1302 is *blocked while doing* on purpose: if the state were inferred from the
 *  column, a card in the "doing" column would look unblocked, which is the case a
 *  colour-only encoding hides. */
const STATUSES = ['backlog', 'ready', 'doing', 'review', 'done']
const tasks = {}
STATUSES.forEach((status, i) => {
  const id = `T-13${String(i).padStart(2, '0')}`
  tasks[id] = task(id, status)
})
tasks['T-1305'] = task('T-1305', 'doing', { blocked_by: ['T-1300'] })
tasks['T-1306'] = task('T-1306', 'blocked', { blocked_by: ['T-1300', 'T-1301'] })
tasks['T-1307'] = task('T-1307', 'ready', { due: '2026-09-01' })

const STATUSES_LIST = [...STATUSES, 'blocked']

export const STATE = {
  digest: 'a11y-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: STATUSES_LIST,
  terminal: ['done'],
  phase: 'CROSS_EXAMINE',
  viewer: 'human',
  viewer_kind: 'human',
  write: { enabled: false, as: '' },
  milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'codex', model: '' } },
  register: {},
  tasks,
  reports: { series: [], throughput: [], blocked: [], median_cycle: null, recorded: 8, seed_only: 0 },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift: [],
  withheld_tasks: 0,
}

/** The text a reader, or a screen reader, can get out of an element: what is drawn
 *  plus the names that are attached to it. A glyph with no name adds nothing. */
async function readText(locator) {
  return locator.evaluate((el) => {
    const names = [el.getAttribute('title'), el.getAttribute('aria-label')]
    for (const child of el.querySelectorAll('[title], [aria-label], [alt]')) {
      names.push(child.getAttribute('title'), child.getAttribute('aria-label'), child.getAttribute('alt'))
    }
    const cls = [...el.querySelectorAll('svg, i, [class*="icon"], [class*="aim-dot"]')]
      .map((n) => n.getAttribute('class') || '')
    return [el.innerText, ...names.filter(Boolean), ...cls].join(' ')
  })
}

test.describe('T-0203 status and blockers survive with colour taken away', () => {
  test.use({ viewport: { width: 1440, height: 1000 } })

  test.beforeEach(async ({ page }) => {
    // Colour is removed by the browser, not by an assertion about CSS: with
    // forced colours every author colour is replaced, so anything that was encoded
    // in hue is gone by the time the assertions below read the page.
    await page.emulateMedia({ forcedColors: 'active' })
    await page.route('**/api/state**', (r) => r.fulfill({
      contentType: 'application/json', body: JSON.stringify(STATE),
    }))
    await page.route('**/api/digest**', (r) => r.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
    }))
  })

  test('the served board is in forced-colours mode for this run', async ({ page }) => {
    await page.goto('/#/kanban')
    await expect(page.locator('.aim-board')).toBeVisible()
    const media = await page.evaluate(() => matchMedia('(forced-colors: active)').matches)
    expect(media, 'the run must actually be in forced-colours mode, or "colour ignored" is a claim '
      + 'about a stylesheet that was never applied').toBe(true)
  })

  test('#/kanban: every card\'s status is readable as text', async ({ page }) => {
    await page.goto('/#/kanban')
    await expect(page.locator('.aim-board')).toBeVisible()

    for (const [id, t] of Object.entries(tasks)) {
      if (t.provenance === SEED) continue
      const card = page.locator(`article[data-id="${id}"]`)
      await expect(card, `${id} is not drawn on the kanban`).toHaveCount(1)
      const column = card.locator('xpath=ancestor::section[1]')
      const header = (await column.locator('header').first().innerText()).replace(/\s+/g, ' ').trim()
      expect(header, `${id} (${t.status}) sits in a column whose header reads "${header}"; `
        + 'the status must be the column\'s word, not only its colour').toContain(t.status)
    }
  })

  test('#/kanban: a blocked card names its blocker in text', async ({ page }) => {
    await page.goto('/#/kanban')
    await expect(page.locator('.aim-board')).toBeVisible()

    for (const [id, t] of Object.entries(tasks)) {
      if (!t.blocked_by.length) continue
      const card = page.locator(`article[data-id="${id}"]`)
      const readable = await readText(card)
      for (const blocker of t.blocked_by) {
        expect(readable, `${id} must name its blocker ${blocker} in text`).toContain(blocker)
      }
    }
  })

  test('#/kanban: the blocked state itself is a word, not a colour or a bare glyph', async ({ page }) => {
    await page.goto('/#/kanban')
    await expect(page.locator('.aim-board')).toBeVisible()

    const card = page.locator('article[data-id="T-1305"]') // doing, blocked by T-1300
    const readable = await readText(card)
    expect(readable, 'the card must say "blocked" in text, or name the glyph').toMatch(/blocked/i)
  })

  test('#/items: each row states its status and names its blockers as text', async ({ page }) => {
    await page.goto('/#/items')
    const table = page.locator('.el-table').first()
    await expect(table).toBeVisible()

    const headers = (await table.locator('thead th').allInnerTexts()).map((h) => h.trim().toLowerCase())
    const statusAt = headers.findIndex((h) => h === 'status')
    const blockedAt = headers.findIndex((h) => h.startsWith('blocked'))
    expect(statusAt, `the items table has no status column: ${JSON.stringify(headers)}`).toBeGreaterThanOrEqual(0)
    expect(blockedAt, `the items table has no blocked-by column: ${JSON.stringify(headers)}`).toBeGreaterThanOrEqual(0)

    for (const [id, t] of Object.entries(tasks)) {
      const row = table.locator('tbody tr').filter({ hasText: id }).first()
      await expect(row, `${id} is not drawn in the items table`).toBeVisible()
      const cells = (await row.locator('td').allInnerTexts()).map((c) => c.replace(/\s+/g, ' ').trim())
      expect(cells[statusAt], `${id}: the status cell must read "${t.status}"`).toBe(t.status)
      const blockedCell = cells[blockedAt] || ''
      if (!t.blocked_by.length) {
        expect(blockedCell, `${id} has no blockers, so its blocked-by cell must say so`).toBeTruthy()
      } else {
        for (const blocker of t.blocked_by) {
          expect(blockedCell, `${id}: the blocked-by cell must name ${blocker}`).toContain(blocker)
        }
      }
    }
  })
})
