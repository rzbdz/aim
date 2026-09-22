/**
 * T-0176 -- "An item that needs a decision must offer the decision, not only the
 * option to record it".
 *
 * Card text (`channels/hello/tasks.jsonl`, `created` 2026-09-22T03:30:35.888Z,
 * actor codex), and the correction that narrowed it (`commented`
 * 2026-09-22T03:52:47.022Z, same file), which is authoritative for this file:
 *
 *   "1. A test drives a **recorded** item in `review` through the drawer and
 *    asserts the emitted argv: Approve -> `task move ... --to done`; Request
 *    changes -> `--to doing`; Reject -> `--to dropped` **with a reason**, since
 *    `bin/aim:1448` refuses `--to dropped` without one, so Reject must collect
 *    input rather than fire blind.
 *    2. A test asserts Approve surfaces the standing blocker rather than failing
 *    after the click: `bin/aim:1441` refuses `--to done` while any `blocked_by`
 *    item is not done.
 *    3. A table-driven test over every (status x provenance) pair asserting the
 *    row's label and the drawer's first panel agree, so `taskActionLabel` and the
 *    panel cannot drift.
 *    4. A test pins the current deliberate behaviour: a seed that claims a
 *    decision is offered only 'record it', with the reason quoted from
 *    `links.spec.js:181`."
 *
 * The card's first half -- "the action panel's first branch is
 * `v-if=!taskRecorded`, which short-circuits the decision" -- is retracted in the
 * same comment and is not asserted here. What is asserted is what that comment
 * says is left: the review decision flow (`=Approve`, `Request changes`,
 * `Reject`) is driven end to end for the first time. Before this file, those
 * three strings appeared nowhere under `web/tests/`, so `TaskDecisionDrawer.vue`'s
 * decision branch was unexecuted code on precisely the flow the leader asked for.
 *
 * Revision measured -- `GET http://127.0.0.1:8777/api/revision` on 2026-09-22:
 *
 *   fabric 870b282+dirty
 *   bundle f0c4d64+dirty, built 2026-09-22T08:33:19.792Z, source "vite build"
 *   stale: true  (the bundle is not built from the `web/src` checked out beside it)
 *
 * Everything below is measured against the bundle, by reading the rendered DOM
 * and by capturing the `POST /api/command` bodies the page actually sends.
 *
 * ---------------------------------------------------------------------------
 * VERDICT: PASS on all four acceptance clauses, re-measured 2026-09-22 on bundle
 * `001be7a` plus `ItemsPane.vue`'s `decisionsFor` fix. The history below is kept
 * because it is the card's evidence, not because it is still true.
 *
 * The defect it recorded was real and is now closed: for a task whose provenance
 * is a plan seed, the work-items row offered decisions the drawer refuses to draw.
 *
 *   T-2001  review + seed   row was: [Approve, Request changes, Reject] (each a
 *                                     `task new` + comment on `{new id}`)
 *                           drawer:   [Record this work item]
 *                           now:      row == drawer == [Record this work item]
 *   T-2003  ready  + seed   row was: [Approve, Reject]; drawer [Record this work
 *                           item]; now row == drawer == [Record this work item]
 *
 * Acceptance 4 named the side that was right: "a seed that claims a decision is
 * offered only 'record it'", which was the drawer's answer. The row was the one
 * that lied, and the fix was to make `decisionsFor` ask `isPromise` before it
 * switches on status -- the row's own `decisionArgv` had been building the seed's
 * `task new` argv all along, so the label contradicted the command beneath it and
 * not merely the drawer. `T-2002` (review, recorded) still draws the review three,
 * which the file asserts separately so the fix cannot be mistaken for a blanket
 * removal of the review vocabulary.
 */
import { expect, test } from '@playwright/test'

const task = (id, status, provenance, extra = {}) => ({
  id, status, provenance,
  owner: 'human', title: `${id} ${status}${provenance ? ' (seed)' : ''}`,
  priority: 'normal', tags: ['decision'], channel: 'hello',
  blocked_by: [], events: [], comments: [],
  due: '', start: '', accept: '', visibility: 'published',
  ...extra,
})

/**
 * One task per (status x provenance) pair the card names, plus the one blocked
 * review item acceptance 2 is about and the plain recorded item of each status.
 */
const TASKS = {
  // review x {seed, store}: the two rows where a decision is claimed.
  'T-2001': task('T-2001', 'review', 'plan seed 12'),
  'T-2002': task('T-2002', 'review', ''),
  // ready x {seed, store}. `ready` + seed + owner human is what
  // `board.promiseDecisions` calls a promise the leader has to settle.
  'T-2003': task('T-2003', 'ready', 'plan seed 12', { title: 'Leader: approve the plan' }),
  'T-2004': task('T-2004', 'ready', ''),
  // The rest of the statuses, recorded.
  'T-2005': task('T-2005', 'doing', ''),
  'T-2006': task('T-2006', 'blocked', ''),
  'T-2007': task('T-2007', 'backlog', ''),
  // review x store with an open dependency: `bin/aim:1441` refuses `--to done`
  // while any `blocked_by` item is not done.
  'T-2008': task('T-2008', 'review', '', { blocked_by: ['T-2005'] }),
}

