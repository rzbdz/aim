/**
 * T-0165 -- "Scope action feedback to the row that owns the action".
 *
 * Card text (`channels/hello/tasks.jsonl`, `created` 2026-09-22T03:02:06.931Z,
 * actor codex, owner claude-session1), verbatim acceptance:
 *
 *   "Confirm-receipt success/error appears on the message row that owns it and
 *    never on a phase request; phase approve/reject success/error appears only on
 *    that request card; busy and result state are keyed by action identity; a
 *    failure in one action does not disable or annotate unrelated rows; Playwright
 *    covers two phase requests plus a receipt action and asserts the error is
 *    visible only on the initiating surface"
 *
 * The card was moved to `doing` with the reproduction that named it: "clicking
 * confirm receipt with no write permission rendered The tool refused this action
 * inside the unrelated Leader Decisions phase card".
 *
 * Revision measured -- `curl -s http://127.0.0.1:8777/api/revision`, 2026-09-22:
 *
 *   fabric f0c4d64+dirty
 *   bundle f0c4d64+dirty, built 2026-09-22T08:33:19.792Z, source "vite build"
 *   stale  true   (front_end_sha256 425d390... answered 08:31:54, then
 *                 18fcafd... at 08:34:58; the bundle answering 8777 was not
 *                 built from the `web/src` checked out beside it, and peers were
 *                 rebuilding it during this run. A verdict here is a verdict
 *                 about the bundle that answerered.)
 *
 * What the defect is, so the fixture below is not arbitrary.
 * `web/src/panes/OverviewPane.vue` holds one `actionBusy` and one `actionError`
 * for the whole page, and passes `:error="actionError"` to every
 * `PhaseApprovalCard`; the bundle answering 8777 does the same (`n.error` in
 * `dist/assets/OverviewPane-*.js`). So a refusal from any action is drawn by
 * every phase-request card, and the message row that asked for a receipt has no
 * error surface at all. The confirm button's `loading` is already keyed
 * (`confirm:${msg_id}`) and each card's approve/decline loading is keyed
 * (`advance|reject:${channel}:${ts}`), which is why the busy half of the
 * acceptance measures green and the attribution half measures red.
 *
 * The fixture is the smallest page that can tell those two halves apart: two
 * phase requests on two channels (so a refusal can be attributed to one card and
 * provably absent from the other) plus one direct message that still owes a
 * receipt (so a receipt refusal has a row of its own). The command route refuses
 * with the argv it was handed, so the text on screen names the action that
 * failed -- attribution is asserted by which surface holds that text, not by
 * counting alerts.
 *
 * A test that cannot pass against the bundle measured here carries
 * `test.fail(true, ...)` so the suite stays green and the failure stays recorded
 * as a measurement. The day the page starts passing, Playwright reports "passed
 * unexpectedly"; the annotation is then removed, never the assertion.
 */
import { expect, test } from '@playwright/test'

const stamp = (ts) => ts.replace(/[-:]/g, '')

/**
 * A channel row of kind `request`, the shape `board.phaseRequests` filters for:
 * `subject` must match `request: FROM -> TO` and the channel's current phase must
 * equal FROM, or the card is not drawn at all (and the fixture would be measuring
 * nothing).
 */
const phaseRequest = (channel, fromPhase, toPhase, ts, from) => ({
  from, to: channel, kind: 'request', ts,
  subject: `request: ${fromPhase} -> ${toPhase}`,
  body: `${from} asks to move ${channel} from ${fromPhase} to ${toPhase}.`,
  msg_id: `${stamp(ts)}-${from}`,
})

/** A direct message the viewer still owes a receipt: the row that owns `confirm receipt`. */
const unackedDirect = (ts, { from = 'claude-session1', to = 'human' } = {}) => ({
  from, to, ts, subject: 'the message waiting on a receipt', body: 'a long message body',
  msg_id: `${stamp(ts)}-${from}`,
  ack_required: true, acked_at: '', claimed_at: '', bytes: 120, state: 'delivered',
})

const ALPHA_TS = '2026-09-22T09:00:00.000Z'
const BETA_TS = '2026-09-22T09:05:00.000Z'
const MAIL_TS = '2026-09-22T09:10:00.000Z'

const MAIL = unackedDirect(MAIL_TS)
const ACKED = { ...MAIL, acked_at: '2026-09-22T09:11:00.000Z', state: 'acked' }

/** The two names the request cards print, and the only honest way to tell them apart. */
const ALPHA = 'codex asks COMMIT \u2192 SYNTHESIS'
const BETA = 'claude-session1 asks SEALED_DIVERGENT \u2192 COMMIT'

