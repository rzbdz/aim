import { expect, test } from '@playwright/test'

/**
 * T-0172 -- "Chat 'needs me' must be able to match a channel, and the thread list
 * must show the state it filters on".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T03:20:22.505Z,
 * actor codex), verbatim acceptance:
 *
 *   "With the human as viewer, needs me surfaces a channel thread that contains
 *    something addressed to the human, and every thread row carries a visible
 *    waiting-on-you marker. Today threadNeedsMe returns false for group==='channel'
 *    unconditionally and the payload's channel objects carry only
 *    gated/id/messages/phase/rule with no unread state; measured live, needs me
 *    took 9 threads to 4 and all four were direct threads the human is not a party
 *    to, while #hello held an unanswered phase request and was filtered out."
 *
 * Revision measured for this file -- `GET http://127.0.0.1:8777/api/revision`
 * on 2026-09-22, immediately before the reported run and again immediately after
 * it:
 *
 *   fabric 870b282+dirty          (before and after the run; it has since moved
 *                                  to 02916e0+dirty, a peer commit that did not
 *                                  touch the bundle below)
 *   bundle 870b282+dirty, built 2026-09-22T08:40:07.787Z, source "vite build",
 *          source_sha256 a22a1a231960314cb761e9279d3c833dd9f522c95057fdcc8f7174364002822a
 *   stale: true
 *   front_end_sha256 092bbdd10559c2594a5578e1533918940943e8b8fa9857b3f8f84467eef861f8
 *                    before, 525685aea2734c5f100e2a3121fb6f226743504d8197dffeb4647a2f44a4fe56
 *                    after -- `web/src` was edited *during* the run
 *
 * `stale` is true and it is not a rounding error: a peer is editing `web/src`
 * while this file runs, so the bundle answering 8777 was not built from the source
 * in the checkout, and the source hash moved between the two reads above. The
 * verdict below is therefore a verdict about the bytes a reader loads on 8777, and
 * it was measured on a bundle a peer rebuilt mid-session (the first run of this
 * file hit `f0c4d64+dirty, built 08:33:19.792Z`, the reported run hit the rebuild;
 * both passed, and both chunks carry the same predicate). The served `ChatPane`
 * chunk was read beside the tree rather than assumed: both ask the channel question
 * with the newest message's author (`ChatPane.vue:50` / `threadWaiting`, exported),
 * so chunk and tree agree about *this* card even though the build stamp and
 * `source_sha256` do not match the tree.
 *
 * ---------------------------------------------------------------------------
 * The two clauses, and the one thing the payload cannot say
 *
 * Clause 1: `needs me`, read as `human`, keeps a channel that is waiting on the
 * leader. The defect the card names is that the predicate answered `false` for
 * `group === 'channel'` unconditionally -- there is no channel for which the fix
 * is more work than the bug, so the fixture's `#hello` holds exactly the card's
 * case: a message from `codex` of `kind: 'request'` ("request: SEALED_DIVERGENT ->
 * COMMIT"), newest in the channel, with no answer after it. It must be kept, and
 * `#quiet`, whose newest message is the viewer's own note, must not be.
 *
 * The card's phrase "contains something addressed to the human" is not
 * implementable for a channel, and that is a payload fact rather than a choice.
 * A channel message as `/api/state` ships it has `from`, `ts`, `kind`,
 * `responds_to`, `subject`, `phase`, `body`, `hash` -- no `to` -- and
 * `ChatPane.vue` derives `to: '#' + channel.id` for every row it flattens
 * (`stores/board.js:310`). So `message.to === viewer` can never be true for a
 * channel message and there is no per-viewer cursor in the payload either (the
 * card says it: channel objects carry only gated/id/messages/phase/rule). The
 * computable state is who spoke last, which is what this fixture is built on; the
 * residue -- a channel the human has already answered, but which still holds an
 * earlier request for them -- is called out in the report and is *not* asserted
 * here, because asserting it would be asserting a rule the card does not state.
 *
 * Clause 2: every row the view draws carries a marker, and the marker names the
 * reader. A count alone ("1") says a thread is busy; `waiting-on-you` is the part
 * that has to be visible, so the marker's own tooltip -- `2 message(s) addressed
 * to human with no receipt yet` / `this thread is waiting on human` -- is read as
 * well as its text.
 *
 * The last test closes the card's own sentence: "the thread list must show the
 * state it filters on". It flips the control in the pane and asserts the set of
 * rows that carry a marker equals the set the filter keeps. That is the property
 * the old pane broke in both directions at once -- it filtered on a state
 * (`threadNeedsMe`) and drew a different one (`t.unread`), so a channel could be
 * kept by the filter with no marker, or marked with no filter.
 *
 * ---------------------------------------------------------------------------
 * The fixture, and why every row is there
 *
 *   #hello            claude-session1 note, then codex's unanswered phase
 *                     request                              -> waits on the leader
 *   #quiet            one note, from the viewer            -> does not
 *   #hello / #r1      room with `unread: { human: 1 }`     -> waits on the leader
 *   codex ⇄ human     m1 codex -> human, unread            -> waits on the leader
 *                     m2 human -> codex, unread            -> the viewer's own
 *   claude-session1 ⇄ codex   m3 codex -> claude-session1  -> another agent's
 *   claude-session1 ⇄ human   m4 human -> claude-session1, acked -> answered
 *
 * `#quiet`, `claude-session1 ⇄ codex` and `claude-session1 ⇄ human` are in the
 * unfiltered list and out of the filtered one: a test that only asked "are these
 * three labels absent from `needs me`" would pass on an empty pane, so each one
 * is asserted to exist first.
 *
 * ---------------------------------------------------------------------------
 * VERDICT: PASS against the bundle named above. All five tests pass, and the
 * clauses they assert are the card's: clause 1 keeps `#hello` and drops `#quiet`,
 * clause 2 finds a marker on every kept row whose tooltip names `human`, and the
 * last test finds the kept set equal to the marked set.
 *
 *   $ npx playwright test tests/card-t0172-chat-needsme.spec.js --workers=1 --retries=0 --reporter=line
 *   Running 5 tests using 1 worker
 *   [1/5] ... the fixture discriminates: the channel that waits and the channels that do not
 *   [2/5] ... needs me keeps the channel holding the unanswered request
 *   [3/5] ... the channel that is not waiting is in the list and out of the filter
 *   [4/5] ... every row the filter keeps carries a marker that names the viewer
 *   [5/5] ... the marker and the filter are one state: marked exactly where kept
 *     5 passed (15.8s)
 *
 * The card's defect is gone in the bundle as well as in the tree: `threadWaiting`
 * (`ChatPane.vue:38`) answers the channel question with the newest message's
 * author, and the row marker is `t.unread || threadNeedsMe(t)`, so the channel
 * that has no countable unread still carries the word. Grepped in the served
 * chunk as well as read in the tree -- `web/dist/assets/ChatPane-Pv16ek7k.js`
 * (16,747 bytes, 16:40) holds
 * `...:e.msgs.length>0&&e.msgs.at(-1)?.by!==t` and the `unread||`needs me``
 * fallback with the tooltip `this thread is waiting on ${viewer}` -- because the
 * revision says `stale` and a reader gets the chunk, not the tree.
 *
 * Measured live beside the fixture, on the same revision, read-only: the card's
 * own instance now has a marker. As `human`, the payload holds 9 threads and the
 * pane's predicate keeps 5 -- `#barrier-v0`, `#hello`, `codex ⇄ human`,
 * `codex-orangement ⇄ human`, `human ⇄ human` -- where the card measured "9
 * threads to 4, all four direct threads the human is not a party to".
 */
