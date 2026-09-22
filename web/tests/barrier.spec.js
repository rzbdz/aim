import { expect, test } from '@playwright/test'

/**
 * T-0220: the barrier's tab strip cannot change the channel.
 *
 * The refusal ledger is the subject of this page -- README §2 says the design
 * exists to record the moment an agent wanted something it was not allowed -- and
 * 13 of the recorded refusals were unreachable by clicking. Having navigated the
 * way the page invites, the reader saw "0 of 13 record(s)" over an empty table.
 *
 * Two mechanisms, one symptom:
 *
 *  * the strip was `v-model="shown"` where `shown` is a computed, so the tab's
 *    `update:modelValue` was assigned to a readonly ref, dropped, and (being a
 *    production build) warned about nowhere. `el-tabs` moved its own highlight
 *    and switched the pane on screen while `filters.channel` and the URL stayed
 *    put;
 *  * the table's filters were computed against `current` -- the channel named by
 *    the URL -- while the table itself rendered inside `v-for="ch in channels"`,
 *    so the header's numerator and denominator came from different channels.
 *
 * The fixture gives each channel a different number of refusals, so a numerator
 * borrowed from the wrong channel cannot coincide with the right one.
 */

const CHANNEL = (id, phase, refusals, extra = {}) => ({
  id, phase, topic: `${id} topic`, leader: 'human',
  participants: ['codex', 'claude-session1'], round: 0,
  sealed: [], concessions: 0, tasks_recorded: 0, tasks_unknown_events: 0,
  chain: { 'log.jsonl': { state: 'OK', records: 2, why: 'fixture' } },
  refusals,
  history: [{ at: '2026-09-22T00:00:00.000Z', phase, by: 'human', note: '' }],
  ...extra,
})

const REFUSAL = (agent, action, cls = 'barrier', phase = 'SEALED_DIVERGENT') => ({
  ts: '2026-09-22T00:00:30.000Z', agent, action, class: cls, phase,
  reason: `${agent} may not ${action} in ${phase}`,
})

const STATE = {
  digest: 'barrier-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'done'],
  terminal: ['done'],
  phase: 'SEALED_DIVERGENT',
  milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' } },
  register: {},
  tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [
    CHANNEL('alpha', 'SEALED_DIVERGENT', [REFUSAL('codex', 'read_others')]),
    CHANNEL('hello', 'COMMIT', [
      REFUSAL('codex', 'read_others'),
      REFUSAL('codex', 'channel_say', 'barrier', 'SEALED_DIVERGENT'),
      REFUSAL('claude-session1', 'advance'),
      REFUSAL('human', 'advance', 'form', 'SEALED_DIVERGENT'),
    ]),
    CHANNEL('scratch', 'SYNTHESIS', []),
  ],
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

/**
 * The refusal table's rows, and only its rows.
 *
 * The pane holds three tables, so a bare `.el-table__body tr` under the active
 * pane also counts the chain and the seals -- and a count that includes two facts
 * nobody is asserting is a count that cannot fail for the reason it claims to.
 * The table is addressed by its own class for that reason.
 */
const rows = (page) => page.locator('.el-tab-pane:visible .aim-refusal-table .el-table__body tr')
/**
 * The refusal card's header, in the pane the reader is looking at.
 *
 * `el-tabs` keeps every pane in the DOM and hides the inactive ones, so a bare
 * selector finds one header per channel -- and a `toContainText` over three
 * elements is a strict-mode error, not an assertion. Scoping to the visible pane
 * is what makes this a statement about the channel on screen.
 */
const refusalHeader = (page) =>
  page.locator('.el-tab-pane:visible .el-card__header').filter({ hasText: 'refusals' })

test('clicking a channel tab changes the channel, the URL and the ledger', async ({ page }) => {
  await page.goto('/#/barrier')
  // The fallback is the selection, so a reader who arrives with no `?channel=`
  // is reading `alpha` and the URL says so.
  await expect(page).toHaveURL(/channel=alpha/)
  await expect(refusalHeader(page)).toContainText('1 of 1 record(s)')

  await page.locator('.el-tabs__item').filter({ hasText: '#hello' }).click()

  // The URL is the source of truth, so the click has to reach it. This is the
  // assertion the defect failed: the pane switched on screen and the address bar
  // did not move.
  await expect(page).toHaveURL(/channel=hello/)
  // And the count is the count of the channel the table is drawn in: 4 refusals,
  // not alpha's 1.
  await expect(refusalHeader(page)).toContainText('4 of 4 record(s)')
  await expect(rows(page)).toHaveCount(4)

  // Back again: the strip is a two-way control, not a one-shot.
  await page.locator('.el-tabs__item').filter({ hasText: '#scratch' }).click()
  await expect(page).toHaveURL(/channel=scratch/)
  await expect(refusalHeader(page)).toContainText('0 of 0 record(s)')
})

test('the refusal filters narrow the ledger of the channel the table is in', async ({ page }) => {
  // The other half of the same defect: the filters were computed from `current`
  // (the URL's channel) while the table rendered from the pane's. With one
  // channel holding a `form` refusal and another holding none, a filter borrowed
  // from the wrong channel empties a table that should have rows.
  await page.goto('/#/barrier?channel=hello')
  await expect(rows(page)).toHaveCount(4)

  // The class filter, addressed by its own placeholder rather than by position:
  // a test that counts selects breaks the day someone adds a filter. `class` is
  // also the only one of the three whose option set is fixed, so the option it
  // is asked for is one the fixture is guaranteed to be able to match.
  await page.locator('.el-tab-pane:visible .el-select').filter({ hasText: 'class' }).first().click()
  await page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
    .filter({ hasText: 'form' }).click()
  await expect.poll(() => rows(page).count()).toBe(1)
  await expect(rows(page).first()).toContainText('human')

  // A reader who narrows and then moves to a channel with nothing to match: the
  // header must count *that* channel's rows, not the previous channel's.
  await page.locator('.el-tabs__item').filter({ hasText: '#alpha' }).click()
  await expect(page).toHaveURL(/channel=alpha/)
  await expect(refusalHeader(page)).toContainText('0 of 1 record(s)')
})
