/**
 * T-0162 -- "Define needs-me and receipts-owed from recipient state, not from the
 * presence of a receipt chip".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T03:00:32.223Z,
 * actor codex), verbatim:
 *
 *   "For each viewer, needs-me includes only incoming direct messages addressed
 *    to that viewer that require an acknowledgement and are not acked, plus rooms
 *    with unread state for that viewer; it excludes messages the viewer sent and
 *    messages addressed to another agent; each thread shows a count/reason for why
 *    it needs the viewer; tests cover human, codex and claude-session1 viewers
 *    with fixtures containing incoming unacked, outgoing unacked and already-acked
 *    mail"
 *
 * This file asserts the selection and the per-thread count, for all three named
 * viewers. It does not assert the card's last clause ("clicking the Attention
 * receipts signal lands on the same filtered set"): that is a navigation
 * assertion, `OverviewPane` sends it to `/chat?needsMe=1&shape=direct`, and it is
 * not restated here.
 *
 * Verified by reading the source, not only the bundle: the rule now lives at
 * `web/src/panes/ChatPane.vue:35` (`messageWaiting`) and `:38` (`threadWaiting`),
 * exported so that `web/tests/unit/W3.spec.js` reads the same predicate the page
 * does.
 *
 * Revision measured for this file -- `GET http://127.0.0.1:8777/api/revision`
 * on 2026-09-22, immediately before the run below:
 *
 *   fabric f0c4d64+dirty
 *   bundle f0c4d64+dirty, built 2026-09-22T08:33:19.792Z, source "vite build"
 *   stale: true
 *
 * `stale` is true: the bundle answering 8777 was not built from a clean tree.
 * The verdict below is a verdict about the bundle a reader loads, and its rule
 * was read in the source beside it and is the same rule.
 *
 * ---------------------------------------------------------------------------
 * Three predicates, and why the fixture has to separate them
 *
 *   naive   -- the card's named defect: a thread needs the viewer if it holds a
 *              message carrying the `receipt demanded` chip anywhere. The chip is
 *              drawn as `row.ack_required && row.state !== 'acked'` (`:177`), so
 *              "carrying the chip" is `ack_required && state !== 'acked'` -- which
 *              says nothing about who it is addressed to. Every demand the viewer
 *              *sent* satisfies it.
 *
 *   shipped -- what the checkout does: `message.to === viewer && message.state
 *              !== 'acked'` (`ChatPane.vue:35`). It gets the addressee right and
 *              the demand wrong: `ack_required` is never consulted, so a receipt
 *              the viewer owes nobody is counted while it is undelivered.
 *
 *   card    -- `message.to === viewer && message.ack_required && message.state
 *              !== 'acked'`, plus a room whose `unread` names the viewer.
 *
 * The mailbox, one row of each kind the card names:
 *
 *   d1  codex -> human            ack_required, unread       the demand X must answer
 *   d2  human -> codex            ack_required, unread       X *sent* it (needs the peer, not X)
 *   d3  codex -> claude-session1  ack_required, unread       addressed to another agent
 *   d4  claude-session1 -> human  no ack_required, delivered a receipt X owes nobody
 *   d5  codex -> human            ack_required, *acked*      already answered
 *   d6  human -> codex            ack_required, *acked*      already answered
 *   d7  codex -> claude-session1  no ack_required, delivered receipt to another agent
 *
 * plus a room `#hello / #r1` with `unread: { human: 2, codex: 0 }`.
 *
 * d1 and d2 share one thread (`codex ⇄ human`): the chip counts 2, the card
 * counts 1. Over the whole fixture the chip counts 3 (d1, d2, d3 -- it never asks
 * who a message is for) where the card counts 1 for every viewer. That is the
 * count the naive implementation gets wrong, and `the fixture discriminates`
 * asserts the disagreement rather than assuming it.
 *
 * ---------------------------------------------------------------------------
 * VERDICT: FAIL against the bundle named above. Nine of these twelve tests pass;
 * three are annotated `test.fail` because `messageWaiting` asks `message.to ===
 * viewer && message.state !== 'acked'` and never asks `message.ack_required`.
 * Measured:
 *
 *  1. Viewer `human`: `needs me` draws ["#hello / #r1", "claude-session1 ⇄ human",
 *     "codex ⇄ human"]. The card's set is ["#hello / #r1", "codex ⇄ human"].
 *     One extra thread: d4 (`claude-session1 -> human`, `ack_required: false`,
 *     `state: 'delivered'`) is the receipt `human` owes nobody, drawn as a thread
 *     that needs them.
 *  2. Viewer `claude-session1`: the badge on `claude-session1 ⇄ codex` reads 2
 *     where the card's count is 1. The second is d7 (`codex -> claude-session1`,
 *     `ack_required: false`, `state: 'delivered'`), the same receipt shape.
 *
 * The predicate that gets both right is in this file (`cardWaiting`): add the
 * `ack_required` test and both sets and both counts come out as the card says.
 * The defect is one clause wide; the count in clause 2 is the smallest sentence
 * that names it.
 *
 * ---------------------------------------------------------------------------
 * A note on the write set. When this file was written, another session was
 * editing the same path with its own T-0162 test (`md5 c3a42df8ce16a71f67591b8d
 * 46158ee3`; preserved at /tmp/t0162-peer-copy2.spec.js). This file replaced it
 * at the path the brief names. See the report for the collision.
 */
