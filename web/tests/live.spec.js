import { expect, test } from '@playwright/test'

/**
 * The record is a live thing. These tests hold the dashboard to that: a change on
 * the server arrives on its own, without a click, and the only time it does not
 * is when arriving now would take something away from the reader.
 *
 * Both cases are driven from a route handler whose digest the test moves, so the
 * "server" changes exactly when the test says it does.
 */

const TASK = (id, title, status = 'backlog') => ({
  id, title, owner: 'codex', status, priority: 'normal', milestone: '',
  tags: [], due: '', blocked_by: [], visibility: 'published',
  provenance: 'seed only (fixture)', events: [], comments: [],
})

const kanban = (digest, tasks) => ({
  digest,
  statuses: ['backlog', 'doing'],
  terminal: ['done'],
  phase: 'RESOLVE',
  milestones: {},
  agents: {},
  register: {},
  tasks,
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
})

const chat = (digest, bodies) => ({
  digest,
  statuses: ['backlog'],
  terminal: ['done'],
  phase: 'RESOLVE',
  milestones: {},
  agents: { human: { kind: 'human', model: '' } },
  register: {},
  tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: {
    channels: [{
      id: 'hello', phase: 'RESOLVE', gated: false, rule: 'fixture',
      messages: bodies.map((body, index) => ({
        from: 'codex', to: 'hello', ts: `2026-09-22T00:0${index}:00.000Z`, kind: 'note', body,
      })),
    }],
    rooms: [],
    mail: [],
  },
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: true, as: 'human' },
})

/** A server whose record changes when the test says so. */
async function serveChangingRecord(page, first, second = first) {
  const box = { doc: first, digest: first.digest }
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(box.doc),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: box.digest }),
  }))
  return {
    /** Move the record on. A third state is a second call, not a second helper. */
    move(next = second) {
      box.doc = next
      box.digest = next.digest
    },
  }
}

test('a changed record arrives on its own, with nothing clicked and nothing focused', async ({ page }) => {
  let navigations = 0
  page.on('framenavigated', (frame) => { if (frame === page.mainFrame()) navigations += 1 })

  const server = await serveChangingRecord(
    page,
    kanban('live-1', { 'T-0001': TASK('T-0001', 'Alpha') }),
    kanban('live-2', { 'T-0001': TASK('T-0001', 'Alpha'), 'T-0002': TASK('T-0002', 'Beta') }),
  )
  await page.goto('/#/kanban')
  await expect(page.locator('.aim-card')).toHaveCount(1)
  const navigationsAfterLoad = navigations
  expect(await page.evaluate(() => document.activeElement?.tagName || '')).not.toBe('TEXTAREA')

  server.move()
  await expect.poll(() => page.locator('.aim-card').count(), { timeout: 15_000 }).toBe(2)
  await expect(page.locator('.aim-card[data-id="T-0002"]')).toBeVisible()

  // Nothing the reader chose was thrown away to get there: same route, same URL,
  // same document, no reload, and no banner announcing that a refresh happened.
  expect(page.url()).toContain('#/kanban')
  expect(navigations).toBe(navigationsAfterLoad)
  await expect(page.getByText('the record has moved')).toHaveCount(0)
  await expect(page.locator('.aim-deferred')).toHaveCount(0)
})

test('a draft in the composer survives, and the update waits instead of interrupting', async ({ page }) => {
  const server = await serveChangingRecord(
    page,
    chat('live-a', ['first message']),
    chat('live-b', ['first message', 'second message']),
  )
  await page.goto('/#/chat')
  await expect(page.locator('.aim-msg')).toHaveCount(1)

  const draft = 'half a sentence I have not sent yet'
  await page.locator('.aim-composer textarea').fill(draft)
  await expect(page.locator('.aim-composer textarea')).toHaveValue(draft)

  server.move()
  // The board notices, and says so quietly instead of reloading under the reader.
  await expect(page.locator('.aim-deferred')).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('.aim-deferred')).toContainText('newer activity on the record')
  await expect(page.locator('.aim-composer textarea')).toHaveValue(draft)
  await expect(page.locator('.aim-msg')).toHaveCount(1)
  await expect(page.getByText('the record has moved')).toHaveCount(0)
  await expect(page.locator('.el-alert--warning')).toHaveCount(0)

  // Taking the update is one quiet click, and it still does not cost the draft.
  await page.locator('.aim-deferred button').click()
  await expect(page.locator('.aim-msg')).toHaveCount(2)
  await expect(page.locator('.aim-composer textarea')).toHaveValue(draft)
  await expect(page.locator('.aim-deferred')).toHaveCount(0)
})

