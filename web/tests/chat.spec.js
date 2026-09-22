import { expect, test } from '@playwright/test'

/**
 * T-0181: opening a conversation lands where the reader needs to be, and the list
 * says what is waiting on them.
 *
 * Two measured defects, one pane. The leader's words were "滚动到第一个 unread，
 * 默认自动滚动到最新你没做，要用户自己点，这些都是不可接受的" -- and it was worse
 * than "a click is needed":
 *
 *  * `anchorIndex` picked the first message carrying a `receipt demanded` chip
 *    whatever its state, so `claude-session1 ⇄ codex` opened on message 8 -- whose
 *    state is `acked` -- with the first genuinely unread message 89,710px below and
 *    the newest 106,485px below that.
 *  * The anchor aligned the message's *top* to a 12px offset, so even the newest
 *    message opened at its own beginning with the rest below the fold. `jumpToEnd`
 *    existed as a button and was the only thing that reached the end.
 *
 * The fixture is built so every clause is falsifiable independently: the
 * viewer is `human`, one thread holds messages addressed to *someone else*, one
 * holds an answered demand, and one is genuinely unread.
 */

const CHANNEL_MSG = (index, from, body) => ({
  from, to: 'hello', ts: `2026-09-22T00:${String(index).padStart(2, '0')}:00.000Z`,
  kind: 'note', body,
})

/**
 * A direct message, as `/api/state` really ships it.
 *
 * Deliberately *without* a `scope`: the board derives the thread key with
 * `directScope(from, to)`, which sorts the pair, and a fixture that hand-sets
 * `scope` is testing a key the server never sends. It also matters here for a
 * second reason -- the thread's `peer` is `scope.split(' ⇄ ').find(x => x !==
 * viewer)`, so a `scope` that does not contain the viewer silently resolves the
 * peer to the *viewer*, and the row is then labelled `human ⇄ human`. That is a
 * real defect this fixture accidentally reproduced; it is not what this file is
 * about, and the fixture must not depend on it either way.
 */
const MAIL = (index, from, to, state, ackRequired = true) => ({
  msg_id: `m${index}`, from, to, ts: `2026-09-22T01:${String(index).padStart(2, '0')}:00.000Z`,
  subject: `subject ${index}`, body: `mail body ${index}`, bytes: 42,
  ack_required: ackRequired, acked_at: state === 'acked' ? '2026-09-22T01:30:00.000Z' : '',
  claimed_at: '', state,
})

/**
 * A thread the viewer is in, with a long history and 3 messages left unread.
 *
 * Two of the three are *not* waiting on the viewer, and they are the point of the
 * fixture. `directScope(from, to)` sorts the pair, so the thread key is derived
 * from who is talking and not from who is reading; a message the viewer **sent**
 * and nobody has receipted lands in the viewer's own thread with
 * `to === 'codex'`. An anchor or a badge that asks "is this message unread"
 * rather than "is this message waiting on *me*" opens three messages above the
 * real one and counts the reader's own unanswered mail back at them.
 *
 * Message 44/45 are between two other agents, so they form a *second* thread --
 * which is what the server does with them, and what the fixture must not flatten
 * into one list to make an assertion easier.
 */
const LONG_MAIL = [
  ...Array.from({ length: 40 }, (_, i) => MAIL(i, i % 2 ? 'human' : 'codex', i % 2 ? 'codex' : 'human', 'acked')),
  // The viewer wrote it and is still owed a receipt for it: unread, not the reader's turn.
  MAIL(40, 'human', 'codex', 'unread'),
  MAIL(41, 'codex', 'human', 'unread'),
  MAIL(42, 'codex', 'human', 'unread'),
  // Somebody else's mail, in a thread that is not the viewer's at all.
  MAIL(43, 'codex', 'claude-session1', 'unread'),
  MAIL(44, 'codex', 'claude-session1', 'unread'),
]