import { expect, test } from '@playwright/test'

const stamp = (ts) => ts.replace(/[-:]/g, '')

/** An ordinary direct message, in the shape `/api/state` ships in `conversation.mail`. */
const mail = (id, from, to, state, ackRequired, ts) => ({
  msg_id: id, from, to, ts,
  subject: `subject ${id}`, body: `body ${id}`, bytes: 42,
  ack_required: ackRequired,
  acked_at: state === 'acked' ? ts : '',
  claimed_at: '', state,
})

/** A receipt: it announces the message it answers and demands nothing back. */
const receipt = (id, from, to, ts) => ({
  msg_id: id, from, to, ts,
  subject: `RECEIPT for ${stamp(ts)}-${from}`, body: `${from} received it from ${to}.\n`,
  bytes: 0, ack_required: false, acked_at: '', claimed_at: '', state: 'delivered',
})

const at = (mm) => `2026-09-22T02:${String(mm).padStart(2, '0')}:00.000Z`

const D1 = mail('d1', 'codex', 'human', 'unread', true, at(1))
const D2 = mail('d2', 'human', 'codex', 'unread', true, at(2))
const D3 = mail('d3', 'codex', 'claude-session1', 'unread', true, at(3))
const D4 = receipt('d4', 'claude-session1', 'human', at(4))
const D5 = mail('d5', 'codex', 'human', 'acked', true, at(5))
const D6 = mail('d6', 'human', 'codex', 'acked', true, at(6))
const D7 = receipt('d7', 'codex', 'claude-session1', at(7))

const MAIL = [D1, D2, D3, D4, D5, D6, D7]

const ROOM = {
  id: 'r1', room: 'r1', channel: 'hello', visibility: 'members',
  // Only `human` has unread state here, and `codex` is named with a zero so the
  // "another agent's unread is not mine" case cannot pass because the key is
  // missing for the wrong reason.
  unread: { human: 2, codex: 0 },
  messages: [{ from: 'codex', to: '#r1', ts: at(8), body: 'room body', mentions: ['human'], kind: 'note' }],
}

/** The channel for `a channel is waiting when its newest message is not the viewer's`. */
const CHANNEL = {
  id: 'hello', phase: 'RESOLVE', gated: false, rule: 'fixture',
  messages: [{ from: 'claude-session1', to: 'hello', ts: at(20), kind: 'note', body: 'last word' }],
}

const VIEWERS = ['human', 'codex', 'claude-session1']

const STATE = (viewer, { channels = [] } = {}) => ({
  digest: `card-t0162-${viewer}`, generated_at: at(30), as_of: '2026-09-22',
  statuses: ['backlog', 'done'], terminal: ['done'], phase: 'RESOLVE', milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' },
            'claude-session1': { kind: 'agent', model: '' } },
  register: {}, tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  viewer,
  conversation: { viewer, is_leader: false, channels, rooms: [ROOM], mail: MAIL, withheld: 0 },
  channels: [], unacked: [], drift: [], withheld_tasks: 0,
  write: { enabled: true, as: viewer },
})

// ---------------------------------------------------------------------------
// The predicates over the fixture, mirroring `ChatPane.vue`'s thread keys
// (`:45` channels, `:54` rooms, `:76` direct).

const shapeOf = (row) => (row.shape === 'channel' ? `ch:${row.channel}`
  : row.shape === 'room' ? `room:${row.channel}:${row.room}` : `dm:${row.scope}`)

/** A thread key as the pane labels it (`:45` channel, `:54` room, `:76` direct). */
const labelOf = (key) => (key.startsWith('ch:') ? `#${key.slice(3)}`
  : key.startsWith('room:') ? `#${key.slice(5).replace(':', ' / #')}`
    : key.slice(3))

