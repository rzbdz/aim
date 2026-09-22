/**
 * T-0163 -- "Task drawer must preserve the full seed and must not carry state
 * between tasks".
 *
 * Card text (`channels/hello/tasks.jsonl`, `created` 2026-09-22T03:00:36.606Z,
 * actor codex), verbatim acceptance:
 *
 *   "Recording a plan seed preserves title, owner, status, priority, milestone,
 *    acceptance, start, due, estimate, tags and blocked-by when the CLI supports
 *    them; the drawer resolves the selected task by id from the current board so
 *    live updates replace a stale object; decision note and error/result state
 *    reset when the selected task changes or the drawer closes; tests create a
 *    seed with tags/estimate/dependencies, record it from the drawer, reload and
 *    assert every field survives; a second test updates the board while the
 *    drawer is open and asserts the drawer shows the current task state".
 *
 * Revision measured -- `GET http://127.0.0.1:8777/api/revision` first, read only,
 * 2026-09-22T08:50Z:
 *
 *   fabric  fac2a0c+dirty
 *   bundle  870b282+dirty, built 2026-09-22T08:40:07.787Z, source "vite build"
 *   stale:  true   (the served bundle is not built from the `web/src` beside it,
 *                   so the verdict below is about the bundle a reader loads)
 *
 * The fabric revision moved while this file was being written (another session in
 * this shared checkout committed; it read `1277f7e+dirty` at 08:53Z) and the
 * bundle revision did not: `bundle 870b282+dirty`, `stale: true` at both reads.
 * The bundle is what a reader loads, so that is the revision the verdict is about.
 *
 * The suite's `webServer` is `reuseExistingServer: !CI`, so this file does not
 * start a board: it intercepts `/api/state`, `/api/digest` and `/api/command`
 * with `page.route` fixtures and reads the leader's board on 8777 only through
 * `baseURL`. Nothing is written back to it.
 *
 * ---------------------------------------------------------------------------
 * What is measured
 *
 * 1. `TaskDecisionDrawer.vue:recordTask()` builds the `task new` argv for a plan
 *    seed. `bin/aim task new` (bin/aim:3318-3331) accepts `--estimate`, `--tag`
 *    (repeatable) and `--blocked-by`; the builder sends none of the three, so a
 *    seed carrying 5 points, two tags and a dependency is recorded without them.
 *    The check is not "the argv looks right": the argv the drawer actually POSTs
 *    is replayed against the real `bin/aim` in a throwaway `AIM_ROOT`, and the
 *    `created` event that comes back must carry every field. The tool is the
 *    oracle, not this file.
 *
 * 2. `App.vue:drawerTask` resolves the open id out of `board.tasks` on every
 *    render. The check drives that end to end: the drawer is opened on a task and
 *    the served payload is moved under it (new digest, new title), which is what
 *    the 2.5s `checkDigest` poll (main.js:267) does when a peer writes. A drawer
 *    holding the object it was opened with fails here.
 *
 * 3. `decisionNote`, `error` and `result` are refs on the drawer component and
 *    `el-drawer` is mounted without `destroy-on-close`, so nothing in the
 *    component resets them. Switching the selected task -- the open-blocker link
 *    in the panel does that without closing the drawer -- and closing/reopening
 *    are both supposed to clear them.
 *
 * VERDICT: FAIL on acceptance 1 and 3, PASS on 2. Both failing tests carry
 * Playwright's `test.fail()` with the measurement written beside them, so the run
 * is green and the defect is on the record rather than hidden.
 */
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const REPO = fileURLToPath(new URL('../../', import.meta.url))
const AIM = path.join(REPO, 'bin', 'aim')

/* --------------------------------------------------------------- the fixture */

/** The seed: every field the card names, and a dependency that exists. */
const SEED = {
  id: 'T-0009', channel: 'hello', owner: 'human', status: 'ready', priority: 'high',
  title: 'Leader: approve the plan; the seed the drawer records',
  milestone: 'M0', accept: 'the recorded work item carries every field the plan states',
  start: '2026-09-20', due: '2026-09-25', estimate: 5, tags: ['alpha', 'beta'],
  blocked_by: ['T-0001'], visibility: 'published', events: [], comments: [],
  provenance: 'seed only (not yet in the store)',
}

