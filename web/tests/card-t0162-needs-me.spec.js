/**
 * T-0162 -- "Define needs-me and receipts-owed from recipient state, not from the
 * presence of a receipt chip".
 *
 * Card text (`channels/hello/tasks.jsonl`, `created` 2026-09-22T03:00:32.223Z,
 * actor codex), verbatim acceptance:
 *
 *   "For each viewer, needs-me includes only incoming direct messages addressed to
 *    that viewer that require an acknowledgement and are not acked, plus rooms with
 *    unread state for that viewer; it excludes messages the viewer sent and messages
 *    addressed to another agent; receipts-owed uses the same derived rule as the
 *    Chat filter; each thread shows a count/reason for why it needs the viewer;
 *    tests cover human, codex and claude-session1 viewers with fixtures containing
 *    incoming unacked, outgoing unacked and already-acked mail; clicking the
 *    Attention receipts signal lands on the same filtered set"
 *
 * Revision measured before writing this file -- `GET /api/revision` on
 * http://127.0.0.1:8777, 2026-09-22T08:32:46Z through 2026-09-22T08:39:13Z:
 *
 *   08:32:46Z  fabric 830dd79+dirty  bundle 830dd79+dirty built 08:31:54.776Z  stale true
 *   08:35Z     fabric 6bbbc51+dirty  bundle f0c4d64+dirty built 08:33:19.792Z  stale true
 *   2026-09-22T08:39:13Z  fabric 870b282+dirty  bundle f0c4d64+dirty built 2026-09-22T08:33:19.792Z  stale true
 *
 * `stale` was true at every read, and it was also false in between (08:31Z): another
 * session in this shared checkout edits `web/src/panes/ChatPane.vue` and rebuilds
 * `web/dist` under it, and HEAD moved from 830dd79 to 6bbbc51 while this file was
 * written. So the verdict below is about the bundle a reader actually loads; the
 * revision lines are timestamps, not constants.
 *
 * Provenance: this path already held an uncommitted draft from another hand
 * (17,178 bytes, md5 286a2cc793792d58eb2dc80adaac846d at 16:27:01+0800, re-read at
 * 16:32 as eb8c42d87d760a40cbedbc9725398cc1 -- it was still being rewritten while
 * this file was authored; overwritten again at 16:36:44+0800 -- 22,494 bytes, md5
 * 402df9583a4ff3ee5925d5d6c7eb9005, kept at /tmp/card-t0162-peer-draft-1636.spec.js --
 * while this file was being run). Those drafts are replaced here, not merged: the
 * leader's write set names this path, and two hands on one path with no lock is the
 * collision the workspace guard (T-0110) exists to catch. Nothing else was written.
 *
 * -----------------------------------------------------------------------------
 * What is measured, and why the fixture looks like this
 *
 * The card names three predicates, and they have to answer differently on the
 * fixture or an assertion can pass by coincidence. For viewer V:
 *
 *   chip     -- "the thread contains a message carrying the `receipt demanded`
 *               chip anywhere": `ack_required && state !== 'acked'`, whoever the
 *               message is addressed to and whoever wrote it.
 *   shipped  -- what `ChatPane.vue` answers today (`waitingOnViewer`):
 *               `to === V && state !== 'acked'`. It gets the addressee right and
 *               never asks `ack_required`, so an incoming message that demands
 *               nothing still counts while it is unanswered.
 *   card     -- `to === V && ack_required && state !== 'acked'`, plus a room whose
 *               `unread` map names V.
 *
 * The mailbox holds one of each kind the card names -- incoming unacked, outgoing
 * unacked, already acked -- plus, for *each* of the three viewers, one incoming
 * message that demands no receipt (`d6`, `d7`, `d8`). That last row is the one the
 * `shipped` rule cannot tell from a real demand, and it is repeated per viewer so
 * no viewer's case rides on another viewer's row:
 *
 *   d1  codex -> human            ack, unread      the demand human owes
 *   d2  human -> codex            ack, unread      the demand codex owes
 *   d3  codex -> claude-session1  ack, unread      the demand claude-session1 owes
 *   d4  codex -> human            ack, acked       answered
 *   d5  human -> codex            ack, acked       answered
 *   d6  claude-session1 -> human  no ack, delivered   a receipt human owes nobody
 *   d7  claude-session1 -> codex  no ack, delivered   a receipt codex owes nobody
 *   d8  human -> claude-session1  no ack, delivered   a receipt claude owes nobody
 *
 * and a room `#hello / #r1` with `unread: { human: 2 }` only.
 *
 * Channels are deliberately absent: the card's clause names direct messages and
 * rooms, and channel matching is T-0172's card. With `conversation.channels` empty
 * a channel cannot enter or leave this set, so the assertion is about the clause
 * the card actually states.
 *
 * The `unacked` list in the fixture is the shape the wire ships: `fabric.py:108`
 * appends every message with `ack_required && !acked_at` with no recipient filter,
 * and `api.py:135` publishes it verbatim. Measured live at 08:32Z: 50 rows for
 * `?as=human`, 50 for `?as=codex`, 50 for `?as=claude-session1` -- the same list,
 * while `conversation.withheld` differed (0 / 29 / 62). The fabric-wide fixture is
 * therefore not a hypothesis; it is the payload that answers 8777.
 */
