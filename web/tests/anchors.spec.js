import { expect, test } from '@playwright/test'

/**
 * T-0171: a link that names a row has to land on that row.
 *
 * The phase chips are links into Help & concepts -- hover the phase in the
 * header, click it, and you should be reading the section about *that* phase.
 * The measurement that filed this task was that clicking the chip and typing
 * `/#/help` were indistinguishable: the app scroller (`.el-main.aim-main`, not
 * the window) stayed at `scrollTop` 0 and the row sat 1244px below the fold of a
 * 2689px page. A link that navigates to a page and then leaves the reader to
 * find the paragraph is a link that half works, and half-working is what this
 * board keeps being wrong about.
 *
 * Every assertion below is made against `.aim-main` on purpose. Asserting
 * `window.scrollY` would pass on an empty page and prove nothing, which is how
 * the original defect survived a suite that already had a Help test in it.
 */

const STATE = {
  digest: 'anchors-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'done'],
  terminal: ['done'],
  phase: 'CROSS_EXAMINE',
  milestones: {},
  agents: { human: { kind: 'human', model: '' } },
  register: {},
  tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  // The attention page's "Plan disagreements" tile is a link only when there is a
  // disagreement to land on -- a zero signal is deliberately a plain tile (T-0180),
  // so the self-link this file is about cannot be tested against an empty drift.
  drift: [{ id: 'T-0001', field: 'status', plan: 'doing', store: 'review' }],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
}

/** How far the named row is from the top of the pane the reader scrolls. */
const rowOffset = (page, id) => page.evaluate((target) => {
  const scroller = document.querySelector('.aim-main')
  const row = document.getElementById(target)
  if (!scroller || !row) return null
  return Math.round(row.getBoundingClientRect().top - scroller.getBoundingClientRect().top)
}, id)