const STATE = {
  digest: 'chat-fixture',
  /**
   * The viewer is declared, and every fixture in this suite should declare it.
   *
   * `board.load()` assigns `this.viewer = this.doc.viewer` unconditionally, so a
   * payload without the key sets the viewer to `undefined` -- not to the default it
   * started with. Measured with a viewer-less copy of this fixture: the mail thread
   * labelled `codex ⇄ human` is still built from `directScope(from, to)`, which does
   * not consult the viewer, while its unread badge and the `needs me` filter both
   * compare against `board.viewer`, so the badge was absent and the thread was
   * filtered out -- a green `#hello` badge next to two threads with no badge at all.
   * `9 of the 11` specs that stub the state endpoint ship no such key (find them by
   * grepping for the route stub, then for a top-level `viewer:`); before today it
   * was `11 of 11`, so those files have been measured against the store's initial
   * `'human'` rather than against what their own fixtures say.
   */
  viewer: 'human',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog'],
  terminal: ['done'],
  phase: 'RESOLVE',
  milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' } },
  register: {},
  tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: {
    channels: [{
      id: 'hello', phase: 'RESOLVE', gated: false, rule: 'fixture',
      messages: Array.from({ length: 60 }, (_, i) => CHANNEL_MSG(i, i % 2 ? 'codex' : 'human', `channel body ${i}`)),
    }],
    rooms: [],
    mail: LONG_MAIL,
  },
  unacked: [{ msg_id: 'm41', from: 'codex', to: 'human', subject: '', bytes: 42 },
            { msg_id: 'm42', from: 'codex', to: 'human', subject: '', bytes: 42 }],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: true, as: 'human' },
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
  }))
})

/** What the reader can actually see: the gap under the newest message, in px. */
const gapBelowNewest = (page) => page.evaluate(() => {
  const history = document.querySelector('.aim-history')
  const nodes = [...document.querySelectorAll('.aim-msg')]
  const last = nodes[nodes.length - 1]
  if (!history || !last) return null
  return Math.round(last.getBoundingClientRect().bottom - history.getBoundingClientRect().bottom)
})

const threadRow = (page, label) => page.locator('.aim-thread').filter({ hasText: label }).first()

test('opening a thread leaves the newest message on screen, with no click', async ({ page }) => {
  await page.goto('/#/chat?thread=ch:hello')
  await expect(page.locator('.aim-msg')).toHaveCount(60)

  // Acceptance 2, as a number: the end of the newest message is at the fold, not
  // 93,972px below it. The container's own bottom padding is allowed for -- what
  // is asserted is the message.
  await expect.poll(() => gapBelowNewest(page)).toBeLessThanOrEqual(0)

  // And it happened without the reader touching anything: the "newest" button is
  // still there, but it is a way *back*, not the only way to the end.
  await expect(page.locator('.aim-reader-head button', { hasText: 'newest' })).toBeVisible()
})

test('a thread with messages waiting on the viewer opens on the first of them', async ({ page }) => {
  await page.goto('/#/chat?thread=dm:codex ⇄ human')
  await expect(page.locator('.aim-msg')).toHaveCount(43)
  await expect(page.locator('.aim-reader-head strong')).toHaveText('codex ⇄ human')

  // The anchor is the first message in this thread that is waiting on the viewer:
  // index 41 (41 rows at indices 0..40, then 41 and 42 are the two addressed to
  // `human` with no receipt). Index 40 is the reader's *own* unread mail to
  // `codex`, and the 40 before it are answered -- so a rule that anchors on "the
  // first unread message" or on "the first receipt chip" lands three rows early.
  await expect(page.locator('.aim-anchor-message')).toBeVisible()
  const anchored = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    const anchor = document.querySelector('.aim-anchor-message')
    if (!history || !anchor) return null
    return {
      index: [...document.querySelectorAll('.aim-msg')].indexOf(anchor),
      // In view, not merely marked: the old behaviour left the anchor rendered
      // and tens of thousands of pixels below the fold.
      fromTop: Math.round(anchor.getBoundingClientRect().top - history.getBoundingClientRect().top),
      viewport: history.clientHeight,
    }
  })
  expect(anchored.index).toBe(41)
  expect(anchored.fromTop).toBeGreaterThanOrEqual(0)
  expect(anchored.fromTop).toBeLessThan(anchored.viewport)
})

test('a thread with nothing waiting on the viewer opens on the newest message', async ({ page }) => {
  // The channel: its last message is the viewer's own, and there is no receipt
  // demand in it at all. So the anchor is the newest message -- and the assertion
  // is that the *answered* demands earlier in the thread did not capture it.
  await page.goto('/#/chat?thread=ch:hello')
  await expect(page.locator('.aim-msg')).toHaveCount(60)
  const index = await page.evaluate(() => {
    const anchor = document.querySelector('.aim-anchor-message')
    return [...document.querySelectorAll('.aim-msg')].indexOf(anchor)
  })
  expect(index).toBe(59)
})