import { expect, test } from '@playwright/test'

/* ------------------------------------------------------------------ mailbox */

/** A timestamp at minute `mm` of a fixed hour, so thread order is mail order. */
const at = (mm) => `2026-09-22T02:${String(mm).padStart(2, '0')}:00.000Z`

/**
 * A direct message, in the shape `/api/state` ships in `conversation.mail`.
 *
 * `shape` is the one field the wire does *not* carry and `board.conversationRows`
 * adds (`stores/board.js:435`, alongside `scope`, `channel` and `room`). It is here
 * because two readers test it: the receipts tile asks `row.shape === 'direct'`
 * before it counts a row, and `threadKey` answers by shape (`ch:` / `room:` /
 * `dm:`). Without it this fixture's mail is not direct mail to either of them --
 * measured before it was added, one clause failed on `their own thread is drawn`
 * with a row that had not been drawn at all.
 */
const dm = (id, from, to, state, ackRequired, ts) => ({
  msg_id: id, from, to, ts,
  subject: `subject ${id}`, body: `body ${id}`, bytes: 42,
  ack_required: ackRequired,
  acked_at: state === 'acked' ? ts : '', claimed_at: '', state,
  shape: 'direct', scope: [from, to].sort().join(' ⇄ '),
})

/**
 * A message that demands nothing back: a receipt, which is what d6/d7/d8 are.
 *
 * `shape`/`scope` are here for the same reason as on `dm`: `threadKey` and the
 * receipts tile read them. `ts` is a parameter because `conversationRows` sorts on
 * it (`stores/board.js:443`); every one of these rows is newer than every `dm` row
 * above, and the sort is stable, so before this they kept mail order by accident
 * rather than by the field the payload's own ordering rule reads.
 */
const receipt = (id, from, to, ts) => ({
  msg_id: id, from, to, ts,
  subject: `RECEIPT for ${id}`, body: `${from} received it from ${to}.\n`,
  bytes: 0, ack_required: false, acked_at: '', claimed_at: '', state: 'delivered',
  shape: 'direct', scope: [from, to].sort().join(' ⇄ '),
})

const DEMAND_ON_HUMAN = dm('d1', 'codex', 'human', 'unread', true, at(1))
const DEMAND_ON_CODEX = dm('d2', 'human', 'codex', 'unread', true, at(2))
const DEMAND_ON_CLAUDE = dm('d3', 'codex', 'claude-session1', 'unread', true, at(3))
const ANSWERED_ON_HUMAN = dm('d4', 'codex', 'human', 'acked', true, at(4))
const ANSWERED_ON_CODEX = dm('d5', 'human', 'codex', 'acked', true, at(5))
const RECEIPT_FOR_HUMAN = receipt('d6', 'claude-session1', 'human', at(6))
const RECEIPT_FOR_CODEX = receipt('d7', 'claude-session1', 'codex', at(7))
const RECEIPT_FOR_CLAUDE = receipt('d8', 'human', 'claude-session1', at(8))