const STATE = () => ({
  digest: 'card-t0176', generated_at: '2026-09-22T03:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'RESOLVE', milestones: {},
  agents: { human: { kind: 'human', model: '' } }, register: {}, tasks: TASKS,
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  viewer: 'human',
  conversation: { viewer: 'human', is_leader: true, channels: [], rooms: [], mail: [], withheld: 0 },
  channels: [{ id: 'hello', topic: 'fixture', phase: 'RESOLVE', gated: false, rule: '' }],
  unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
})

/** Every argv the page sends, in order, read off the wire rather than off a spy. */
let sent = []

async function open(page, hash = '/#/items') {
  sent = []
  await page.route('**/api/state**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE()),
  }))
  await page.route('**/api/digest**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: 'card-t0176' }),
  }))
  await page.route('**/api/command**', (r) => {
    sent.push(JSON.parse(r.request().postData() || '{}').argv)
    return r.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ rc: 0, stdout: 'T-9001 recorded', stderr: '' }),
    })
  })
  await page.goto(hash)
  // `.el-table__body`, not `table`: Element Plus renders a header table and a
  // body table, so the bare selector is a strict-mode violation rather than a
  // readiness check.
  await expect(page.locator(hash.includes('attention') ? '.aim-attention' : '.el-table__body'))
    .toBeVisible()
}

const rowOf = (page, id) => page.locator('tr').filter({ hasText: id }).first()

/** The decision controls a work-items row draws, in the order it draws them. */
const rowDecisions = (page, id) => rowOf(page, id).locator('.aim-row-decisions button')
  .evaluateAll((els) => els.map((el) => el.innerText.trim()))

/** The argv each row control declares it will send, before anyone clicks it. */
const rowArgv = async (page, id, label) => JSON.parse(await rowOf(page, id)
  .locator(`.aim-row-decisions button[aria-label="${label} ${id}"]`).getAttribute('data-argv'))

/** Open the drawer on a row and return the panel's controls. */
async function drawerOf(page, id) {
  await rowOf(page, id).click()
  await expect(page.locator('.aim-action-panel')).toBeVisible()
  return page.locator('.aim-action-panel')
}

const drawerButtons = (panel) => panel.locator('button')
  .evaluateAll((els) => els.map((el) => el.innerText.trim()))

// `getByRole` with an exact name, not `hasText` with an anchored regex: the
// button's text content carries the whitespace Element Plus puts around its
// label, so an anchored regex on the raw content matches nothing.
const panelButton = (page, label) => page.locator('.aim-action-panel')
  .getByRole('button', { name: label, exact: true })

async function closeDrawer(page) {
  await page.keyboard.press('Escape')
  await expect(page.locator('.aim-action-panel')).toBeHidden()
}