/** The dependency the seed names. Done, so it never blocks the drawer's buttons. */
const BLOCKER = {
  id: 'T-0001', channel: 'hello', owner: 'worker', status: 'done', priority: 'normal',
  title: 'the dependency the plan names', milestone: 'M0', accept: '', start: '', due: '',
  estimate: 2, tags: [], blocked_by: [], visibility: 'published', events: [], comments: [],
  provenance: '',
}

/** A recorded item in review, with one *open* blocker: the task-change path. */
const REVIEW = {
  id: 'T-0011', channel: 'hello', owner: 'worker', status: 'review', priority: 'normal',
  title: 'a review the leader has to settle', milestone: '', accept: 'the review has a sentence a reviewer can falsify',
  start: '', due: '', estimate: 1, tags: [], blocked_by: ['T-0012'], visibility: 'published',
  events: [{ ts: '2026-09-22T02:00:00.000Z', actor: 'worker', event: 'created' }], comments: [],
  provenance: '',
}

/** Its open blocker, and the drawer's way from one task to the next. */
const OPEN_BLOCKER = {
  id: 'T-0012', channel: 'hello', owner: 'worker', status: 'doing', priority: 'low',
  title: 'the blocker still open', milestone: '', accept: '', start: '', due: '',
  estimate: 1, tags: [], blocked_by: [], visibility: 'published', events: [], comments: [],
  provenance: '',
}

const TASKS = { [SEED.id]: SEED, [BLOCKER.id]: BLOCKER, [REVIEW.id]: REVIEW,
                [OPEN_BLOCKER.id]: OPEN_BLOCKER }

const state = (tasks, digest) => ({
  digest, generated_at: '2026-09-22T08:50:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'RESOLVE', milestones: {},
  agents: { human: { kind: 'human', model: '' }, worker: { kind: 'codex', model: '' } },
  register: {}, tasks, series: [], reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  viewer: 'human', viewer_kind: 'human',
  channels: [{ id: 'hello', topic: 'fixture', phase: 'RESOLVE', gated: false, rule: '' }],
  conversation: { viewer: 'human', is_leader: true, channels: [], rooms: [], mail: [], withheld: 0 },
  unacked: [], drift: [], withheld_tasks: 0, unplaced_events: 0, write: { enabled: true, as: 'human' },
})

/* ------------------------------------------------------------ the page's end */

/** Every `POST /api/command` argv, read off the wire. */
let sent = []
/** What `/api/command` answers next: 'ok' or a refusal. */
let commandMode = 'ok'

async function open(page) {
  sent = []
  commandMode = 'ok'
  await page.route('**/api/state**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify(state(TASKS, 'card-t0163-a')),
  }))
  await page.route('**/api/digest**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: 'card-t0163-a' }),
  }))
  await page.route('**/api/command**', (r) => {
    sent.push(JSON.parse(r.request().postData() || '{}').argv)
    return r.fulfill(commandMode === 'ok'
      ? { contentType: 'application/json', body: JSON.stringify({ rc: 0, stdout: 'T-0099 created' }) }
      : { contentType: 'application/json',
          body: JSON.stringify({ rc: 2, stdout: '', stderr: 'REFUSED: the fixture refused this action' }) })
  })
  await page.goto('/#/items')
  await expect(page.locator('.el-table__body')).toBeVisible()
}

const rowOf = (page, id) => page.locator('tr').filter({ hasText: id }).first()

/** Open the drawer on a row and return its action panel. */
async function drawerOf(page, id) {
  // The row's `@row-click` opens the drawer; the action cell's buttons stop the
  // event, so the click is aimed at the id cell, which carries no handler of
  // its own.
  await rowOf(page, id).locator('td').first().click()
  await expect(page.locator('.aim-action-panel')).toBeVisible()
  return page.locator('.aim-action-panel')
}

const panelButton = (page, label) => page.locator('.aim-action-panel')
  .getByRole('button', { name: label, exact: true })

async function closeDrawer(page) {
  await page.keyboard.press('Escape')
  await expect(page.locator('.aim-action-panel')).toBeHidden()
}

/** Click `Record this work item` and hand back the argv the drawer sent. */
async function recordFromDrawer(page, id) {
  await drawerOf(page, id)
  await panelButton(page, 'Record this work item').click()
  await expect.poll(() => sent.length).toBeGreaterThan(0)
  return sent[0]
}