const MAIL = [DEMAND_ON_HUMAN, DEMAND_ON_CODEX, DEMAND_ON_CLAUDE, ANSWERED_ON_HUMAN,
  ANSWERED_ON_CODEX, RECEIPT_FOR_HUMAN, RECEIPT_FOR_CODEX, RECEIPT_FOR_CLAUDE]

const ROOM = {
  id: 'r1', room: 'r1', channel: 'hello', visibility: 'members',
  // Only `human` has unread state here. `codex` is named with a zero so "another
  // agent's unread is not mine" cannot pass because the key happens to be absent.
  unread: { human: 2, codex: 0 },
  messages: [{ msg_id: 'r1-1', from: 'codex', to: '#r1', ts: at(20), body: 'room body', kind: 'note' }],
}

const VIEWERS = ['human', 'codex', 'claude-session1']

/** `unacked` as `fabric.py:108` builds it: the message, and nothing about who owes it. */
const asUnacked = (m) => ({ msg_id: m.msg_id, from: m.from, to: m.to, subject: m.subject, bytes: m.bytes })
const UNACKED = [DEMAND_ON_HUMAN, DEMAND_ON_CODEX, DEMAND_ON_CLAUDE].map(asUnacked)

const STATE = (viewer, { receipts = 'fabric' } = {}) => ({
  digest: 'card-t0162', generated_at: at(30), as_of: '2026-09-22',
  phase: 'COMMIT', statuses: ['backlog', 'done'], terminal: ['done'], milestones: {},
  agents: {
    human: { kind: 'human', model: '' },
    codex: { kind: 'agent', model: '' },
    'claude-session1': { kind: 'agent', model: '' },
  },
  register: {}, tasks: {}, reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  viewer,
  conversation: { viewer, is_leader: false, channels: [], rooms: [ROOM], mail: MAIL, withheld: 0 },
  channels: [], drift: [], withheld_tasks: 0,
  unacked: receipts === 'fabric' ? UNACKED : UNACKED.filter((row) => row.to === viewer),
  write: { enabled: true, as: viewer },
})

/* ------------------------------------------------------- what the card says */

/**
 * The threads the card selects, per viewer, written out rather than derived from
 * the fixture -- an expectation computed by the same expression as the code under
 * test asserts nothing. `#hello / #r1` is there for `human` only, because the
 * room's `unread` map names `human` only.
 */
const CARD_SET = {
  human: ['#hello / #r1', 'codex ⇄ human'],
  codex: ['codex ⇄ human'],
  'claude-session1': ['claude-session1 ⇄ codex'],
}

/** The viewer's own thread: where their one message that waits on them lives. */
const CARD_THREAD = {
  human: 'codex ⇄ human',
  codex: 'codex ⇄ human',
  'claude-session1': 'claude-session1 ⇄ codex',
}

/** How many messages in that thread wait on the viewer: one demand, and only theirs. */
const CARD_COUNT = { human: 1, codex: 1, 'claude-session1': 1 }

/** The thread the card drops and the pre-fix *shipped* rule (`to === V`, no `ack_required`) draws. */
const SHIPPED_ONLY = {
  human: 'claude-session1 ⇄ human',      // d6: addressed to the viewer, demands nothing
  codex: 'claude-session1 ⇄ codex',      // d7: same, one thread over
  'claude-session1': 'claude-session1 ⇄ human', // d8: same, one thread over
}

/** The thread the card drops and the *chip* rule (a demand anywhere) draws. */
const CHIP_ONLY = {
  human: 'claude-session1 ⇄ codex',      // d3: a demand codex sent claude-session1
  codex: 'claude-session1 ⇄ codex',      // d3: sent by codex, addressed to another agent
  'claude-session1': 'codex ⇄ human',    // d1 + d2: a demand on someone else
}

