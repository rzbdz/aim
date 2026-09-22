import { expect, test } from '@playwright/test'
import { PHASES } from '../src/concepts.js'

/**
 * T-0192 — "Audit & barrier: one heading over 5400px, and the leader's only
 * action is 4000px down".
 *
 * The card's acceptance, verbatim:
 *
 *   "The page states its purpose in one sentence, is ordered barrier-first and
 *    evidence-second, its leader action is above the fold, sealed claims are
 *    collapsed, and empty sections are one line."
 *
 * The card is also explicit about the shape of that one action (its "Two
 * minimal changes", item 1): a leader card above the chain, carrying the exact
 * argv `aim advance --as human --channel <id> --to <next phase>`, and nothing
 * rendered when the viewer is not that channel's leader.
 *
 * Revision measured — `curl -s http://127.0.0.1:8777/api/revision`:
 *   fabric  dc2e212+dirty
 *   bundle  e3824c5+dirty, built 2026-09-22T08:15:50Z
 *   stale   true   (the running bundle was NOT built from the source in this
 *                   checkout; a page measured here may not be the page in
 *                   web/src. Reported, not resolved, by this file.)
 *
 * Ground truth on 127.0.0.1:8777/#/barrier, viewer human, 1440x1000, channel
 * `barrier-v0` (2 seals / 12 claims, 0 refusals): the scroller `.aim-main` is
 * 951px tall over 5400px of content; the page has exactly one heading, "Audit &
 * barrier"; the four cards stand at
 *
 *     the chain     top= 294  h= 287px
 *     seals         top= 595  h=3931px   (73% of the page)
 *     refusals      top=4541  h= 497px   (0 of 0 records)
 *     phase history top=5052  h= 284px   ("only the leader moves it")
 *
 * and no element in the pane contained the string `aim advance`. The page could
 * not satisfy the acceptance then, so every test that encoded a missing clause
 * was declared with `test.fail(true, ...)`. Each failure is a measurement, and
 * the day the page starts passing it, Playwright reports "passed unexpectedly":
 * the annotation is then to be removed, never the assertion.
 *
 * That day came: `BarrierPane.vue` grew the leader card, the purpose sentence
 * and the collapsed seal rows, and all five annotated tests ran "Expected to
 * fail, but passed" on the bundle built 2026-09-22T10:44Z. The five annotations
 * are therefore gone and the assertions are untouched -- the numbers in the
 * measurements block above are history, not a description of the current pane.
 *
 * Assertions are made against a fixture, because the acceptance is about the
 * page's shape and not about what the live fabric holds today. The fixture keeps
 * the two properties the card's numbers turn on: seals rich enough to blow the
 * page up if their claims are printed inline, and a refusals table with nothing
 * in it.
 */

// The card's numbers were taken in a 1440x1000 frame, where `.aim-main` is
// 951px tall; the assertions about "above the fold" and the section heights are
// only comparable to it in the same frame.
test.use({ viewport: { width: 1440, height: 1000 } })

const claims = (n) => Array.from({ length: n }, (_, i) => ({
  id: `C${i + 1}`,
  claim: `claim ${i + 1}: `.padEnd(60, 'x'),
  confidence: 0.6,
  kill_if: 'y'.repeat(90),
}))

const CHANNEL = {
  id: 'barrier-v0',
  phase: 'COMMIT',
  topic: 'does the barrier hold',
  leader: 'human',
  participants: ['codex', 'claude-session1'],
  round: 0,
  concessions: 0,
  tasks_recorded: 0,
  tasks_unknown_events: 0,
  chain: { 'log.jsonl': { state: 'OK', records: 2, why: 'fixture' } },
  sealed: [
    { agent: 'codex', sealed: true, claims_count: 12, ts: '2026-09-22T00:00:00.000Z', digest: 'a1b2c3d4e5f6', claims: claims(12) },
    { agent: 'claude-session1', sealed: true, claims_count: 3, ts: '2026-09-22T00:01:00.000Z', digest: 'f6e5d4c3b2a1', claims: claims(3) },
  ],
  refusals: [],
  history: [{ at: '2026-09-22T00:00:00.000Z', phase: 'COMMIT', by: 'human', note: '' }],
}