const at = (mm) => `2026-09-22T02:${String(mm).padStart(2, '0')}:00.000Z`

/**
 * A channel message in the shape `/api/state` really ships: no `to`.
 *
 * Deliberately without one. A fixture that added `to: 'human'` would make
 * `messageWaiting` true for a channel message and the card's first clause would
 * pass for a reason the server can never produce.
 */
const ch = (mm, from, over = {}) => ({
  from, ts: at(mm), kind: 'note', responds_to: '', subject: '', phase: 'COMMIT',
  body: `channel body ${mm}`, hash: `h${mm}`, ...over,
})

/** The card's case: an unanswered phase request, addressed to the barrier's leader. */
const PHASE_REQUEST = {
  kind: 'request', responds_to: '', phase: 'SEALED_DIVERGENT',
  subject: 'request: SEALED_DIVERGENT -> COMMIT',
  body: 'Both agents have sealed. Advance the barrier so cross-examination can proceed.',
}

const mail = (id, from, to, state, ackRequired, mm) => ({
  msg_id: id, from, to, ts: at(mm), subject: `subject ${id}`, body: `body ${id}`, bytes: 42,
  ack_required: ackRequired, acked_at: state === 'acked' ? at(mm) : '', claimed_at: '', state,
})

const ROOM = {
  id: 'r1', room: 'r1', channel: 'hello', visibility: 'members',
  unread: { human: 1, codex: 0 },
  messages: [ch(12, 'codex', { to: '#r1', mentions: ['human'], body: 'room body' })],
}