/**
 * What "receipts owed" is worth, per the card: the messages addressed to *this*
 * viewer that demand an acknowledgement and have none. One each.
 */
const RECEIPTS_OWED = { human: 1, codex: 1, 'claude-session1': 1 }

/* ------------------------------------------- the three predicates, over MAIL */

/** The thread a message is filed in: `directScope` in `stores/board.js`. */
const threadOf = (row) => [row.from, row.to].sort().join(' ⇄ ')

/** The threads a predicate selects over the fixture's mail. */
const selected = (viewer, waiting) =>
  [...new Set(MAIL.filter((row) => waiting(row, viewer)).map(threadOf))].sort()

const byChip = (row) => Boolean(row.ack_required) && row.state !== 'acked'
const byShipped = (row, viewer) => row.to === viewer && row.state !== 'acked'
const byCard = (row, viewer) => row.to === viewer && Boolean(row.ack_required) && row.state !== 'acked'

const counted = (viewer, thread, waiting) =>
  MAIL.filter((row) => waiting(row, viewer) && threadOf(row) === thread).length

/* ------------------------------------------------------- reading the panes */

/** Every thread row the pane drew: its label, its badge, and the badge's reason. */
const drawnThreads = (page) => page.locator('.aim-thread').evaluateAll((els) => els.map((el) => ({
  label: (el.getAttribute('aria-label') || '').replace(/^Open conversation /, ''),
  badge: (el.querySelector('.aim-unread')?.textContent || '').trim(),
  badgeTitle: el.querySelector('.aim-unread')?.getAttribute('title') || '',
})))

const labels = async (page) => (await drawnThreads(page)).map((row) => row.label).sort()

/** One Attention tile: the number it prints for `label`, and a retrying locator. */
const tile = (page, label) => page.locator('.aim-signal').filter({ hasText: label }).locator('span').first()

/**
 * Serve one viewer's payload, open (or re-open) the pane, and wait for it to mount,
 * retrying the load.
 *
 * The retry is not for the card: it is for the host. The page's module graph comes from
 * the live board's `web/dist`, which another session in this checkout rebuilds while this
 * file runs (measured: `bundle built 08:40:07.787Z` landed inside one run of this file),
 * and the same board is being read by however many peers are testing at that minute -- a
 * document load measured 4s on an idle host and over 8s while they ran. A rebuild that
 * lands between `index.html` and the chunks it names leaves the app unmounted; that is a
 * failure to load, not a verdict about the card, so it is retried and then reported as
 * itself. A hash `goto` is a same-document navigation and asks the board for nothing, so
 * a pane opened at a *new* route is always reached by reloading the target route -- which
 * is also what makes a swap of the fixture visible.
 */
/**
 * The address for one viewer's pane, as something `page.goto` can be handed.
 *
 * `new URL(`/${hash}`, page.url())` is the obvious spelling and it is wrong on the
 * first call of every test in this file. `page.url()` is the test's own `baseURL`
 * (`playwright.config.js:19`) until the page has navigated, and `new URL` ignores
 * the base and returns the input alone when the input is itself absolute -- which
 * `/`-prefixed is. Measured on a fresh page with that same config: `page.url()`
 * is `http://127.0.0.1:8777`, the resolved target prints as
 * `about:/#/chat?needsMe=1`, and `goto` on it lands there, which is a document
 * that never runs the bundle. The pane then cannot mount and the failure is
 * reported as "the .aim-chat pane mounted for human (the served bundle loaded)",
 * which names the bundle rather than the address.
 *
 * So the target is the relative form, which Playwright resolves against `baseURL`
 * itself -- one number, in the one place that already holds it. Measured: `goto(
 * '/#/chat?needsMe=1')` lands on `http://127.0.0.1:8777/#/chat?needsMe=1` and
 * `.aim-chat` mounts. The hash is the whole route in hash mode, so nothing here
 * needs an origin to be correct, which is why the absolute round-trip was a way to
 * get the base wrong rather than a way to be careful with it.
 *
 * It is issued unconditionally rather than behind a "are we already there" test:
 * the second clause's `?needsMe=1` is a hash query, and comparing two URLs that
 * carry one is how the guard this replaced went wrong. A `goto` to the route it is
 * already on costs a same-document navigation, and the `reload` below is what
 * makes the swapped fixture visible either way.
 */