const state = (mail) => ({
  digest: 't0165-fixture', generated_at: '2026-09-22T09:10:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'COMMIT',
  milestones: {}, agents: {}, register: {}, tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: {
    viewer: 'human', is_leader: true, withheld: 0, rooms: [], mail,
    channels: [
      { id: 'alpha', gated: false, rule: '', messages: [phaseRequest('alpha', 'COMMIT', 'SYNTHESIS', ALPHA_TS, 'codex')] },
      { id: 'beta', gated: false, rule: '', messages: [phaseRequest('beta', 'SEALED_DIVERGENT', 'COMMIT', BETA_TS, 'claude-session1')] },
    ],
  },
  channels: [
    { id: 'alpha', phase: 'COMMIT', leader: 'human', participants: ['codex', 'human'], round: 0 },
    { id: 'beta', phase: 'SEALED_DIVERGENT', leader: 'human', participants: ['claude-session1', 'human'], round: 1 },
  ],
  unacked: [{ msg_id: MAIL.msg_id, from: MAIL.from, to: MAIL.to, subject: MAIL.subject, bytes: MAIL.bytes }],
  drift: [], withheld_tasks: 0,
  write: { enabled: true, as: 'human' },
})

const requestCards = (page) => page.locator('.aim-phase-request')
const requestCard = (page, text) => requestCards(page).filter({ hasText: text })
const mailRow = (page) => page.locator('.aim-attention-row')
  .filter({ has: page.getByRole('button', { name: 'confirm receipt' }) })

/**
 * Every visible surface that carries a refusal, named by the row or card it is
 * drawn on.
 *
 * Read from the DOM rather than by counting `.el-alert--error`, so the verdict
 * does not depend on the refusal being drawn as an `el-alert`: what the card asks
 * is *where* the text lands. The innermost element holding the text is the one
 * counted, so an ancestor that merely contains it does not add a surface.
 */
async function refusalSurfaces(page) {
  return page.evaluate(() => {
    const seen = new Map()
    for (const el of document.querySelectorAll('body *')) {
      if (typeof el.innerText !== 'string' || !el.innerText.includes('REFUSED')) continue
      if ([...el.querySelectorAll('*')].some((child) => (child.innerText || '').includes('REFUSED'))) continue
      const box = el.getBoundingClientRect()
      if (!box.width && !box.height) continue
      const card = el.closest('.aim-phase-request')
      const row = el.closest('.aim-attention-row')
      const surface = card
        ? `phase-request: ${(card.querySelector('p') || {}).innerText || ''}`.trim()
        : row ? `message-row: ${(row.innerText || '').split('\n')[0]}`.trim()
          : `page: ${(el.className || el.tagName).toString()}`
      if (!seen.has(surface)) seen.set(surface, (el.innerText || '').trim().slice(0, 160))
    }
    return [...seen.entries()].map(([surface, text]) => ({ surface, text }))
  })
}

/** The refusal is rendered asynchronously: wait for it to exist somewhere first. */
const waitForRefusal = (page) => expect
  .poll(() => refusalSurfaces(page).then((surfaces) => surfaces.length),
    'no surface on the page ever showed the refusal')
  .toBeGreaterThan(0)

