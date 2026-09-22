import { expect, test } from '@playwright/test'

/**
 * T-0227: work nobody has taken has to say so, and the row has to offer the one
 * command that takes it.
 *
 * The leader's rule is that a work item belongs to nobody until someone picks it
 * up. The tool could not produce that state until T-0226 (`bin/aim` wrote
 * `"owner": args.owner or who`, so `created` always carried a name), so this file
 * builds the state it is about with `page.route` rather than waiting for the live
 * fabric to hold one. Measured on the board at 8777 before this landed, with
 * `?unassigned=1` typed into the address bar:
 *
 *   /#/items              => rows 162, data-claim-command 0, data-unassigned 0
 *   /#/items?unassigned=1 => rows 162, data-claim-command 0, data-unassigned 0
 *
 * i.e. the query was ignored entirely and every row drew a blank owner cell --
 * which a reader cannot tell from "the field did not render".
 *
 * Two fixtures, one payload. That is deliberate: the *only* difference between
 * the participant case and the leader case is the identity the page was told it
 * is, so an assertion that the mark survives both while the control survives only
 * one is an assertion about the gate, not about the fixture.
 */

const TASK = (id, title, owner, extra = {}) => ({
  id, title, owner, status: 'backlog', priority: 'normal', milestone: '', tags: [], due: '',
  accept: `acceptance for ${id}`, blocked_by: [], visibility: 'published',
  provenance: 'store only', events: [], comments: [],
  channel: 'dev', context_id: 'dev', ...extra,
})

/**
 * `channel` is on each row on purpose.
 *
 * The claim command names a channel, and the one the row offers has to be the
 * channel the item is actually in -- `hello` and `dev` are both live here, and a
 * control that always said `hello` would name a channel the item is not in, which
 * is a command that fails the moment the reader runs it.
 */
const STATE = {
  digest: 'unassigned-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'doing', 'done'],
  terminal: ['done'],
  phase: 'SEALED_DIVERGENT',
  milestones: {},
  // Both the leader and a plain participant are registered: `claimable` reads the
  // registry's kind for the viewer, so a fixture with one agent in it could not
  // tell a gate from an empty dictionary.
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'codex', model: 'gpt-5' } },
  register: {},
  tasks: {
    'T-0001': TASK('T-0001', 'Nobody has taken this one', ''),
    'T-0002': TASK('T-0002', 'Someone already took this one', 'codex'),
    'T-0003': TASK('T-0003', 'Unowned, in another channel', '', { channel: 'hello', context_id: 'hello' }),
  },
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [
    { id: 'dev', phase: 'SEALED_DIVERGENT', participants: ['claude-session1', 'codex'],
      leader: 'human', gated: false, messages: [] },
    { id: 'hello', phase: 'SEALED_DIVERGENT', participants: ['claude-session1', 'codex'],
      leader: 'human', gated: false, messages: [] },
  ],
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: true, as: 'human' },
  read: { as: 'human', borrowed: false },
}

/** The same payload, read as the leader. The write gate never varies by viewer. */
const LEADER_STATE = { ...STATE, viewer: 'human', viewer_kind: 'human' }
/** The same payload, read as a registered non-human participant. */
const PARTICIPANT_STATE = { ...STATE, viewer: 'codex', viewer_kind: 'codex' }

/**
 * What the row offers, as the exact string the viewer would run.
 *
 * Asserted as a whole string. `toHaveText('claim')` would pass for a control
 * whose command names the wrong task, the wrong channel or an `--as` that is not
 * the viewer -- which is the failure this task exists to catch, and the board has
 * already shipped a control that promised a verb the tool does not have.
 */
const CLAIM = (viewer, id, channel = 'dev') =>
  `aim task claim --as ${viewer} --channel ${channel} --id ${id}`

async function stub(page, state) {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(state),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: state.digest }),
  }))
}

const row = (page, id) => page.locator('.el-table__body tr').filter({ hasText: id })
const card = (page, id) => page.locator(`.aim-card[data-id="${id}"]`)
/** Which rows are drawn, whether or not they are owned. */
const rowIds = (page) =>
  page.locator('.el-table__body tr td:first-child').allTextContents()
/**
 * Which rows the board is *calling* unowned.
 *
 * Read off the rows themselves rather than off the filter, so a page that drew
 * the right rows for the wrong reason -- a filter that narrowed nothing, a mark
 * that never rendered -- fails here instead of passing.
 */
const unownedIds = (page) =>
  page.locator('.el-table__body tr:has([data-unassigned]) td:first-child').allTextContents()

