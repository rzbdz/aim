import { expect, test } from '@playwright/test'
import { PHASES } from '../src/concepts.js'

/**
 * T-0192 — the leader card, and the seals as rows.
 *
 * Measured on the live board (127.0.0.1:8777, viewer `human`, 1440x1000,
 * `#/barrier`, default tab `#barrier-v0 — Synthesising`, revision
 * `bundle dbdd04e+dirty`) before this change:
 *
 *   .el-main.aim-main        951px box over 5400px of content
 *   topic/leader/phase block y= 109  ~1000px   (an `el-descriptions`, 12 cells)
 *   the chain                 y= 344   287px
 *   seals                     y= 645  3931px   2 rows, 12 claims printed inline
 *   refusals                  y=4591   497px   0 rows
 *   phase history             y=5102   284px   3 rows
 *   controls in the DOM       an icon button at y=12 and a `clear` at y=788
 *
 * 73% of the page was one card holding two rows, and the page whose own header
 * said "only the leader moves it" offered no way to move it. Per channel from
 * `/api/state`: barrier-v0 2 seals/12 claims -> 3931px, hello 2/15 -> 2678px.
 *
 * Three properties are asserted here, each with the fixture that makes it
 * falsifiable:
 *
 *  1. the leader card is above the chain card — by bounding box, because DOM
 *     order alone is satisfied by a card that a later rule has floated to the
 *     bottom of the pane;
 *  2. the advance control is drawn for the channel's leader and for nobody
 *     else, and the argv on it is the argv it posts. Two fixtures, one payload:
 *     the *only* difference between them is the identity the page was told it
 *     is, so the second case fails the moment the control is unconditional;
 *  3. the whole pane fits the scroller. That is the assertion that fails on the
 *     5400px page: on the fixture below with the claims inline it measures
 *     2457px of content in a 957px box, and one expanded seal alone takes it to
 *     1695px — which is allowed, because opening a seal is the reader asking.
 *     The 2457px is the one that is not: nothing was opened and the last card
 *     still ended 1436px below the fold.
 *
 * `el-tabs` keeps every pane in the DOM with `display:none`, so every locator
 * here is scoped to `.el-tab-pane:visible` — the same rule `barrier.spec.js`
 * documents, for the same reason: an unscoped count of `.aim-claim` counts the
 * panes nobody is looking at.
 *
 * The numbers above come from the probe harness named in the report
 * (`/tmp/aim-tasks/reports/T-0192.md`), which mounts this same `.vue` file under
 * this same payload. **The agent that wrote this file did not run it** — the
 * coordinator owns every Playwright run, and that run is what turns these
 * numbers into a verdict.
 */

test.use({ viewport: { width: 1440, height: 1000 } })

/** 12 claims over two seals, in the shape `/api/state` serves them. */
const CLAIMS = (agent, n, offset) => Array.from({ length: n }, (_, i) => ({
  id: `${agent}-C${offset + i + 1}`,
  // A marker per claim, so "is this claim on screen" is a question about one
  // string rather than about the shape of the card's copy.
  claim: `T0192CLAIM-${agent}-${offset + i + 1} ${'x'.repeat(80)}`,
  confidence: 0.7,
  kill_if: `the observation that would retire claim ${offset + i + 1}`,
}))

const CHANNEL = {
  id: 'barrier-v0',
  phase: 'SYNTHESIS',
  topic: 'Is a file-first, phase-gated barrier between independent agents real?',
  leader: 'human',
  participants: ['codex', 'claude-session1'],
  round: 0,
  concessions: 0,
  tasks_recorded: 3,
  tasks_unknown_events: 0,
  // One chain row, one history row, no refusals: the evidence sections as small
  // as the payload allows. They are not what this file is about, and a fat chain
  // card would let a pane that is still 4000px tall pass a "fits the scroller"
  // assertion if the viewport were taller than the barrier.
  chain: { 'log.jsonl': { state: 'OK', records: 2, why: 'fixture' } },
  sealed: [
    { agent: 'claude-session1', sealed: true, claims_count: 6, ts: '2026-09-21T07:38:59.423Z',
      digest: 'fa3ca2723eff480762423f7e8801c25413afa94f60afd336426830fdf5ffb533',
      claims: CLAIMS('claude-session1', 6, 0) },
    { agent: 'claude-session2', sealed: true, claims_count: 6, ts: '2026-09-21T07:43:39.784Z',
      digest: 'be8cb681495e327769fb289a2564a235839a96cee20c0e5ff55e52a504f5f89a',
      claims: CLAIMS('claude-session2', 6, 0) },
  ],
  refusals: [],
  history: [{ at: '2026-09-21T07:38:29.971Z', phase: 'SEALED_DIVERGENT', by: 'human',
              note: 'channel opened' }],
}