/* ---------------------------------------------------- the tool, as the oracle */

/** Run the real `bin/aim` in a throwaway fabric and return the `created` event. */
function recordThroughCli(argv, title) {
  const root = mkdtempSync(path.join(tmpdir(), 'card-t0163-'))
  const env = { ...process.env, AIM_ROOT: root }
  const aim = (...args) => execFileSync('python3', [AIM, ...args.map(String)],
                                        { env, encoding: 'utf8' })
  try {
    aim('init')
    aim('register', '--as', 'human', '--kind', 'human')
    aim('register', '--as', 'worker', '--kind', 'codex')
    aim('new-channel', '--id', 'hello', '--topic', 'card t0163', '--participants',
        'human,worker', '--leader', 'human')
    // The dependency the seed names, so `task new --blocked-by` has something to
    // point at. It is the first id the allocator hands out, T-0001.
    aim('task', 'new', '--as', 'human', '--channel', 'hello',
        '--title', 'the dependency the plan names', '--owner', 'worker')
    aim('task', 'new', '--as', 'human', ...argv.slice(2))
    const log = path.join(root, 'channels', 'hello', 'tasks.jsonl')
    const rows = readFileSync(log, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
    const created = rows.filter((r) => r.event === 'created' && r.title === title)
    return created[created.length - 1] || { missing: 'no created event with this title', rows }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

/** `['--a','1','--b','2','--b','3']` -> `{ '--a': '1', '--b': ['2','3'] }`. */
function flagsOf(argv) {
  const out = {}
  for (let i = 0; i < argv.length; i += 1) {
    const flag = argv[i]
    if (!flag.startsWith('--')) continue
    const value = argv[i + 1]
    out[flag] = flag in out ? [].concat(out[flag], value) : value
    i += 1
  }
  return out
}

/* ------------------------------------------------------------ the assertions */

test.describe('T-0163: the drawer records the whole seed and carries nothing over', () => {
  test('recording a seed carries title, owner, status, priority, milestone, accept, dates, estimate, tags and blocked-by', async ({ page }) => {
    // Measured 2026-09-22 against bundle 870b282+dirty (stale true): the drawer's
    // `task new` argv is
    //   ["task","new","--channel","hello","--title","…","--owner","human",
    //    "--status","ready","--priority","high","--milestone","M0","--accept","…",
    //    "--due","2026-09-25","--start","2026-09-20"]
    // -- no --estimate, no --tag, no --blocked-by -- so the recorded work item
    // loses the 5 points, both tags and its dependency. Recorded as an expected
    // failure rather than by weakening the assertion.
    test.fail(true,
      'T-0163 acceptance 1 FAIL (bundle 870b282+dirty, /api/revision stale true): '
      + 'TaskDecisionDrawer.vue:recordTask() sends title/owner/status/priority/milestone/'
      + 'accept/due/start and drops --estimate, --tag and --blocked-by, which '
      + '`bin/aim task new` accepts (bin/aim:3318-3331). Measured: the argv the drawer '
      + 'POSTed, replayed against the real tool in a throwaway AIM_ROOT, creates a work '
      + 'item whose estimate_pts is 0, tags [] and blocked_by [], where the plan seed '
      + 'states 5, [alpha, beta] and [T-0001].')
    await open(page)
    const argv = await recordFromDrawer(page, SEED.id)

    // 1. What the drawer sent, field by field, so the failure names each one.
    const wanted = {
      '--title': SEED.title, '--owner': 'human', '--status': 'ready',
      '--priority': 'high', '--milestone': 'M0', '--accept': SEED.accept,
      '--start': '2026-09-20', '--due': '2026-09-25', '--estimate': '5',
      '--tag': ['alpha', 'beta'], '--blocked-by': 'T-0001',
    }
    const flags = flagsOf(argv)
    const missing = Object.entries(wanted)
      .filter(([flag, want]) => JSON.stringify(flags[flag]) !== JSON.stringify(want))
      .map(([flag, want]) => `${flag}: the plan says ${JSON.stringify(want)}, the drawer sent ${JSON.stringify(flags[flag])}`)

    // 2. The same argv, run through the real tool, so "preserves" is measured
    //    against `bin/aim`'s parser rather than against this file's opinion.
    const created = recordThroughCli(argv, SEED.title)
    const survived = {
      title: created.title, owner: created.owner, status: created.status,
      priority: created.priority, milestone: created.milestone, accept: created.accept,
      start: created.start, due: created.due, estimate_pts: created.estimate_pts,
      tags: created.tags, blocked_by: created.blocked_by,
    }
    expect({ missing, survived }).toEqual({
      missing: [],
      survived: {
        title: SEED.title, owner: 'human', status: 'ready', priority: 'high',
        milestone: 'M0', accept: SEED.accept, start: '2026-09-20', due: '2026-09-25',
        estimate_pts: 5, tags: ['alpha', 'beta'], blocked_by: ['T-0001'],
      },
    })
  })

  test('the open drawer shows the board as it is now, not the object it was opened with', async ({ page }) => {
    await open(page)
    let moved = false
    // The payload moves under the drawer the way a peer's write moves it: a new
    // digest, then a board that differs. `checkDigest` polls every 2.5s.
    await page.route('**/api/digest**', (r) => r.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ digest: moved ? 'card-t0163-b' : 'card-t0163-a' }),
    }))
    await page.route('**/api/state**', (r) => r.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(state(
        moved ? { ...TASKS, [BLOCKER.id]: { ...BLOCKER, title: 'the dependency, renamed by a peer',
                                            status: 'review' } } : TASKS,
        moved ? 'card-t0163-b' : 'card-t0163-a')),
    }))
    await drawerOf(page, BLOCKER.id)
    await expect(page.locator('.aim-drawer-head')).toContainText(BLOCKER.title)
    moved = true
    await expect(page.locator('.aim-drawer-head h3')).toHaveText('the dependency, renamed by a peer',
                                                                { timeout: 15_000 })
    await expect(page.locator('.aim-drawer-head .el-tag').first()).toHaveText('review')
    // Nothing was written to change what the reader is looking at.
    expect(sent).toEqual([])
  })

  test('the note and the error/result state do not survive a task change or a close', async ({ page }) => {
    // Measured 2026-09-22 against bundle 870b282+dirty (stale true): after the
    // fixture accepts one action and refuses the next, the panel still draws the
    // success alert and the refusal after the selected task changed (the
    // open-blocker link moves the drawer to T-0012 without closing it), and the
    // decision note typed for T-0011 is still in the textarea after the drawer
    // was closed and reopened on the same row. `el-drawer` is mounted without
    // `destroy-on-close` and nothing in `TaskDecisionDrawer.vue` resets the three
    // refs when `task` changes.
    test.fail(true,
      'T-0163 acceptance 3 FAIL (bundle 870b282+dirty, /api/revision stale true): '
      + '`decisionNote`, `error` and `result` are component refs with no watcher on '
      + '`props.task`, and `el-drawer` has no `destroy-on-close`, so the note typed for '
      + 'T-0011 and the alerts of its last action survive both a task change and a close.')
    await open(page)
    const panel = await drawerOf(page, REVIEW.id)

    // A success first, so the `result` alert exists and the note is the one the
    // reader typed last rather than the one `decide()` clears after a success.
    commandMode = 'ok'
    await panel.locator('textarea').fill('first pass')
    await panelButton(page, 'Request changes').click()
    await expect(page.locator('.aim-action-panel .el-alert--success')).toBeVisible()

    commandMode = 'fail'
    await panel.locator('textarea').fill('a note that must not follow the reader')
    await panelButton(page, 'Reject').click()
    await expect(page.locator('.aim-action-panel .el-alert--error')).toBeVisible()

    // Closing and reopening the same row: the note is not the reader's to keep.
    await closeDrawer(page)
    await drawerOf(page, REVIEW.id)
    expect.soft(await panel.locator('textarea').inputValue(),
                'the decision note after the drawer was closed and reopened').toBe('')

    // Changing the selected task without closing: the open-blocker link.
    // The blocker alert is drawn above the action panel, inside the drawer body.
    await page.locator('.el-drawer .aim-blocker-link').first().click()
    await expect(page.locator('.aim-drawer-head h3')).toHaveText(OPEN_BLOCKER.title)
    expect.soft(await page.locator('.aim-action-panel .el-alert--error').count(),
                'refusal alerts after the selected task changed').toBe(0)
    expect.soft(await page.locator('.aim-action-panel .el-alert--success').count(),
                'result alerts after the selected task changed').toBe(0)
  })
})