const STATE = {
  digest: 'card-t0172',
  generated_at: at(30), as_of: '2026-09-22',
  statuses: ['backlog', 'done'], terminal: ['done'], phase: 'COMMIT', milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' },
            'claude-session1': { kind: 'agent', model: '' } },
  register: {}, tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  viewer: 'human',
  conversation: {
    viewer: 'human', is_leader: true,
    channels: [
      { id: 'hello', phase: 'COMMIT', gated: false, rule: 'everything in this phase',
        messages: [ch(10, 'claude-session1'), ch(11, 'codex', PHASE_REQUEST)] },
      { id: 'quiet', phase: 'COMMIT', gated: false, rule: 'everything in this phase',
        messages: [ch(1, 'human', { body: 'the viewer had the last word here' })] },
    ],
    rooms: [ROOM],
    mail: [
      mail('m1', 'codex', 'human', 'unread', true, 2),
      mail('m2', 'human', 'codex', 'unread', true, 3),
      mail('m3', 'codex', 'claude-session1', 'unread', true, 4),
      mail('m4', 'human', 'claude-session1', 'acked', true, 5),
    ],
    withheld: 0,
  },
  channels: [], unacked: [], drift: [], withheld_tasks: 0,
  write: { enabled: true, as: 'human' },
}

// --- what the fixture says, computed from the payload and not from the pane ---

const VIEWER = 'human'

/** One chronological flattening, as `stores/board.js:310` builds it. */
function rowsOf(state) {
  const rows = []
  for (const channel of state.conversation.channels) {
    for (const m of channel.messages) rows.push({ ...m, shape: 'channel', channel: channel.id, room: null })
  }
  for (const room of state.conversation.rooms) {
    for (const m of room.messages) rows.push({ ...m, shape: 'room', channel: room.channel, room: room.id })
  }
  for (const m of state.conversation.mail) {
    rows.push({ ...m, shape: 'direct', channel: null, room: null,
                scope: [m.from, m.to].sort().join(' ⇄ ') })
  }
  return rows.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
}

const keyOf = (row) => (row.shape === 'channel' ? `ch:${row.channel}`
  : row.shape === 'room' ? `room:${row.channel}:${row.room}` : `dm:${row.scope}`)
const labelOf = (key) => (key.startsWith('ch:') ? `#${key.slice(3)}`
  : key.startsWith('room:') ? `#${key.slice(5).replace(':', ' / #')}` : key.slice(3))

/**
 * The threads this fixture says are waiting on the viewer.
 *
 * Written against the payload, not against `ChatPane.vue`: a direct thread waits
 * when it holds a message addressed to the viewer that nothing has acked; a room
 * waits when its server-computed unread names the viewer; a channel waits when
 * its newest message is not the viewer's (see the header for why that is the only
 * computable reading of the card's clause for a channel).
 */
function waitsOnViewer(state, viewer = VIEWER) {
  const byKey = new Map()
  for (const row of rowsOf(state)) {
    if (!byKey.has(keyOf(row))) byKey.set(keyOf(row), [])
    byKey.get(keyOf(row)).push(row)
  }
  const kept = new Set()
  for (const channel of state.conversation.channels) {
    const msgs = byKey.get(`ch:${channel.id}`) || []
    if (msgs.length && msgs.at(-1).from !== viewer) kept.add(`ch:${channel.id}`)
  }
  for (const room of state.conversation.rooms) {
    if ((room.unread || {})[viewer]) kept.add(`room:${room.channel}:${room.id}`)
  }
  for (const [key, msgs] of byKey) {
    if (key.startsWith('dm:') && msgs.some((m) => m.to === viewer && m.state !== 'acked')) kept.add(key)
  }
  return [...kept].map(labelOf).sort()
}

const sorted = (list) => [...list].sort()

// --- reading the pane -------------------------------------------------------

const threadLabels = (page) => page.locator('.aim-thread')
  .evaluateAll((els) => els.map((el) => (el.getAttribute('aria-label') || '')
    .replace(/^Open conversation /, '')))

const rowOf = (page, label) => page.locator(`.aim-thread[aria-label="Open conversation ${label}"]`)

/** The marker on a row, as text plus the tooltip that says whose turn it is. */
async function markerOf(page, label) {
  const tag = rowOf(page, label).locator('.aim-unread')
  if (!await tag.count()) return null
  return { text: (await tag.first().innerText()).trim(),
           title: (await tag.first().getAttribute('title')) || '' }
}