const STATE = {
  digest: 't0192-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  viewer: 'human',
  viewer_kind: 'human',
  statuses: ['backlog', 'done'],
  terminal: ['done'],
  phase: 'SYNTHESIS',
  milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'codex', model: 'gpt-5' } },
  register: {},
  tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [CHANNEL],
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: true, as: 'human' },
}

/**
 * The same payload, read as a participant.
 *
 * `write` is deliberately left enabled and still names `human`: the write
 * posture is the server's and never varies with the seat, and keeping it
 * identical means the only thing that differs between this fixture and `STATE`
 * is `viewer`. A control that renders for both is a control gated on the wrong
 * thing.
 */
const PARTICIPANT = { ...STATE, viewer: 'codex', viewer_kind: 'codex' }

/**
 * The move the fixture is waiting on, from the lifecycle rather than typed.
 *
 * `PHASES[].next` is the forward edge. It is *not* "the first of
 * `TRANSITIONS[current]`": at CROSS_EXAMINE the machine also offers a re-seal
 * back to SYNTHESIS, and a test that read the transition table's first entry
 * would disagree with the page at exactly the phase where the choice matters.
 */
const NEXT = PHASES.find((p) => p.key === CHANNEL.phase).next
const ARGV = `aim advance --as ${CHANNEL.leader} --channel ${CHANNEL.id} --to ${NEXT}`

async function serve(page, state) {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(state),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: state.digest }),
  }))
}

const pane = (page) => page.locator('.el-tab-pane:visible')
const leaderCard = (page) => page.locator('.el-tab-pane:visible .aim-leader-card')
const advanceButton = (page) => page.locator('.el-tab-pane:visible .aim-advance')

/**
 * The scroller the reader actually scrolls: its own height, the height of what
 * is in it, and where the last card ends relative to the box's top edge.
 *
 * Both of the last two matter and they differ by `.aim-main`'s 64px bottom
 * padding (`web/src/style.css:92`). `scrollHeight > clientHeight` is the number
 * the task file names — *is there anything to scroll*. The last card's bottom is
 * what the reader sees: 64px of trailing whitespace is not content, and a test
 * that only asserted the first would call a page with nothing left to read
 * "overflowing".
 */
async function scroller(page) {
  return page.evaluate(() => {
    const main = document.querySelector('.el-main.aim-main')
    if (!main) return null
    const visible = (el) => !!el && el.getClientRects().length > 0
    const pane = [...document.querySelectorAll('.el-tab-pane')].find(visible)
    const cards = pane ? [...pane.querySelectorAll('.el-card')].filter(visible) : []
    const box = main.getBoundingClientRect()
    return {
      client: main.clientHeight,
      scroll: main.scrollHeight,
      contentBottom: cards.length ? Math.round(cards.at(-1).getBoundingClientRect().bottom - box.top) : 0,
      cards: cards.length,
    }
  })
}

const fitMessage = (m, tag) => `${tag}: .el-main.aim-main is ${m.client}px tall holding ${m.scroll}px `
  + `(${m.cards} card(s); the last one ends ${m.contentBottom}px below the top of the box, so `
  + `${Math.max(0, m.contentBottom - m.client)}px of it is past the fold)`

test('the whole pane fits the scroller, and the claims are behind their seal rows', async ({ page }) => {
  await serve(page, STATE)
  await page.goto('/#/barrier')

  // Both seals, and their counts, are on the page -- collapsed is not deleted.
  await expect(pane(page)).toContainText('claude-session1')
  await expect(pane(page)).toContainText('claude-session2')

  // Twelve claims exist in the payload and none of them is rendered. Counting
  // *visible* claims rather than `.aim-claim` nodes is deliberate: an
  // implementation that keeps them mounted and hides them is honest too, and
  // this is the assertion both shapes pass and the inline one fails.
  await expect(page.locator('.el-tab-pane:visible .aim-claim').filter({ visible: true }))
    .toHaveCount(0)
  const markers = await page.locator('.el-tab-pane:visible').innerText()
  expect(markers, 'a claim body is on screen before its seal row was opened')
    .not.toContain('T0192CLAIM-')

  // The measurement the task names: `.el-main.aim-main`'s scrollHeight against
  // its clientHeight. Unchanged before this, on this fixture: 2457/957. After:
  // 1006/957 -- and the 49px is `.aim-main`'s own 64px bottom padding, so the
  // last card ends 942px below the top of a 957px box. Both numbers are printed,
  // because "does it fit" is a statement about a box.
  const closed = await scroller(page)
  expect(closed, 'no .el-main.aim-main scroller on the page').not.toBeNull()
  expect(closed.contentBottom,
    fitMessage(closed, 'collapsed')).toBeLessThanOrEqual(closed.client)
})