async function showViewer(page, viewer, { receipts = 'fabric', hash = '#/chat?needsMe=1' } = {}) {
  await page.unroute('**/api/state**')
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE(viewer, { receipts })),
  }))
  const pane = hash.startsWith('#/chat') ? '.aim-chat' : '.aim-attention'
  let mounted = false
  for (let attempt = 0; attempt < 2 && !mounted; attempt += 1) {
    await page.goto(`/${hash}`)
    await page.reload()
    mounted = await page.locator(pane).first()
      .waitFor({ state: 'visible', timeout: attempt === 0 ? 20_000 : 10_000 })
      .then(() => true, () => false)
  }
  expect(mounted, `the ${pane} pane mounted for ${viewer} (the served bundle loaded)`).toBe(true)
  if (pane === '.aim-chat') {
    // A pane with no payload yet and a pane whose filter matched nothing both draw no
    // thread, and those are different facts. So wait for the list to stop saying it has
    // nothing (`0 / 0 thread(s)`) rather than for a row to appear.
    await expect(page.locator('.aim-chat-side')).not.toContainText('0 / 0 thread(s)')
  }
}

test.describe('T-0162: needs me is the recipient state, not the presence of a chip', () => {
  // Three panes per test, each a full document load on a host that other sessions are
  // loading and rebuilding at the same time; measured 4s idle, over 8s busy. The default
  // 30s was consumed by a single slow load, which reported as a red card.
  test.describe.configure({ timeout: 120_000 })

  test.beforeEach(async ({ page }) => {
    // The pane polls the digest every 2.5s (`main.js:267`); a fixture that answers
    // it keeps the live board out of the measurement.
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: '{"digest":"card-t0162"}',
    }))
  })

  test('the fixture separates the chip rule, the shipped rule and the card', () => {
    // Not a UI assertion: the precondition that makes the ones below mean something.
    // If a future edit to the fixture makes these three agree, the drawn-set test
    // would pass on the defect the card names, and this test says so instead.
    for (const viewer of VIEWERS) {
      expect(selected(viewer, byCard), `${viewer}: the card, over this fixture`).toEqual(
        CARD_SET[viewer].filter((label) => label !== '#hello / #r1'))
      expect(selected(viewer, byChip), `${viewer}: the chip rule must not select what the card does`)
        .not.toEqual(CARD_SET[viewer].filter((label) => label !== '#hello / #r1'))
      expect(selected(viewer, byShipped), `${viewer}: nor must the shipped rule`)
        .not.toEqual(CARD_SET[viewer].filter((label) => label !== '#hello / #r1'))
    }
    // And the counts, because the card's clause is a count per thread. On the
    // thread that holds an unanswered demand each way, the chip counts both and
    // the card counts the one the viewer owes.
    expect(counted('human', 'codex ⇄ human', byChip),
      'the chip counts the demand the viewer sent beside the one they owe').toBe(2)
    expect(counted('human', 'codex ⇄ human', byCard),
      'the card counts only the demand the viewer owes').toBe(1)
  })

  test('needs me draws the card set, for each of the three viewers', async ({ page }) => {
    // MEASURED FAILURE, 2026-09-22T08:35Z, bundle 830dd79+dirty: each viewer's own
    // thread is drawn and the room rule is right, but the pane also draws the thread
    // holding mail addressed to the viewer that demands *nothing* -- `human` drew
    // `claude-session1 ⇄ human` (d6), `codex` drew `claude-session1 ⇄ codex` (d7),
    // `claude-session1` drew `claude-session1 ⇄ human` (d8). `messageWaiting`
    // (`web/src/panes/ChatPane.vue:35`) asked `to === viewer && state !== 'acked'` and
    // never asked `ack_required`.
    //
    // That warrant is spent and the annotation is gone with it: the predicate now
    // asks `Boolean(message.ack_required)` as well, so the three receipt rows are
    // not waiting mail and no longer enter the set. Playwright reports an annotated
    // test whose body passes as "Expected to fail, but passed", which is what this
    // test did on the fixed bundle; removing the marker is the fix for that, not a
    // concession about the card.
    for (const viewer of VIEWERS) {
      await showViewer(page, viewer)
      // soft, so all three viewers are measured before the test is called failed
      expect.soft(await labels(page), `${viewer}: the threads needs-me draws`)
        .toEqual([...CARD_SET[viewer]].sort())
    }
  })

  test('sent mail, mail for another agent and answered mail are not counted', async ({ page }) => {
    // Same failure as the test above, measured from the other side: the two threads
    // the card drops are the two the shipped predicate kept. Annotation removed with
    // the one above, for the same reason and on the same bundle.
    for (const viewer of VIEWERS) {
      await showViewer(page, viewer)
      const seen = await labels(page)

      // Each of these threads is drawn only by a rule that ignores the recipient or
      // ignores the demand; the fixture really does put that mail there.
      expect(selected(viewer, byShipped),
        `${viewer}: ${SHIPPED_ONLY[viewer]} holds mail addressed to the viewer that demands nothing`).toContain(SHIPPED_ONLY[viewer])
      expect.soft(seen, `${viewer}: ${SHIPPED_ONLY[viewer]} must not be drawn`).not.toContain(SHIPPED_ONLY[viewer])

      expect(selected(viewer, byChip),
        `${viewer}: ${CHIP_ONLY[viewer]} holds a demand that is not the viewer's`).toContain(CHIP_ONLY[viewer])
      expect.soft(seen, `${viewer}: ${CHIP_ONLY[viewer]} must not be drawn`).not.toContain(CHIP_ONLY[viewer])

      // The answered rows (d4, d5) sit in the thread the card *does* draw, so their
      // exclusion is a number rather than a row: one demand owed, not three rows
      // answered. `byShipped` and `byCard` both answer 1 here; `byChip` answers 2.
      expect(counted(viewer, CARD_THREAD[viewer], byCard),
        `${viewer}: messages that wait on the viewer in their own thread`).toBe(1)
    }
  })

  test('every drawn thread says why it needs the viewer: a count, or a reason', async ({ page }) => {
    for (const viewer of VIEWERS) {
      await showViewer(page, viewer)
      const rows = await drawnThreads(page)

      const own = rows.find((row) => row.label === CARD_THREAD[viewer])
      expect(own, `${viewer}: their own thread is drawn`).toBeTruthy()
      expect(own.badge, `${viewer}: the count of messages waiting on them`).toBe(String(CARD_COUNT[viewer]))
      expect(own.badgeTitle, `${viewer}: and the count says whose it is`).toContain(viewer)

      // The room has no per-viewer count in the pane -- a room message is addressed
      // `#r1`, never to the viewer -- so its marker is the reason instead.
      const room = rows.find((row) => row.label === '#hello / #r1')
      if (viewer === 'human') {
        expect(room, `${viewer}: the room the payload says is unread for them`).toBeTruthy()
        expect(room.badge, `${viewer}: a count where the fabric has one, the reason where it does not`).toBe('needs me')
        expect(room.badgeTitle, `${viewer}: the room says who it is waiting on`).toContain('human')
      } else {
        expect(room, `${viewer}: the room's unread is not theirs`).toBeUndefined()
      }
    }
  })

  test('receipts-owed counts the recipient, and the payload counts the fabric', async ({ page }) => {
    // The card's fourth clause, on the payload the wire really ships: `fabric.py:108`
    // appends every message with `ack_required && !acked_at` and filters on no
    // recipient, and `api.py:135` publishes that list as it is. The fixture carries
    // the same three rows, and each viewer owes exactly one.
    //
    // The predicate asks `messageWaiting`, which is the card's rule, so the three
    // rows `unacked` names produce the same tile as the scoped payload below does:
    // the tile no longer counts the list that counts the fabric. Annotation removed
    // on the bundle that made it pass (`f83c4c0+dirty`); the test below, which never
    // carried one, is the same measurement on the viewer-scoped payload.
    expect(UNACKED.length, 'the fixture ships three receipts for every viewer').toBe(3)
    for (const viewer of VIEWERS) {
      await showViewer(page, viewer, { receipts: 'fabric', hash: '#/attention' })
      await expect.soft(tile(page, 'Receipts owed'),
        `${viewer}: receipts owed, on a payload that counts every recipient`)
        .toHaveText(String(RECEIPTS_OWED[viewer]))
    }
  })

  test('with the payload scoped to the viewer, the tile prints the receipts the viewer owes', async ({ page }) => {
    // The same pane, the same tiles, a payload that carries only this viewer's own
    // receipts: the number is then the one the Chat filter selects. So the whole of
    // the difference in the test above is the scope of `unacked`, not a second
    // derivation in the pane -- which is what makes the failure above a fabric
    // finding rather than a front-end one.
    for (const viewer of VIEWERS) {
      await showViewer(page, viewer, { receipts: 'viewer', hash: '#/attention' })
      await expect(tile(page, 'Receipts owed'), `${viewer}: receipts the viewer owes`)
        .toHaveText(String(RECEIPTS_OWED[viewer]))
    }
  })

  test('clicking the Attention receipts signal lands on the same filtered set', async ({ page }) => {
    // This test carried the last `test.fail()` marker in the repo, and the defect
    // it was hiding is in the destination rather than in the assertion.
    //
    // `OverviewPane` builds the Receipts-owed destination as a ternary on how many
    // threads owe the reader. Both branches sent `needsMe=1`; the one-thread branch
    // sent `thread=<key>` and the multi-thread branch sent `shape=direct`. Those are
    // two different keys doing two different jobs:
    //
    //   `shape`  is the *filter*   -- `ChatPane.vue:391` drops every thread whose
    //                                 `group` does not match
    //   `thread` is the *selection* -- `ChatPane.vue:487` (`openThread`) sets
    //                                 `picked.value` and `filters.thread`, which the
    //                                 reader pane reads at `:423`. Nothing in
    //                                 `visibleThreads` consults it.
    //
    // So the branch that named the conversation sent no filter at all. Measured on
    // the live board 2026-09-23: `?needsMe=1&thread=dm:codex ⇄ human` draws 5
    // threads (two channels plus three directs) where `?needsMe=1&shape=direct`
    // draws 3 -- which for `human` is the whole needs-me list, exactly what this
    // marker's reason said. The card's acceptance is "lands on the same filtered
    // set", and the set the tile counts is the directs.
    //
    // Fixed by sending both keys: `shape=direct` is the filter, `thread=` is the
    // selection, and the two do not conflict. "It opens on the conversation rather
    // than the list" (`OverviewPane.vue:118`) survives because `picked` is still
    // set to that thread -- the list beside it is the directs rather than
    // everything, which is the other half of the same sentence.
    //
    // The earlier reason on this line is kept because it was also true and is a
    // *different* fact: this assertion used to demand `shape=direct` unconditionally
    // while the product emitted it only for two or more threads, so the test was
    // expected-failing on an assertion the product could never satisfy for this
    // fixture -- which for `test.fail()`, satisfied by *any* failure, meant the
    // test had no power to report the set question it is named for.
    for (const viewer of VIEWERS) {
      await showViewer(page, viewer, { receipts: 'viewer', hash: '#/attention' })
      await page.locator('.aim-signal').filter({ hasText: 'Receipts owed' }).click()
      await page.waitForURL(/#\/chat\?/)
      expect.soft(page.url(), `${viewer}: the signal's destination`).toContain('needsMe=1')
      expect(page.url(), `${viewer}: the signal's filter`).toContain('shape=direct')
      await expect(page.locator('.aim-chat-side')).not.toContainText('0 / 0 thread(s)')
      expect.soft(await labels(page), `${viewer}: the set the Attention count lands on`)
        .toEqual([CARD_THREAD[viewer]])
    }
  })
})