test('a reading position the reader chose is not thrown away by an update', async ({ page }) => {
  const thread = (bodies) => ({
    ...chat(`scroll-${bodies.length}`, []),
    conversation: {
      channels: [{
        id: 'hello', phase: 'RESOLVE', gated: false, rule: 'fixture',
        messages: bodies.map((body, index) => ({
          from: 'codex', to: 'hello',
          ts: `2026-09-22T01:${String(index).padStart(2, '0')}:00.000Z`,
          kind: 'note', body,
        })),
      }],
      rooms: [], mail: [],
    },
  })
  const sixty = Array.from({ length: 60 }, (_, index) => `fixture message ${index}`)
  const server = await serveChangingRecord(page, thread(sixty), thread([...sixty, 'a newer message']))

  await page.goto('/#/chat')
  await expect(page.locator('.aim-msg').first()).toBeVisible()
  const parked = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    history.scrollTop = 200
    return history.scrollTop
  })
  expect(parked).toBeGreaterThan(0)

  server.move()
  await expect(page.locator('.aim-deferred')).toBeVisible({ timeout: 15_000 })
  // A reader who scrolled away from the top is mid-sentence too: the new message
  // waits instead of pushing the page around under them.
  await expect(page.locator('.aim-deferred')).toContainText('is scrolled')
  expect(await page.evaluate(() => document.querySelector('.aim-history').scrollTop)).toBe(parked)

  // And taking the update does not move them either. The earlier version of this
  // test stopped at the deferral, which is the half that was already true: the
  // scroller a reader moved is not on the focus path, so a forced update restored
  // everything *except* the one pane they were reading. Measured then: 200 -> 5948.
  await page.locator('.aim-deferred button').click()
  await expect(page.locator('.aim-msg')).toHaveCount(61)
  expect(await page.evaluate(() => document.querySelector('.aim-history').scrollTop)).toBe(parked)
})

test('a forced update keeps the composer, and the reader stays where they were', async ({ page }) => {
  // The other half of the acceptance: a forced update is still not allowed to
  // cost the reader anything. Two positions are checked at once here -- the
  // parked history and the half-typed sentence -- because they are protected by
  // the same pass and a fix that buys one with the other is not a fix.
  const third = [...Array.from({ length: 60 }, (_, index) => `fixture message ${index}`),
                 'a newer message', 'newer still']
  const thread = (bodies) => ({
    ...chat(`multi-${bodies.length}`, []),
    conversation: {
      channels: [{
        id: 'hello', phase: 'RESOLVE', gated: false, rule: 'fixture',
        messages: bodies.map((body, index) => ({
          from: 'codex', to: 'hello',
          ts: `2026-09-22T02:${String(index).padStart(2, '0')}:00.000Z`,
          kind: 'note', body,
        })),
      }],
      rooms: [], mail: [],
    },
  })
  const sixty = thread(third.slice(0, 60))
  const server = await serveChangingRecord(page, sixty, thread(third.slice(0, 61)))

  await page.goto('/#/chat')
  await expect(page.locator('.aim-msg')).toHaveCount(60)
  const draft = 'half a sentence I have not sent yet'
  await page.locator('.aim-composer textarea').fill(draft)

  server.move()
  await expect(page.locator('.aim-deferred')).toBeVisible({ timeout: 15_000 })
  await page.locator('.aim-deferred button').click()
  await expect(page.locator('.aim-msg')).toHaveCount(61)
  await expect(page.locator('.aim-composer textarea')).toHaveValue(draft)
  await expect(page.locator('.aim-deferred')).toHaveCount(0)

  // And a position a *reading* visitor chose survives the same pass, including
  // when both protections are wanted at once: the parked position is set while
  // the draft is still in the composer, so neither may be bought with the other.
  // Taking the update must not move the history a pixel.
  await page.locator('.aim-history').evaluate((history) => { history.scrollTop = 200 })
  const parked = await page.locator('.aim-history').evaluate((history) => history.scrollTop)
  expect(parked).toBeGreaterThan(0)

  server.move(thread(third.slice(0, 62)))
  await expect(page.locator('.aim-deferred')).toBeVisible({ timeout: 15_000 })
  await page.locator('.aim-deferred button').click()
  await expect(page.locator('.aim-msg')).toHaveCount(62)
  expect(await page.locator('.aim-history').evaluate((history) => history.scrollTop)).toBe(parked)
  await expect(page.locator('.aim-composer textarea')).toHaveValue(draft)
})