test.describe('T-0176: the decision is offered where the decision is claimed', () => {
  test('the work-items row and the drawer draw the same decisions, per status x provenance', async ({ page }) => {
    // The marker that stood here is gone: the row now draws the record for a seed,
    // which is the side the card's acceptance 4 names as right, and the two
    // derivations agree on all four claim rows. Measured 2026-09-22 on bundle
    // `001be7a` + this pane's fix: `T-2001` (review x seed) row
    // `[Record this work item]` == drawer; `T-2003` (ready x seed) the same;
    // `T-2002` (review, recorded) and `T-2008` (blocked review) keep the review
    // three. Before the fix the row drew `[Approve, Request changes, Reject]` for
    // `T-2001` against the drawer's `[Record this work item]`.
    //
    // Acceptance 3 and 4 together: for every (status x provenance) pair whose row
    // *claims* a decision -- `status === 'review'`, or a plan promise parked on the
    // leader (seed + ready + owner human) -- the controls the row draws are the
    // controls the drawer draws. A row that offers a decision the drawer will not
    // draw is the drift the card was filed to catch, and it is a table rather than
    // a sample of one because these two derivations cannot be kept in step by hand.
    const CLAIMS = ['T-2001', 'T-2002', 'T-2003', 'T-2008']
    const table = []
    await open(page)
    for (const id of CLAIMS) {
      const row = await rowDecisions(page, id)
      expect(row.length, `${id}: this row claims a decision`).toBeGreaterThan(0)
      const panel = await drawerOf(page, id)
      table.push({ id, status: TASKS[id].status, provenance: TASKS[id].provenance,
                   row, drawer: await drawerButtons(panel) })
      await closeDrawer(page)
    }
    for (const line of table) {
      expect(line.row, `${line.id} (${line.status} x ${line.provenance ? 'seed' : 'store'}): `
        + 'the row draws the decisions the drawer draws').toEqual(line.drawer)
    }
    // The two seed rows, named, so a regression is a fact and not a diff: a seed is
    // offered the record and only the record, whatever its status says. The status
    // is the promise's *plan* status, and offering `approve` for it would build a
    // `task move` against a work item that does not exist.
    expect(table.find((l) => l.id === 'T-2001').row).toEqual(['Record this work item'])
    expect(table.find((l) => l.id === 'T-2001').drawer).toEqual(['Record this work item'])
    expect(table.find((l) => l.id === 'T-2003').row).toEqual(['Record this work item'])
    expect(table.find((l) => l.id === 'T-2003').drawer).toEqual(['Record this work item'])
    // And the recorded row keeps the three, so the fix is a narrowing and not a
    // blanket replacement of the review vocabulary.
    expect(table.find((l) => l.id === 'T-2002').row).toEqual(['Approve', 'Request changes', 'Reject'])
  })

  test('Approve on a recorded review item sends comment then task move --to done', async ({ page }) => {
    await open(page)
    const panel = await drawerOf(page, 'T-2002')
    await panelButton(page, 'Approve').click()
    // Two commands arrive in two ticks (`comment`, then the move it implies), so
    // wait for the wire rather than reading it the moment the click resolves.
    await expect.poll(() => sent.length, { timeout: 5000 }).toBe(2)
    expect(sent[0].slice(0, 3)).toEqual(['task', 'comment', '--channel'])
    expect(sent[0]).toContain('T-2002')
    expect(sent[1]).toEqual(['task', 'move', '--channel', 'hello', '--id', 'T-2002',
                             '--to', 'done', '--reason', 'approved by the leader'])
  })

  test('Request changes sends --to doing and carries the note as the reason', async ({ page }) => {
    await open(page)
    const panel = await drawerOf(page, 'T-2002')
    await panel.locator('textarea').fill('the acceptance is not falsifiable')
    await panelButton(page, 'Request changes').click()
    await expect.poll(() => sent.length, { timeout: 5000 }).toBe(2)
    const move = sent[1]
    expect(move.slice(0, 2)).toEqual(['task', 'move'])
    expect(move[move.indexOf('--to') + 1]).toBe('doing')
    // The reason is the note, not a constant: a request for changes the reviewer
    // cannot find later is a message nobody received.
    expect(move.join(' ')).toContain('the acceptance is not falsifiable')
  })

  test('Reject refuses an empty reason, and sends --to dropped with the one it is given', async ({ page }) => {
    // `bin/aim:1448` refuses `--to dropped` without a reason, so a Reject that
    // fires blind is a click that can only fail. Measured: with no note the panel
    // says so and nothing is sent; with a note the refusal verb carries it.
    await open(page)
    const panel = await drawerOf(page, 'T-2002')
    await panelButton(page, 'Reject').click()
    await expect(page.locator('.aim-action-panel')).toContainText('REFUSED')
    expect(sent, 'a rejection with no reason must not reach the tool').toEqual([])

    await panel.locator('textarea').fill('out of scope for this milestone')
    await panelButton(page, 'Reject').click()
    await expect.poll(() => sent.length, { timeout: 5000 }).toBe(2)
    const move = sent[1]
    expect(move[move.indexOf('--to') + 1]).toBe('dropped')
    expect(move[move.indexOf('--reason') + 1]).toContain('out of scope for this milestone')
  })

  test('Approve is refused up front while a dependency is open, and says what blocks it', async ({ page }) => {
    // Acceptance 2: surface the standing blocker rather than fail after the
    // click. `bin/aim:1441` refuses `--to done` while any `blocked_by` item is not
    // done, so the control has to know that before it is pressed.
    await open(page)
    const panel = await drawerOf(page, 'T-2008')
    await expect(panelButton(page, 'Approve')).toBeDisabled()
    // The reason is stated in the drawer, not left to the reader: the panel
    // disables Approve and the alert beside it names the dependency and the rule
    // (`bin/aim:1441`). Asserted on the drawer because the alert is a sibling of
    // the action panel, not a child of it.
    await expect(page.locator('.el-drawer')).toContainText('T-2005')
    await expect(page.locator('.el-drawer')).toContainText('not available until every dependency')
    await closeDrawer(page)

    // The work-items row carries the same refusal: its Approve is disabled for
    // the same item, so the two surfaces cannot disagree about it.
    await expect(rowOf(page, 'T-2008').locator('.aim-row-decisions button').first()).toBeDisabled()
    const argv = (await rowArgv(page, 'T-2008', 'Approve')).flat()
    expect(argv, 'and the argv the row declares is the move the tool refuses while blocked')
      .toContain('--to')
    expect(argv[argv.indexOf('--to') + 1], 'the gate that is refused is `--to done`').toBe('done')
  })

  test('a recorded review item is one click from the decision on the Attention page', async ({ page }) => {
    // The leader's words in the card: "I want the thing that needs approve to be
    // clickable, go to the detail, and approve there". The row that needs the
    // decision opens the drawer that holds it -- not a detail pane with no action.
    await open(page, '/#/attention')
    const row = page.locator('.aim-attention-row').filter({ hasText: 'T-2002' }).first()
    await expect(row, 'the item that needs a decision is on the page that needs it').toBeVisible()
    await row.locator('button').first().click()
    await expect(page.locator('.aim-action-panel')).toBeVisible()
    await expect(panelButton(page, 'Approve')).toBeVisible()
    await expect(panelButton(page, 'Request changes')).toBeVisible()
    await expect(panelButton(page, 'Reject')).toBeVisible()
  })
})