const STATE = {
  digest: 't0192-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  viewer: 'human',
  statuses: ['backlog', 'done'],
  terminal: ['done'],
  phase: 'COMMIT',
  milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' } },
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

/** The state a reader who is *not* this channel's leader is looking at. */
const NOT_LEADER = { ...STATE, viewer: 'codex', write: { enabled: false, as: 'codex' } }

/** Every section on the page is empty here, which is the card's point 4. */
const EMPTY = {
  ...STATE,
  channels: [{ ...CHANNEL, sealed: [], refusals: [], history: [] }],
}

const NEXT = PHASES.find((p) => p.key === CHANNEL.phase).next
const ARGV = `aim advance --as human --channel barrier-v0 --to ${NEXT}`

async function routeState(page, state) {
  await page.unroute('**/api/state**').catch(() => {})
  await page.unroute('**/api/digest**').catch(() => {})
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(state),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: state.digest }),
  }))
}

/**
 * One pass over the rendered pane, in the reader's units.
 *
 * `top` is measured from the top of `.aim-main`, the container the reader
 * actually scrolls -- the same frame the card's numbers were taken in, and the
 * only frame in which "above the fold" means anything.
 */
function snapshot() {
  const scroller = document.querySelector('.aim-main')
  const base = scroller ? scroller.getBoundingClientRect().top : 0
  const pane = [...document.querySelectorAll('.el-tab-pane')].find((p) => p.offsetParent !== null) || null
  const top = (el) => Math.round(el.getBoundingClientRect().top - base)
  const height = (el) => Math.round(el.getBoundingClientRect().height)
  const cards = pane ? [...pane.querySelectorAll('.el-card')].map((el) => {
    const head = el.querySelector('.el-card__header')
    return {
      header: (head ? head.innerText : '').trim().split('\n')[0],
      top: top(el), height: height(el), text: el.innerText,
    }
  }) : []
  const refusalEl = pane ? [...pane.querySelectorAll('.el-card')].find((el) => (
    ((el.querySelector('.el-card__header') || {}).innerText || '').trim().toLowerCase()
      .startsWith('refusals'))) : null
  return {
    scrollerH: scroller ? scroller.clientHeight : 0,
    scrollH: scroller ? scroller.scrollHeight : 0,
    cards,
    // Statements of one sentence, wherever the page puts them -- exactly one
    // terminator, so an element holding two sentences is not a purpose line.
    sentences: pane ? [...pane.querySelectorAll('p, span, div, li, header, h1, h2, h3')]
      .filter((el) => el.offsetParent !== null && (el.innerText || '').trim())
      .map((el) => ({ text: (el.innerText || '').trim(), top: top(el) }))
      .filter((row) => /^[A-Z][^.!?]{15,220}\.$/.test(row.text)) : [],
    // Claim bodies are the `confidence … · would change my mind: …` lines. If
    // the claims are collapsed, none of them is on screen.
    claimsInline: pane ? [...pane.querySelectorAll('div, span, p')]
      .filter((el) => el.offsetParent !== null && /^confidence\b/.test((el.innerText || '').trim())).length : 0,
    leader: cards.find((c) => c.text.includes('aim advance')) || null,
    refusals: refusalEl
      ? { top: top(refusalEl), height: height(refusalEl), selects: refusalEl.querySelectorAll('.el-select').length }
      : null,
  }
}

const cardAt = (s, prefix) => s.cards.find((c) => c.header.toLowerCase().startsWith(prefix))
const positions = (s) => s.cards.map((c) => `${c.header}@${c.top}=${c.height}px`).join(' | ')

test.beforeEach(async ({ page }) => {
  await routeState(page, STATE)
})

test('the page states its purpose in one sentence', async ({ page }) => {
  await page.goto('/#/barrier')
  await expect(page.locator('.el-tab-pane:visible')).toBeVisible()
  const s = await page.evaluate(snapshot)
  const seals = cardAt(s, 'seals')
  expect(seals, `no seals card to measure against: ${positions(s)}`).toBeTruthy()
  const purpose = s.sentences.filter((row) => row.top < seals.top
    && /barrier|phase|leader|seal|audit/i.test(row.text))
  expect(purpose.length,
    `one-sentence purpose lines above the evidence: ${JSON.stringify(purpose)}; `
    + `every one-sentence element on the page: ${JSON.stringify(s.sentences)}`).toBeGreaterThanOrEqual(1)
})