test('a seal row opens onto its own claims', async ({ page }) => {
  await serve(page, STATE)
  await page.goto('/#/barrier')

  // Two seals, two claim sets, and the fixture gives each claim a marker with
  // its author in it -- so "the row opened *its* claims" is a question this can
  // answer, and a card that opened both rows on one click would fail it.
  const first = page.locator('.el-tab-pane:visible .aim-seal-toggle').first()
  await expect(first).toBeVisible()
  await expect(page.locator('.el-tab-pane:visible')).not.toContainText('T0192CLAIM-claude-session1')
  await expect(page.locator('.el-tab-pane:visible')).not.toContainText('T0192CLAIM-claude-session2')

  await first.click()

  // Six claims, the first row's, and only the first row's.
  await expect(page.locator('.el-tab-pane:visible .aim-claim').filter({ visible: true }))
    .toHaveCount(6)
  await expect(page.locator('.el-tab-pane:visible')).toContainText('T0192CLAIM-claude-session1')
  await expect(page.locator('.el-tab-pane:visible')).not.toContainText('T0192CLAIM-claude-session2')

  // Expanding is a deliberate act, and it is allowed to overflow: the reader who
  // opens six claims has asked for 688px more than the box holds (measured:
  // 1695/957 with one row open) and the scroller is still what scrolls. Asserting
  // the *collapsed* pane fits is the claim; asserting this one does would be a
  // claim that the page cannot show a seal's contents at all.
  const expanded = await scroller(page)
  expect(expanded.contentBottom,
    fitMessage(expanded, 'one seal expanded')).toBeGreaterThan(expanded.client)

  // And it closes again.
  await first.click()
  await expect(page.locator('.el-tab-pane:visible .aim-claim').filter({ visible: true }))
    .toHaveCount(0)
})

test('the leader card is above the chain, and states the move with its exact argv', async ({ page }) => {
  const posted = []
  await serve(page, STATE)
  // The write path is stubbed at the wire, not at the pane: what is asserted is
  // the argv that reaches `POST /api/command`, which is the command the card
  // prints (see the pane's `advance()` -- the same function builds both).
  await page.route('**/api/command**', (route) => {
    posted.push(route.request().postDataJSON())
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, rc: 0, argv: posted.at(-1)?.argv, stdout: 'advanced', stderr: '' }),
    })
  })
  await page.goto('/#/barrier')

  const card = leaderCard(page)
  await expect(card).toBeVisible()
  // It states what the channel is, and which phase it is in.
  await expect(card).toContainText('Is a file-first, phase-gated barrier between independent agents real?')
  await expect(card).toContainText('Synthesising')

  // Above the chain, by geometry. DOM order alone would be satisfied by a card
  // that a rule has floated below the evidence, which is the failure the reader
  // would actually see: two boxes, and the wrong one on top.
  const chainHeader = page.locator('.el-tab-pane:visible .el-card__header')
    .filter({ hasText: 'the chain' })
  await expect(chainHeader).toBeVisible()
  const cardBox = await card.boundingBox()
  const chainBox = await chainHeader.boundingBox()
  expect(cardBox, 'the leader card has no box').not.toBeNull()
  expect(chainBox, 'the chain card has no box').not.toBeNull()
  expect(cardBox.y, `leader card at y=${cardBox.y}, the chain at y=${chainBox.y}`)
    .toBeLessThan(chainBox.y)

  // The action, and the argv behind it, for the leader.
  await expect(advanceButton(page)).toBeVisible()
  await expect(page.locator('.el-tab-pane:visible .aim-leader-argv')).toHaveText(ARGV)

  await advanceButton(page).click()
  await expect.poll(() => posted.length).toBeGreaterThan(0)
  expect(posted[0].argv, `the control printed ${ARGV} and posted ${JSON.stringify(posted[0].argv)}`)
    .toEqual(['advance', '--as', CHANNEL.leader, '--channel', CHANNEL.id, '--to', NEXT])
})

test('a viewer who is not the leader is offered no advance control', async ({ page }) => {
  await serve(page, PARTICIPANT)
  await page.goto('/#/barrier')

  // The card still says what the channel is and where it is: the topic and the
  // phase are facts about the channel, not about the reader.
  const card = leaderCard(page)
  await expect(card).toBeVisible()
  await expect(card).toContainText('Synthesising')

  // ... and the action is absent, control and argv both. Measured: the same
  // payload with `viewer: "codex"` and the write posture unchanged.
  await expect(advanceButton(page)).toHaveCount(0)
  await expect(card).not.toContainText('aim advance')
})