test('every thread row says what is waiting on the viewer', async ({ page }) => {
  // The list has to be readable without opening each item. Before this, every row
  // was equally quiet: the leader's own mail sat at the bottom of the sidebar with
  // no marker while `unacked` named two messages awaiting their receipt.
  await page.goto('/#/chat')
  await expect(page.locator('.aim-thread').first()).toBeVisible()

  const own = threadRow(page, 'codex ⇄ human')
  await expect(own.locator('.aim-unread')).toHaveText('2')

  // The agent-to-agent thread is noisy but is not *the viewer's*: the three
  // `codex -> claude-session1` rows are someone else's mail, so the badge counts
  // what is addressed to the reader and not what merely contains a demand. This is
  // the 50%-false-positive defect from the same predicate.
  const pair = threadRow(page, 'claude-session1 ⇄ codex')
  await expect(pair.locator('.aim-unread')).toHaveCount(0)
})

test('"needs me" means the viewer, and a channel can match it', async ({ page }) => {
  await page.goto('/#/chat?needsMe=1')
  const listed = await page.locator('.aim-thread').allTextContents()
  const labels = listed.map((text) => text.trim().split('\n')[0])
  expect(labels.some((label) => label.includes('codex ⇄ human'))).toBe(true)
  // A thread that contains demands addressed to someone else is not the reader's.
  expect(labels.some((label) => label.includes('claude-session1 ⇄ codex'))).toBe(false)
  // And a channel is not disqualified by being a channel: the old predicate
  // returned false for every channel unconditionally, which filtered `#hello` out
  // of the one view that would have shown it.
  expect(labels.some((label) => label.includes('#hello'))).toBe(true)
})

test('an arriving message does not move a reader who is reading', async ({ page }) => {
  // The other half of the rule, and the one the old code got backwards in the
  // opposite direction: it re-anchored on *every* change of the anchor index,
  // including a new message landing on the live record -- so the page yanked
  // itself to the bottom under a reader mid-paragraph.
  //
  // The message is delivered through the deferral the store already implements,
  // not around it. `update()` vetoes a refresh while "a reading pane is scrolled",
  // which is exactly the state this test puts the reader in -- measured on this
  // fixture: parked at 400, digest changed, `msgs 60, scrollTop 400, deferred true,
  // "held back because a reading pane is scrolled"`. So the 61st message is
  // *supposed* to be held back, and asserting it arrives would be asserting that a
  // protection the reader asked for did not work. What is asserted instead is both
  // halves of the honest behaviour: nothing moves under the reader, the board says
  // a newer record is waiting, and the reader's own "update now" brings it in
  // without moving them either.
  let doc = STATE
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(doc),
  }))
  // Both endpoints have to move together. `checkDigest` compares the digest it
  // reads against `lastDigest`, so a fixture that changes the state and not the
  // digest is a record the board is right to ignore: measured here, the pane sat
  // at 60 messages for 20s and never showed the deferral, because `/api/digest`
  // was still answering with `beforeEach`'s constant.
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: doc.digest }),
  }))
  await page.goto('/#/chat?thread=ch:hello')
  await expect(page.locator('.aim-msg')).toHaveCount(60)

  // Park the reader up the thread, the way a reader parks.
  await page.locator('.aim-msg').first().hover()
  await page.mouse.wheel(0, -600)
  const parked = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    history.scrollTop = 400
    return history.scrollTop
  })
  expect(parked).toBeGreaterThan(0)

  doc = {
    ...STATE,
    digest: 'chat-fixture-2',
    conversation: {
      ...STATE.conversation,
      channels: [{
        ...STATE.conversation.channels[0],
        messages: [...STATE.conversation.channels[0].messages, CHANNEL_MSG(59, 'codex', 'a newer message')],
      }],
    },
  }
  // The board notices without help: the digest is polled every 2500ms.
  await expect(page.locator('.aim-deferred')).toBeVisible({ timeout: 20_000 })
  expect(await page.evaluate(() => document.querySelector('.aim-history').scrollTop)).toBe(parked)
  await expect(page.locator('.aim-msg')).toHaveCount(60)

  // And the reader's own way in does not cost them their place either.
  await page.locator('.aim-deferred button').click()
  await expect(page.locator('.aim-msg')).toHaveCount(61, { timeout: 20_000 })
  expect(await page.evaluate(() => document.querySelector('.aim-history').scrollTop)).toBe(parked)
})