test('the pane is ordered barrier-first and evidence-second', async ({ page }) => {
  await page.goto('/#/barrier')
  await expect(page.locator('.el-tab-pane:visible')).toBeVisible()
  const s = await page.evaluate(snapshot)
  const chain = cardAt(s, 'the chain')
  const seals = cardAt(s, 'seals')
  expect(chain, `no chain card: ${positions(s)}`).toBeTruthy()
  expect(seals, `no seals card: ${positions(s)}`).toBeTruthy()
  // The barrier is where the reader may act; the audit is what they may enter.
  // Every measured section position (and height) is carried in the failure
  // message, so a red run reports the numbers rather than only the verdict.
  expect(s.leader,
    `no card on the page carries the leader action; sections measured: ${positions(s)}`).not.toBeNull()
  expect(s.leader.top, `sections measured: ${positions(s)}`).toBeLessThan(chain.top)
  expect(s.leader.top, `sections measured: ${positions(s)}`).toBeLessThan(seals.top)
})

test("the leader's action is above the fold and renders the exact aim advance argv", async ({ page }) => {
  await page.goto('/#/barrier')
  await expect(page.locator('.el-tab-pane:visible')).toBeVisible()
  const s = await page.evaluate(snapshot)
  expect(s.leader,
    `sections measured: ${positions(s)}; scroller ${s.scrollerH}px over ${s.scrollH}px`).not.toBeNull()
  // The command is the action: a control that only opens a pane is a dead end
  // (AGENTS.md), so the exact argv has to be on the page, not inferred.
  expect(s.leader.text,
    `leader card text: ${JSON.stringify(s.leader.text)}; expected to contain ${JSON.stringify(ARGV)}`)
    .toContain(ARGV)
  const bottom = s.leader.top + s.leader.height
  expect(bottom,
    `leader card bottom ${bottom}px vs the fold at ${s.scrollerH}px (top ${s.leader.top}, height ${s.leader.height})`)
    .toBeLessThanOrEqual(s.scrollerH)

  // The other half of the card body's rule: a viewer who is not the channel's
  // leader is shown no leader action at all.
  await routeState(page, NOT_LEADER)
  await page.reload()
  await expect(page.locator('.el-tab-pane:visible')).toBeVisible()
  const other = await page.evaluate(snapshot)
  expect(other.leader,
    `the leader action renders for viewer "codex" though the channel's leader is "${CHANNEL.leader}"`)
    .toBeNull()
})

test('sealed claims are collapsed behind their seal rows', async ({ page }) => {
  await page.goto('/#/barrier')
  await expect(page.locator('.el-tab-pane:visible')).toBeVisible()
  const s = await page.evaluate(snapshot)
  const seals = cardAt(s, 'seals')
  expect(seals, `no seals card: ${positions(s)}`).toBeTruthy()
  // Collapsed, not deleted: both seals and their claim counts stay on the page.
  expect(seals.text, 'the seals card no longer names its seals').toContain('codex')
  expect(seals.text, 'the seals card no longer names its seals').toContain('claude-session1')
  expect(seals.text, 'the seals card no longer shows a claims count').toContain('12')
  expect(seals.text, 'the seals card no longer shows a claims count').toContain('3')
  // ... but the claim bodies are behind an expansion.
  expect(s.claimsInline,
    `${s.claimsInline} claim body(ies) rendered inline; the seals card is ${seals.height}px, `
    + `the card's target is ~200px`).toBe(0)
  expect(seals.height,
    `seals card ${seals.height}px against the card's ~200px target`).toBeLessThanOrEqual(400)
})

test('an empty section renders as one line', async ({ page }) => {
  await routeState(page, EMPTY)
  await page.goto('/#/barrier')
  await expect(page.locator('.el-tab-pane:visible')).toBeVisible()
  const s = await page.evaluate(snapshot)
  expect(s.refusals, `no refusals section: ${positions(s)}`).not.toBeNull()
  expect(s.refusals.height,
    `empty refusals section is ${s.refusals.height}px with ${s.refusals.selects} filter select(s); `
    + `sections measured: ${positions(s)}`).toBeLessThanOrEqual(60)
  expect(s.refusals.selects,
    `an empty table offers ${s.refusals.selects} filter(s) over nothing`).toBe(0)
})