test.describe('an item nobody has taken', () => {
  test('is marked unassigned, in words rather than as a blank cell', async ({ page }) => {
    await stub(page, LEADER_STATE)
    await page.goto('/#/items')

    const open = row(page, 'T-0001')
    await expect(open.locator('[data-unassigned]')).toHaveText('unassigned')

    // The other half of the same claim: an item that *has* an owner must not be
    // painted as unowned. Without this the mark could be unconditional and every
    // assertion above would still pass.
    const taken = row(page, 'T-0002')
    await expect(taken).toContainText('codex')
    await expect(taken.locator('[data-unassigned]')).toHaveCount(0)
  })

  test('offers the exact command that takes it, and only for the viewer who can run it',
    async ({ page }) => {
      await stub(page, LEADER_STATE)
      await page.goto('/#/items?as=human')

      const control = row(page, 'T-0001').locator('[data-claim-command]')
      await expect(control).toHaveCount(1)
      // The whole string, including both names the command needs: the identity it
      // acts as and the item it acts on.
      await expect(control).toHaveAttribute('data-claim-command', CLAIM('human', 'T-0001'))
      await expect(control).toHaveAttribute('data-claim-id', 'T-0001')
      await expect(control).toHaveAttribute('data-claim-as', 'human')
      await expect(control).toHaveText(CLAIM('human', 'T-0001'))

      // The command names the item's own channel, not the first channel the board
      // happens to hold: T-0003 was written into `hello`, not into `dev`.
      await expect(row(page, 'T-0003').locator('[data-claim-command]'))
        .toHaveAttribute('data-claim-command', CLAIM('human', 'T-0003', 'hello'))

      // Only the unowned rows carry a claim control at all.
      await expect(page.locator('[data-claim-command]')).toHaveCount(2)
      await expect(row(page, 'T-0002').locator('[data-claim-command]')).toHaveCount(0)
    })

  test('a participant who cannot write is shown the mark and no control', async ({ page }) => {
    // Same payload, different identity. This is the half that fails if the
    // control is rendered unconditionally, and the mark has to survive it: a
    // reader must still be able to tell "nobody has taken this" from "the field
    // did not render", even when they are not the one who can take it.
    await stub(page, PARTICIPANT_STATE)
    await page.goto('/#/items?as=codex')

    const open = row(page, 'T-0001')
    await expect(open.locator('[data-unassigned]')).toHaveText('unassigned')
    await expect(page.locator('[data-claim-command]')).toHaveCount(0)
  })
})

test.describe('the kanban card', () => {
  test('marks the unowned card and carries the same command as the row', async ({ page }) => {
    await stub(page, LEADER_STATE)
    await page.goto('/#/kanban?as=human')

    await expect(card(page, 'T-0001').locator('[data-unassigned]')).toHaveText('unassigned')
    const control = card(page, 'T-0001').locator('[data-claim-command]')
    await expect(control).toHaveAttribute('data-claim-command', CLAIM('human', 'T-0001'))
    await expect(control).toHaveText(CLAIM('human', 'T-0001'))
    // An owned card is drawn exactly as it was: no mark, no control.
    await expect(card(page, 'T-0002').locator('[data-unassigned]')).toHaveCount(0)
    await expect(card(page, 'T-0002').locator('[data-claim-command]')).toHaveCount(0)
  })

  test('a participant who cannot write sees the mark and no control', async ({ page }) => {
    await stub(page, PARTICIPANT_STATE)
    await page.goto('/#/kanban?as=codex')
    await expect(card(page, 'T-0001').locator('[data-unassigned]')).toHaveText('unassigned')
    await expect(page.locator('[data-claim-command]')).toHaveCount(0)
  })
})

test.describe('#/items?unassigned=1', () => {
  test('filters to exactly the unowned rows', async ({ page }) => {
    await stub(page, LEADER_STATE)
    await page.goto('/#/items?unassigned=1')
    await expect(page.locator('.el-table__body tr').first()).toBeVisible()
    await expect.poll(() => unownedIds(page)).toEqual(['T-0001', 'T-0003'])
    await expect(page.locator('.el-table__body')).not.toContainText('T-0002')
    // The URL is the state, not a thing that was consumed on the way in.
    expect(new URL(page.url()).hash).toContain('unassigned=1')
  })

  test('survives a reload, because it is the URL that carries it', async ({ page }) => {
    await stub(page, LEADER_STATE)
    await page.goto('/#/items?unassigned=1')
    await expect.poll(() => unownedIds(page)).toEqual(['T-0001', 'T-0003'])

    await page.reload()
    await expect(page.locator('.el-table__body tr').first()).toBeVisible()
    await expect.poll(() => unownedIds(page)).toEqual(['T-0001', 'T-0003'])
  })

  test('checks the box that already exists, and clearing it writes the URL back', async ({ page }) => {
    // The app already has one URL-backed filter mechanism (`useQueryFilters`) and
    // this is that mechanism, not a second one: the control is an `el-checkbox` in
    // the existing `.aim-filterbar`, its state round-trips through `?unassigned=1`
    // the way `?onlyLate=1` does, and unchecking it removes the key again.
    await stub(page, LEADER_STATE)
    await page.goto('/#/items?unassigned=1')
    const box = page.locator('.aim-filterbar .el-checkbox').filter({ hasText: 'unassigned' })
    await expect(box.locator('.el-checkbox__input')).toHaveClass(/is-checked/)

    await box.click()
    await expect.poll(() => new URL(page.url()).hash).not.toContain('unassigned')
    await expect.poll(() => rowIds(page)).toEqual(['T-0001', 'T-0002', 'T-0003'])

    // And a link that names a different filter replaces it rather than adding to
    // it -- the same "adopt the URL whole" rule the other filters keep, which is
    // the defect `useQueryFilters` was written to end.
    await page.goto('/#/items?unassigned=1')
    await expect.poll(() => unownedIds(page)).toEqual(['T-0001', 'T-0003'])
    await page.goto('/#/items?owner=codex')
    await expect.poll(() => rowIds(page)).toEqual(['T-0002'])
  })

  test('an item with an owner is unaffected', async ({ page }) => {
    await stub(page, LEADER_STATE)
    await page.goto('/#/items')
    await expect(row(page, 'T-0002')).toContainText('codex')
    await expect(row(page, 'T-0002').locator('[data-unassigned]')).toHaveCount(0)

    await page.goto('/#/items?unassigned=1')
    await expect(page.locator('.el-table__body')).not.toContainText('Someone already took this one')
  })
})