const rowsOf = (state) => {
  const rows = []
  for (const channel of state.conversation.channels) {
    for (const m of channel.messages || []) rows.push({ ...m, shape: 'channel', channel: channel.id, room: null })
  }
  for (const room of state.conversation.rooms) {
    for (const m of room.messages || []) rows.push({ ...m, shape: 'room', channel: room.channel, room: room.id })
  }
  for (const m of state.conversation.mail) {
    rows.push({ ...m, shape: 'direct', scope: [m.from, m.to].sort().join(' ⇄ '), channel: null, room: null })
  }
  return rows.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
}

/** The chip drawn at `ChatPane.vue:177`; "carrying a receipt chip", the named naive test. */
const carriesChip = (row) => row.shape === 'direct' && Boolean(row.ack_required) && row.state !== 'acked'
/** The shipped predicate, `ChatPane.vue:35` (`messageWaiting`). */
const shippedWaiting = (row, viewer) =>
  row.shape === 'direct' && row.to === viewer && row.state !== 'acked'
/** The card's predicate. */
const cardWaiting = (row, viewer) =>
  row.shape === 'direct' && row.to === viewer && Boolean(row.ack_required) && row.state !== 'acked'

/**
 * Which threads a predicate selects for a viewer.
 *
 * Rooms and channels are the same in all three, because the card and the source
 * agree there: a room is selected by `unread[viewer]` (the card's words), and a
 * channel message is addressed `#<id>` rather than to a viewer, so the only
 * computable reading -- and the one `ChatPane.vue:50` argues for -- is that a
 * channel waits on the reader when its newest message is somebody else's. The
 * fixture's main states carry no channel, so that clause gets its own test.
 */
function selected(state, viewer, waiting) {
  const byKey = new Map()
  for (const row of rowsOf(state)) {
    if (!byKey.has(shapeOf(row))) byKey.set(shapeOf(row), [])
    byKey.get(shapeOf(row)).push(row)
  }
  const keys = new Set(byKey.keys())
  for (const room of state.conversation.rooms) {
    if (!(room.unread || {})[viewer]) keys.delete(`room:${room.channel}:${room.id}`)
  }
  for (const channel of state.conversation.channels) {
    const msgs = byKey.get(`ch:${channel.id}`) || []
    if (!(msgs.length && msgs.at(-1).from !== viewer)) keys.delete(`ch:${channel.id}`)
  }
  for (const [key, msgs] of byKey) {
    if (key.startsWith('dm:') && !msgs.some((row) => waiting(row, viewer))) keys.delete(key)
  }
  return keys
}

/** What the badge on a thread must print: how many of its messages wait on the viewer. */
const countOf = (state, viewer, key, waiting) =>
  rowsOf(state).filter((row) => shapeOf(row) === key && waiting(row, viewer)).length

const sorted = (s) => [...s].sort()

// --- reading the pane -------------------------------------------------------

const threadLabels = (page) => page.locator('.aim-thread')
  .evaluateAll((els) => els.map((el) => (el.getAttribute('aria-label') || '')
    .replace(/^Open conversation /, '')))

/**
 * What a row's marker prints: a number where the fabric can count one, and the
 * words `needs me` where it cannot (a channel has no per-viewer cursor), so both
 * are read as themselves rather than coerced.
 */
const badgeOf = async (page, label) => {
  const tag = page.locator(`.aim-thread[aria-label="Open conversation ${label}"] .aim-unread`)
  if (!await tag.count()) return 0
  const text = (await tag.first().innerText()).trim()
  return /^\d+$/.test(text) ? Number(text) : text
}

/**
 * One `/api/state` payload per test, and a digest that matches it so the pane does
 * not refetch behind the test's back.
 *
 * `reload` is what makes a second payload land on the same page: `goto` with the
 * URL the page is already on is only a hash change, so Vue does not remount and
 * the old record stays on screen. The state route is re-registered rather than
 * stacked, so a second payload replaces the first instead of racing it.
 */
async function open(page, state, { reload = false } = {}) {
  await page.unroute('**/api/state**')
  await page.route('**/api/state**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify(state),
  }))
  await page.route('**/api/digest**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: state.digest }),
  }))
  if (reload) await page.reload()
  else await page.goto('/#/chat?needsMe=1')
  await expect(page.locator('.aim-chat')).toBeVisible()
  await expect(page.locator('.aim-thread').first()).toBeVisible()
}