test.describe('T-0165 action feedback belongs to the row that owns the action', () => {
  let doc
  let refuse
  let onSuccess
  let gate

  test.beforeEach(async ({ page }) => {
    doc = state([MAIL])
    refuse = true
    onSuccess = null
    gate = null
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(doc),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: 't0165-fixture' }),
    }))
    await page.route('**/api/command**', async (route) => {
      const { argv } = route.request().postDataJSON()
      if (gate) await gate
      if (!refuse) {
        if (onSuccess) doc = onSuccess(doc)
        return route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify({ ok: true, rc: 0, stdout: 'done', stderr: '' }),
        })
      }
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ ok: false, rc: 1, stdout: '', stderr: `aim: REFUSED: ${argv.join(' ')}` }),
      })
    })
  })

  test('a receipt refusal appears on the message row that owns it, and on no phase request', async ({ page }) => {
    test.fail(true, 'T-0165, bundle f0c4d64+dirty: the receipt refusal is drawn on both phase-request cards '
      + '(one shared `actionError` is passed to every PhaseApprovalCard) and on no part of the message row that asked for the receipt.')
    await page.goto('/#/attention')
    await expect(mailRow(page)).toHaveCount(1)
    await expect(requestCards(page)).toHaveCount(2)

    await mailRow(page).getByRole('button', { name: 'confirm receipt' }).click()
    await waitForRefusal(page)
    const surfaces = await refusalSurfaces(page)

    expect.soft(surfaces.filter((s) => s.surface.startsWith('phase-request')),
      `the receipt refusal is drawn on a phase request the reader did not touch: ${JSON.stringify(surfaces)}`)
      .toEqual([])
    expect.soft(surfaces.filter((s) => s.surface.startsWith('message-row')).length,
      `the row that owns the action shows its own refusal: ${JSON.stringify(surfaces)}`).toBe(1)
    expect.soft(surfaces, 'exactly one surface carries the refusal').toHaveLength(1)
  })

  test('a phase refusal appears only on the request card it was made from', async ({ page }) => {
    test.fail(true, 'T-0165, bundle f0c4d64+dirty: approving on the alpha request draws the refusal on the beta request too, '
      + 'because OverviewPane passes the page-wide `actionError` to every PhaseApprovalCard.')
    await page.goto('/#/attention')
    await expect(requestCards(page)).toHaveCount(2)

    await requestCard(page, ALPHA).getByRole('button', { name: 'Approve advance' }).click()
    await waitForRefusal(page)
    const surfaces = await refusalSurfaces(page)

    expect.soft(surfaces.map((s) => s.surface),
      `surfaces carrying the refusal: ${JSON.stringify(surfaces)}`)
      .toEqual([`phase-request: ${ALPHA}`])
    expect.soft(surfaces[0] && surfaces[0].text,
      'the refusal names the action that failed').toContain('advance --channel alpha --to SYNTHESIS')
  })

  test('a declined request refusal appears only on the request card it was made from', async ({ page }) => {
    test.fail(true, 'T-0165, bundle f0c4d64+dirty: declining on the beta request draws the refusal on the alpha request too, '
      + 'because OverviewPane passes the page-wide `actionError` to every PhaseApprovalCard.')
    await page.goto('/#/attention')
    await expect(requestCards(page)).toHaveCount(2)

    const beta = requestCard(page, BETA)
    await beta.getByPlaceholder('Reason if you decline this phase request').fill('the barrier is not ready')
    await beta.getByRole('button', { name: 'Decline with reason' }).click()
    await waitForRefusal(page)
    const surfaces = await refusalSurfaces(page)

    expect.soft(surfaces.map((s) => s.surface),
      `surfaces carrying the refusal: ${JSON.stringify(surfaces)}`)
      .toEqual([`phase-request: ${BETA}`])
    expect.soft(surfaces[0] && surfaces[0].text,
      'the refusal names the action that failed').toContain('say --channel beta --kind note')
  })

  test('busy is keyed by the action, so an in-flight request does not mark another row busy', async ({ page }) => {
    let release
    gate = new Promise((resolve) => { release = resolve })
    try {
      await page.goto('/#/attention')
      const approve = requestCard(page, ALPHA).getByRole('button', { name: 'Approve advance' })
      await approve.click()
      await expect(approve, 'the action the reader took is busy').toHaveClass(/is-loading/)
      await expect.soft(requestCard(page, BETA).getByRole('button', { name: 'Approve advance' }),
        'an unrelated request card is loading').not.toHaveClass(/is-loading/)
      await expect.soft(mailRow(page).getByRole('button', { name: 'confirm receipt' }),
        'an unrelated message row is loading').not.toHaveClass(/is-loading/)
    } finally {
      release()
    }
  })

  test('a refusal on one action does not disable the other rows', async ({ page }) => {
    await page.goto('/#/attention')
    await mailRow(page).getByRole('button', { name: 'confirm receipt' }).click()
    await waitForRefusal(page)

    await expect.soft(requestCard(page, ALPHA).getByRole('button', { name: 'Approve advance' }),
      'the alpha request card survived a failure it had nothing to do with').toBeEnabled()
    await expect.soft(requestCard(page, BETA).getByRole('button', { name: 'Approve advance' }),
      'the beta request card survived a failure it had nothing to do with').toBeEnabled()
    await expect.soft(mailRow(page).getByRole('button', { name: 'confirm receipt' }),
      'the row that failed is still usable for a retry').toBeEnabled()
  })

  test('a successful receipt leaves the phase requests unannotated and follows the new state', async ({ page }) => {
    refuse = false
    onSuccess = () => state([ACKED])
    await page.goto('/#/attention')
    await expect(mailRow(page).getByRole('button', { name: 'confirm receipt' })).toHaveCount(1)

    await mailRow(page).getByRole('button', { name: 'confirm receipt' }).click()

    // The success signal this UI has is the record's: the refetched state says
    // the message is acked, so the row stops offering the action -- and nothing
    // on the page reports a refusal.
    await expect(mailRow(page).getByRole('button', { name: 'confirm receipt' })).toHaveCount(0)
    await expect(page.getByText('The tool refused this action')).toHaveCount(0)
    expect(await refusalSurfaces(page)).toEqual([])
    await expect.soft(requestCard(page, ALPHA).getByRole('button', { name: 'Approve advance' })).toBeEnabled()
    await expect.soft(requestCard(page, BETA).getByRole('button', { name: 'Approve advance' })).toBeEnabled()
  })
})