async function open(page, { needsMe = false } = {}) {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
  }))
  await page.goto(needsMe ? '/#/chat?needsMe=1' : '/#/chat')
  await expect(page.locator('.aim-chat')).toBeVisible()
  await expect(page.locator('.aim-thread').first()).toBeVisible()
}

const NEEDS_ME = ['#hello', '#hello / #r1', 'codex ⇄ human']
const NOT_NEEDS_ME = ['#quiet', 'claude-session1 ⇄ codex', 'claude-session1 ⇄ human']

test.describe('T-0172: a channel can be what needs you, and the list says so', () => {
  test('the fixture discriminates: the channel that waits and the channels that do not', () => {
    // Not a UI assertion -- the precondition that makes the ones below mean
    // something. `#hello`'s newest message is the card's case (a request, from an
    // agent, with no answer after it); `#quiet`'s newest is the viewer's own, so a
    // pane that drew every channel and a pane that drew none would both be wrong
    // about one of them.
    const hello = STATE.conversation.channels[0]
    const quiet = STATE.conversation.channels[1]
    expect(hello.messages.at(-1).kind, '#hello ends with the unanswered request').toBe('request')
    expect(hello.messages.at(-1).from, '#hello is not answered by the viewer').not.toBe(VIEWER)
    expect(quiet.messages.at(-1).from, '#quiet ends with the viewer own note').toBe(VIEWER)
    expect(sorted(waitsOnViewer(STATE)), 'the fixture own answer').toEqual(NEEDS_ME)
    expect(NOT_NEEDS_ME.every((label) => !NEEDS_ME.includes(label)),
      'no label is asserted in both directions').toBe(true)
  })

  test('needs me keeps the channel holding the unanswered request', async ({ page }) => {
    await open(page, { needsMe: true })
    const kept = sorted(await threadLabels(page))
    expect(kept, 'the pane keeps what the fixture says waits on the viewer').toEqual(NEEDS_ME)
    expect(kept, 'the card measured instance: #hello holds an unanswered phase request')
      .toContain('#hello')
  })

  test('the channel that is not waiting is in the list and out of the filter', async ({ page }) => {
    // Both halves, because "not in `needs me`" is worth nothing if the row was
    // never in the drawer: that is the difference between a filter and a pane that
    // forgot the thread.
    await open(page)
    const all = sorted(await threadLabels(page))
    expect(sorted([...NEEDS_ME, ...NOT_NEEDS_ME]), 'every fixture thread has a row').toEqual(all)

    await open(page, { needsMe: true })
    const kept = await threadLabels(page)
    for (const label of NOT_NEEDS_ME) {
      expect(kept, `${label} was in the list and is not waiting on the viewer`).not.toContain(label)
    }
  })

  test('every row the filter keeps carries a marker that names the viewer', async ({ page }) => {
    await open(page, { needsMe: true })
    for (const label of await threadLabels(page)) {
      const marker = await markerOf(page, label)
      expect(marker, `${label}: a row the filter keeps must carry a marker`).not.toBeNull()
      await expect(rowOf(page, label).locator('.aim-unread')).toBeVisible()
      // A number where the fabric can count one, the words where it cannot (a
      // channel has no per-viewer cursor, so a count-only marker drew nothing for
      // exactly the thread this card was filed about).
      expect(marker.text, `${label}: the marker prints a count or the words`).toMatch(/^(needs me|\d+)$/)
      expect(marker.title, `${label}: the marker says whose turn it is`).toContain(VIEWER)
    }
  })

  test('the marker and the filter are one state: marked exactly where kept', async ({ page }) => {
    // The card's own sentence. Flipping the control in the pane is the reader's
    // route into the view, and it is the same route `OverviewPane` deep-links to
    // (`/chat?needsMe=1`).
    await open(page)
    const all = await threadLabels(page)
    const marked = []
    for (const label of all) if (await markerOf(page, label)) marked.push(label)

    const toggle = page.locator('.aim-thread-filters .el-checkbox').filter({ hasText: 'needs me' })
    await toggle.click()
    await expect(page.locator('.aim-thread')).toHaveCount(marked.length)

    const kept = await threadLabels(page)
    expect(sorted(kept), 'kept == marked: the list shows the state it filters on')
      .toEqual(sorted(marked))
    expect(sorted(kept), 'and both are the fixture own answer').toEqual(NEEDS_ME)
  })
})