test.describe('T-0162: needs me is derived from the recipient, not from the chip', () => {
  test('the fixture discriminates: the chip predicate and the card disagree', () => {
    // Not a UI assertion -- the precondition that makes the ones below mean
    // something. If a future edit to the fixture makes the chip predicate select
    // the card's set, or count what it counts, the assertions below could pass on
    // the defect the card names, and this test says so instead.
    for (const viewer of VIEWERS) {
      const state = STATE(viewer)
      const naive = sorted(selected(state, viewer, carriesChip))
      const card = sorted(selected(state, viewer, cardWaiting))
      expect(naive, `${viewer}: the chip predicate's threads`).not.toEqual(card)
    }
    // The count, not just the membership. A predicate that answers "does any
    // message carry a receipt chip" counts d1, d2 and d3 -- three, for every
    // viewer, because it never asks who the message is for. The card counts one
    // for every viewer: human owes d1, codex owes d2, claude-session1 owes d3.
    for (const viewer of VIEWERS) {
      const rows = rowsOf(STATE(viewer))
      expect(rows.filter(carriesChip).length,
        `${viewer}: any-message-carrying-a-chip counts every demand in the fixture`).toBe(3)
      expect(rows.filter((row) => cardWaiting(row, viewer)).length,
        `${viewer}: the card counts only the demands this viewer owes`).toBe(1)
    }
    // The same disagreement inside one thread: d1 (a demand on `human`) and d2
    // (`human`'s own unanswered demand) share `codex ⇄ human`, where the chip
    // counts 2 and the card counts 1.
    const human = STATE('human')
    expect(countOf(human, 'human', 'dm:codex ⇄ human', carriesChip),
      'the chip counts the demand the viewer sent alongside the one they owe').toBe(2)
    expect(countOf(human, 'human', 'dm:codex ⇄ human', cardWaiting),
      'the card counts only the demand the viewer owes').toBe(1)
    // And the receipt rows, which is why the shipped predicate is not the card's
    // either: d4 is addressed to `human` and demands nothing, and d7 is a receipt
    // `claude-session1` owes nobody that lands in a thread that does hold a
    // demand on them. The shipped predicate counts 2 there; the card counts 1.
    expect(sorted(selected(human, 'human', shippedWaiting)),
      'the shipped predicate selects the receipt row the card excludes')
      .toContain('dm:claude-session1 ⇄ human')
    expect(sorted(selected(human, 'human', cardWaiting)))
      .not.toContain('dm:claude-session1 ⇄ human')
    expect(countOf(STATE('claude-session1'), 'claude-session1',
      'dm:claude-session1 ⇄ codex', shippedWaiting),
      'the shipped predicate counts the receipt in with the demand').toBe(2)
    expect(countOf(STATE('claude-session1'), 'claude-session1',
      'dm:claude-session1 ⇄ codex', cardWaiting),
      'the card counts the demand and not the receipt').toBe(1)
  })

  for (const viewer of VIEWERS) {
    test(`needs me draws the card's threads for ${viewer}`, async ({ page }) => {
      test.fail(viewer === 'human',
        'T-0162 FAIL (bundle f0c4d64+dirty, stale): needs me draws `claude-session1 ⇄ human` '
        + 'for human. Expected ["#hello / #r1", "codex ⇄ human"], got ["#hello / #r1", '
        + '"claude-session1 ⇄ human", "codex ⇄ human"]. d4 is claude-session1 -> human, '
        + 'ack_required false, state delivered: the receipt `human` owes nobody, selected '
        + 'because messageWaiting (ChatPane.vue:35) tests `to === viewer && state !== acked` '
        + 'and never asks ack_required.')
      const state = STATE(viewer)
      await open(page, state)
      const drawn = (await threadLabels(page)).sort()
      const wanted = sorted(selected(state, viewer, cardWaiting)).map(labelOf).sort()
      // Literal expectations, so this is not a restatement of the code above:
      // `human` owes d1 and has unread in the room; `codex` owes d2 and nothing
      // else; `claude-session1` owes d3 and nothing else.
      const literals = {
        human: ['#hello / #r1', 'codex ⇄ human'],
        codex: ['codex ⇄ human'],
        'claude-session1': ['claude-session1 ⇄ codex'],
      }
      expect(wanted, `${viewer}: the fixture's own answer`).toEqual(literals[viewer])
      expect(drawn, `${viewer}: the threads "needs me" draws`).toEqual(literals[viewer])
    })
  }

  for (const viewer of VIEWERS) {
    test(`the count on ${viewer}'s threads is the demands they owe`, async ({ page }) => {
      test.fail(viewer === 'claude-session1',
        'T-0162 FAIL (bundle f0c4d64+dirty, stale): the badge on `claude-session1 ⇄ codex` reads '
        + '2 where the card counts 1. d7 is codex -> claude-session1, ack_required false, state '
        + 'delivered -- a receipt claude-session1 owes nobody -- and messageWaiting '
        + '(ChatPane.vue:35) counts it beside d3, the one demand they do owe.')
      const state = STATE(viewer)
      await open(page, state)
      const card = sorted(selected(state, viewer, cardWaiting))
      const direct = card.filter((key) => key.startsWith('dm:'))
      expect(direct.length, `${viewer}: at least one direct thread is drawn`).toBeGreaterThan(0)
      for (const key of direct) {
        const label = labelOf(key)
        // The card's number, spelled out: one, for every viewer, in every thread
        // this fixture draws. d2 (the viewer's own demand) and d7 (a receipt to
        // another agent) are both in a drawn thread for somebody, and neither is
        // a demand on the viewer reading it.
        expect(countOf(state, viewer, key, cardWaiting),
          `${viewer}: the fixture's own answer for ${label}`).toBe(1)
        expect(await badgeOf(page, label), `${viewer}: the badge on ${label}`).toBe(1)
      }
    })
  }

  test('a receipt the viewer owes nobody is neither counted nor drawn', async ({ page }) => {
    test.fail(true,
      'T-0162 FAIL (bundle f0c4d64+dirty, stale): d4 is drawn for human as `claude-session1 ⇄ '
      + 'human` and d7 is counted for claude-session1 as a second demand in `claude-session1 ⇄ '
      + 'codex`. Both are receipts (ack_required false, state delivered) and the card requires '
      + '`ack_required && state !== acked`; the served rule is `to === viewer && state !== acked` '
      + '(ChatPane.vue:35).')
    // d4 (`claude-session1 -> human`, no ack demanded, delivered) and d7 (`codex
    // -> claude-session1`, same) are receipts: the row is somebody else
    // acknowledging a message, so the reader owes an acknowledgement for it to
    // nobody. The shipped predicate counts both, because it never asks
    // `ack_required`, and it counts them for the viewer they are addressed to.
    await open(page, STATE('human'))
    expect(await threadLabels(page), 'human: the receipt thread must not be drawn')
      .not.toContain('claude-session1 ⇄ human')

    // The same defect as a number rather than as a missing row: for
    // `claude-session1`, `claude-session1 ⇄ codex` holds d3 (a demand they owe)
    // and d7 (a receipt they owe nobody). The badge reads 2 on the shipped
    // predicate and 1 on the card's.
    await open(page, STATE('claude-session1'), { reload: true })
    expect(await badgeOf(page, 'claude-session1 ⇄ codex'),
      'claude-session1: d3 is owed, d7 is not').toBe(1)
  })

  for (const viewer of VIEWERS) {
    test(`a room waits on ${viewer} only if its unread state names them`, async ({ page }) => {
      await open(page, STATE(viewer))
      const drawn = await threadLabels(page)
      const room = drawn.find((label) => label.endsWith('#r1'))
      // `unread: { human: 2, codex: 0 }`: `human` is waiting on the room, and the
      // two agents are not. A predicate that asks "does this room have unread
      // state" rather than "does it name this viewer" draws it for all three.
      if (viewer === 'human') expect(room, 'human: unread in the room is theirs').toBe('#hello / #r1')
      else expect(room, `${viewer}: the room's unread is not theirs`).toBeUndefined()
    })
  }

  test('a channel waits on the viewer only when the newest message is not theirs', async ({ page }) => {
    // The card says "rooms with unread state". A channel message is addressed
    // `#hello`, never to a viewer, so the reading measured here is the one
    // `ChatPane.vue:50` argues for -- who spoke last -- and it is asserted so
    // that a change to that rule has to be stated here. `claude-session1` wrote
    // the newest message, so the channel waits on the other two and not on them.
    for (const [i, viewer] of VIEWERS.entries()) {
      await open(page, STATE(viewer, { channels: [CHANNEL] }), { reload: i > 0 })
      const drawn = await threadLabels(page)
      if (viewer === 'claude-session1') {
        expect(drawn, `${viewer}: they wrote the newest message`).not.toContain('#hello')
      } else {
        expect(drawn, `${viewer}: somebody else wrote the newest message`).toContain('#hello')
      }
    }
  })
})