test.describe('a link that names a row lands on that row', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(STATE),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
    }))
  })

  test('clicking the phase chip puts that phase row in the pane', async ({ page }) => {
    await page.goto('/#/kanban')
    const chip = page.locator('.aim-header .aim-phase-chip-link')
    await expect(chip).toBeVisible()
    await chip.click()

    await expect(page).toHaveURL(/#\/help#phase-cross_examine/)
    const row = page.locator('#phase-cross_examine')
    await expect(row).toBeVisible()
    // In view, not merely present: the old behaviour had it rendered and 1244px
    // below the fold, which is indistinguishable from absent to the reader.
    const offset = await rowOffset(page, 'phase-cross_examine')
    expect(offset).not.toBeNull()
    expect(offset).toBeGreaterThanOrEqual(0)
    expect(offset).toBeLessThan(
      await page.evaluate(() => document.querySelector('.aim-main').clientHeight))
  })

  test('a deep link typed or shared behaves the same as a click', async ({ page }) => {
    // The shared URL is the other half of "a link is a way in": if the anchor
    // only works when a chip was clicked, the link a reader pastes into a
    // message is broken for everyone but the person who generated it.
    await page.goto('/#/help#phase-resolve')
    await expect(page.locator('#phase-resolve')).toBeVisible()
    const offset = await rowOffset(page, 'phase-resolve')
    expect(offset).toBeGreaterThanOrEqual(0)
    expect(offset).toBeLessThan(
      await page.evaluate(() => document.querySelector('.aim-main').clientHeight))
  })

  test('the anchor lands after a lazy route load, not only on a second click', async ({ page }) => {
    // The Help pane is a lazy chunk. On the first frame after navigation the row
    // does not exist yet, so an anchor resolved once and given up on works only
    // when the chunk happens to be cached -- i.e. on the second click, which is
    // the click the person demonstrating it makes.
    await page.goto('/#/kanban')
    await page.locator('.aim-header .aim-phase-chip-link').click()
    await expect(page).toHaveURL(/#\/help#phase-cross_examine/)

    // Now walk away and click again, with the chunk cached, and assert the same
    // thing: the position must not depend on which click it was.
    await page.goto('/#/items')
    await page.locator('.aim-header .aim-phase-chip-link').click()
    const offset = await rowOffset(page, 'phase-cross_examine')
    expect(offset).toBeGreaterThanOrEqual(0)
    expect(offset).toBeLessThan(
      await page.evaluate(() => document.querySelector('.aim-main').clientHeight))
  })

  test('an ordinary route change does not carry a position across panes', async ({ page }) => {
    // The other half of the rule, and the reason the fix is in the router rather
    // than in a click handler: fixing the anchor must not turn every navigation
    // into a jump, and must not smear one pane's reading position onto the next.
    //
    // Note what is *not* asserted here: that the scroller keeps its old value.
    // It does not, and it should not -- pane B has a different height and the
    // browser clamps the old number to it, so "keep the number" is not a
    // behaviour anyone can promise. What is promised is the observable fact: the
    // pane the reader asked for is rendered at its top, not scrolled to a
    // position that belonged to a different page.
    await page.goto('/#/help')
    await expect(page.locator('#phase-cross_examine')).toBeVisible()
    // Parked the way a reader parks: the wheel, not a write to `scrollTop`. A
    // scripted write and a real scroll are clamped by the browser differently,
    // and only one of them is the thing being protected.
    await page.locator('.aim-help-table').first().hover()
    await page.mouse.wheel(0, 1200)
    await expect.poll(() => page.evaluate(() => document.querySelector('.aim-main').scrollTop))
      .toBeGreaterThan(0)

    await page.locator('.el-menu-item').filter({ hasText: 'Work items' }).click()
    await expect(page).toHaveURL(/#\/items/)
    await expect(page.locator('.aim-page h2')).toHaveText('Work items')
    expect(await page.evaluate(() => document.querySelector('.aim-main').scrollTop)).toBe(0)

    await page.locator('.el-menu-item').filter({ hasText: 'Help & concepts' }).click()
    await expect(page).toHaveURL(/#\/help/)
    await expect(page.locator('#phase-cross_examine')).toBeVisible()
    expect(await page.evaluate(() => document.querySelector('.aim-main').scrollTop)).toBe(0)
  })
})

/**
 * T-0183: a tile that says needs-action has to move the reader, and a nav click
 * has to put the reader at the top of the page they asked for.
 *
 * Two measured symptoms, one mechanism. The app's scroller is `.aim-main`, and
 * nothing reset it: at 1280x800, `#/items` at 4787/4787 -> nav "Help & concepts"
 * -> `#/help` at 3937/3937, the bottom of a 4688px glossary. And the attention
 * page's own tiles link to fragments *of the page the reader is already on*, so
 * `#/attention#drift` put the fragment in the address bar and moved nothing.
 *
 * Every assertion is against the app's scroller, never `window.scrollY`: the
 * document is 0px tall here, so a window assertion passes on a page that did not
 * move at all.
 */
test.describe('a link that is a way somewhere, on this page or another', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(STATE),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
    }))
  })

  test('a nav click opens the page it names at its top', async ({ page }) => {
    // Parked deep, the way a reader parks: a real wheel over real content. The
    // fixture's Help page is a 4688px wall, which is the page the defect was
    // measured on -- `#/items` at 4787/4787 -> "Help & concepts" -> `#/help` at
    // 3937/3937, the end of the glossary.
    await page.goto('/#/help')
    await expect(page.locator('#phase-cross_examine')).toBeVisible()
    await page.mouse.move(600, 400)
    await page.mouse.wheel(0, 1400)
    await expect.poll(() => page.evaluate(() => document.querySelector('.aim-main').scrollTop))
      .toBeGreaterThan(0)

    await page.locator('.el-menu-item').filter({ hasText: 'Work items' }).click()
    await expect(page.locator('.aim-page h2')).toHaveText('Work items')
    // Not just "a number changed": the new page is at its top.
    await expect.poll(() => page.evaluate(() => document.querySelector('.aim-main').scrollTop)).toBe(0)
  })

  test('a reader who is deep in a page and asks for that page still arrives at its top', async ({ page }) => {
    // The direction that made this a defect rather than a rough edge: the reader
    // clicks Help to *escape* a wall of numbers and lands at the end of the wall.
    // Arriving here by fragment is how they get deep in the first place.
    await page.goto('/#/help#phase-resolve')
    await expect(page.locator('#phase-resolve')).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.querySelector('.aim-main').scrollTop))
      .toBeGreaterThan(0)

    await page.locator('.el-menu-item').filter({ hasText: 'Attention' }).click()
    await expect(page.locator('.aim-page h2')).toHaveText('Attention')
    await expect.poll(() => page.evaluate(() => document.querySelector('.aim-main').scrollTop)).toBe(0)

    await page.locator('.el-menu-item').filter({ hasText: 'Help & concepts' }).click()
    await expect(page.locator('#phase-cross_examine')).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.querySelector('.aim-main').scrollTop)).toBe(0)
  })

  test('a tile whose destination is on this page still moves the reader', async ({ page }) => {
    // `#/attention#drift` is the strongest form of the defect: a *self*-link, on
    // the pane that is already open, from the row of tiles that exists to tell
    // the reader what to do. "Nothing happened" is the only reading available.
    await page.goto('/#/attention')
    await expect(page.locator('#drift')).toBeAttached()
    const before = await page.evaluate(() => document.querySelector('.aim-main').scrollTop)

    await page.locator('.aim-signal').filter({ hasText: 'Plan disagreements' }).click()
    await expect(page).toHaveURL(/#\/attention#drift/)
    const after = await page.evaluate(() => document.querySelector('.aim-main').scrollTop)
    expect(after).toBeGreaterThan(before)

    // In view, not merely scrolled: the target is within a viewport of the top.
    const offset = await rowOffset(page, 'drift')
    expect(offset).toBeGreaterThanOrEqual(0)
    expect(offset).toBeLessThan(
      await page.evaluate(() => document.querySelector('.aim-main').clientHeight))
  })

  test('a fragment link still lands when the reader is already below the target', async ({ page }) => {
    // The measured trap: the same code path gave two results depending on whether
    // the target was above or below the current position. `#/help#concept-drift`
    // -> scrollTop 3289 with the target mid-viewport, `#/help#phase-commit` ->
    // scrollTop 980 with the target at the top. So the direction is asserted, not
    // just the movement.
    await page.goto('/#/help#concept-drift')
    await expect(page.locator('#concept-drift')).toBeVisible()
    const low = await page.evaluate(() => document.querySelector('.aim-main').scrollTop)
    expect(low).toBeGreaterThan(0)

    // A phase row that sits above it: the reader must come back up to it.
    await page.goto('/#/help#phase-commit')
    await expect(page.locator('#phase-commit')).toBeVisible()
    const high = await page.evaluate(() => document.querySelector('.aim-main').scrollTop)
    expect(high).toBeLessThan(low)
    const offset = await rowOffset(page, 'phase-commit')
    expect(offset).toBeGreaterThanOrEqual(0)
    expect(offset).toBeLessThan(
      await page.evaluate(() => document.querySelector('.aim-main').clientHeight))
  })
})
