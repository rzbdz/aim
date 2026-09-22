/**
 * T-0182 independent adversarial verification.
 *
 * I am not the author of the change under test. I read the author's probe
 * (`probe-t0182-after.mjs`) and then wrote this one: the component-loading
 * mechanism is the same idea (execute the real `<script setup>` block read from
 * disk, imports stubbed) because that is the only way to run the component
 * without a build; every fixture, every assertion and the oracle are mine.
 *
 * The oracle is computed by brute force from the *stated intent* in the
 * docblock, NOT from the implementation: for every conversation key, walk the
 * WHOLE payload, count receipts, take the newest, decide absorption, then take
 * the newest five survivors. If the implementation and the oracle disagree on
 * any fixture, that is a finding.
 *
 * `board.conversationRows` is the store's OWN getter, loaded from disk (a copy
 * whose only edit is `../theme` -> the sibling copy), so no second flattening or
 * `directScope` implementation is written here.
 */
import { readFileSync } from 'node:fs'

const FILE = '/root/tmp/agent-im/web/src/panes/OverviewPane.vue'
const receiptRe = /^RECEIPT for\s+/
const TOP = 5

// ---------------------------------------------------------------- fixtures --
const T = (i) => `2026-09-22T00:${String(Math.floor(i / 60)).padStart(2, '0')}:${String(i % 60).padStart(2, '0')}.000Z`
const stamp = (ts) => String(ts).replace(/[-:]/g, '')

const mail = (ts, over = {}) => ({
  from: 'codex', to: 'claude-session1', ts,
  subject: `RECEIPT for ${stamp(ts)}-claude-session1`, body: 'received',
  msg_id: `${stamp(ts)}-codex-receipt`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
  ...over,
})
const ordinary = (ts, i, over = {}) => ({
  from: 'claude-session1', to: 'codex', ts, subject: `note ${i}`, body: 'nothing to do',
  msg_id: `${stamp(ts)}-note-${i}`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
  ...over,
})
const chanMsg = (ts, i, over = {}) => ({
  from: 'codex', to: '#hello', ts, subject: `channel note ${i}`, body: 'x',
  msg_id: `${stamp(ts)}-ch-${i}`, kind: 'note', ack_required: false, acked_at: '', bytes: 0, state: '',
  ...over,
})
const head = (ts, i) => ({
  from: 'claude-session1', to: '#hello', ts, subject: `header ${i}`, body: 'x',
  msg_id: `${stamp(ts)}-hdr-${i}`, kind: 'request', ack_required: false, acked_at: '', bytes: 0, state: '',
})

/** Build a `conversation` doc: `chans` is {channelId: [rows]} for channel shape. */
const conv = (rows, chans = {}, rooms = []) => ({
  conversation: {
    channels: Object.entries(chans).map(([id, messages]) => ({ id, messages, gated: false, rule: '' })),
    rooms, mail: rows, withheld: 0,
  },
})

const ALL = {
  // 1. the headline defect, restated as the author states it: a burst of
  //    receipts, then ordinary rows that push the burst out of the window
  'A. seven receipts, then fifteen ordinary rows (window holds none)': conv([
    ...Array.from({ length: 7 }, (_, i) => mail(T(i))),
    ...Array.from({ length: 15 }, (_, i) => ordinary(T(10 + i), 100 + i)),
  ]),
  // 2. the same burst with nothing after it: window holds all seven
  'B. seven receipts, nothing after them (window holds all seven)': conv(
    Array.from({ length: 7 }, (_, i) => mail(T(i)))),
  // 3. window holds the five newest of seven
  'C. seven receipts preceded by two ordinary rows (window holds five receipts)': conv([
    ordinary(T(1), 1), ordinary(T(2), 2), ...Array.from({ length: 7 }, (_, i) => mail(T(3 + i))),
  ]),
  // 4. the same pair in two shapes: channel message and direct message
  'D. channel receipt + direct receipt naming the same pair': conv(
    [mail(T(0))], { hello: [chanMsg(T(1), 1, { subject: 'RECEIPT for chid-1' })] }),
  // 4b. a *collapsible* channel group, plus a direct receipt for the same pair
  'D2. channel group of 2 collapses + direct receipt for the same pair': conv(
    [mail(T(2))],
    { hello: [chanMsg(T(0), 1, { subject: 'RECEIPT for chid-1' }),
              chanMsg(T(1), 2, { subject: 'RECEIPT for chid-2' })] }),
  // 5. threadKey collision: the pair (`a`,`b`) and (`a`,`b ⇄ c`) -> 'dm:a ⇄ b'
  'E. threadKey collision: a/b vs a/(b ⇄ c)': conv([
    mail(T(0), { from: 'a', to: 'b', subject: 'RECEIPT for x1', msg_id: 'r1' }),
    mail(T(1), { from: 'a', to: 'b ⇄ c', subject: 'RECEIPT for x2', msg_id: 'r2' }),
  ]),
  // 5. threadKey collision, built correctly this time: `directScope` sorts the
  //    two names, so the pair (`a ⇄ b`, `c`) and the pair (`a`, `b ⇄ c`) both
  //    become the string 'a ⇄ b ⇄ c'.
  'E3. real threadKey collision: (a ⇄ b,c) and (a,b ⇄ c)': conv([
    mail(T(0), { from: 'a', to: 'b ⇄ c', subject: 'RECEIPT for pair-one', msg_id: 'k1' }),
    mail(T(1), { from: 'a ⇄ b', to: 'c', subject: 'RECEIPT for pair-two', msg_id: 'k2' }),
  ]),
  // 5c. the collision with three rows, so one conversation's receipt is inside
  //     the window and the other's is outside it
  'E4. collision, one member outside the window': conv([
    mail(T(0), { from: 'a ⇄ b', to: 'c', subject: 'RECEIPT for pair-two', msg_id: 'k2' }),
    mail(T(1), { from: 'x', to: 'y', subject: 'RECEIPT for unrelated', msg_id: 'k3' }),
    mail(T(2), { from: 'x', to: 'y', subject: 'RECEIPT for unrelated-2', msg_id: 'k4' }),
    mail(T(3), { from: 'x', to: 'y', subject: 'RECEIPT for unrelated-3', msg_id: 'k5' }),
    mail(T(4), { from: 'x', to: 'y', subject: 'RECEIPT for unrelated-4', msg_id: 'k6' }),
    mail(T(5), { from: 'a', to: 'b ⇄ c', subject: 'RECEIPT for pair-one', msg_id: 'k1' }),
  ]),
  // 6. an exact tie on ts inside one group
  'F. exact tie on ts (first row should be held)': conv([
    mail(T(0), { subject: 'RECEIPT for FIRST', msg_id: 'aaa', ts: T(5) }),
    mail(T(1), { subject: 'RECEIPT for SECOND', msg_id: 'zzz', ts: T(5) }),
  ]),
  // 7. missing / empty / non-string ts
  'G. receipts with ts "" and ts undefined': conv([
    mail(T(0), { subject: 'RECEIPT for empty-ts', msg_id: 'e', ts: '' }),
    mail(T(1), { subject: 'RECEIPT for no-ts', msg_id: 'n', ts: undefined }),
    mail(T(2), { subject: 'RECEIPT for dated', msg_id: 'd', ts: T(9) }),
  ]),
  // 7b. every receipt of the group has an empty ts
  'G2. group whose receipts all have ts ""': conv([
    mail(T(0), { subject: 'RECEIPT for a', msg_id: 'a', ts: '' }),
    mail(T(1), { subject: 'RECEIPT for b', msg_id: 'b', ts: '' }),
    mail(T(2), { subject: 'RECEIPT for c', msg_id: 'c', ts: '' }),
  ]),
  // 8. no subject / blank subject
  'H. rows with undefined and blank subject among receipts': conv([
    mail(T(0), { subject: undefined, msg_id: 'u' }),
    mail(T(1), { subject: '', msg_id: 'b' }),
    mail(T(2), { subject: 'RECEIPT for real', msg_id: 'r' }),
  ]),
  // 9. the group's newest receipt is OUTSIDE the window, older ones inside
  'I. newest receipt outside the window, five older ones inside': conv([
    ...Array.from({ length: 5 }, (_, i) => mail(T(i))),        // group of 6
    ...Array.from({ length: 5 }, (_, i) => ordinary(T(20 + i), 200 + i)),
    mail(T(40)),                                               // newest, outside window
  ]),
  // 9b. same, but the row just outside is a *different* conversation
  'I2. newest receipt outside window belongs to every group': conv([
    ...Array.from({ length: 4 }, (_, i) => mail(T(i))),
    ...Array.from({ length: 4 }, (_, i) => mail(T(10 + i), { from: 'a', to: 'b' })),
    ...Array.from({ length: 8 }, (_, i) => ordinary(T(20 + i), 300 + i)),
    mail(T(40)), mail(T(41), { from: 'a', to: 'b' }),
  ]),
  // 10. more than five rows of one group
  'J. nine receipts of one group only': conv(Array.from({ length: 9 }, (_, i) => mail(T(i)))),
  // 11. one counted group + one single receipt (must stay raw) + ordinary
  'K. group of 3 + lone receipt + ordinary row': conv([
    mail(T(0)), mail(T(1)), mail(T(2)),
    mail(T(3), { from: 'a', to: 'b' }),
    ordinary(T(4), 1),
  ]),
  // 11b. lone receipt of its group is inside the window while an older group
  //      member is outside it
  'K2. lone-receipt path with old group members outside the window': conv([
    mail(T(0)), mail(T(1)), mail(T(2)),
    ...Array.from({ length: 5 }, (_, i) => ordinary(T(20 + i), 400 + i)),
    mail(T(40), { from: 'a', to: 'b' }),
    mail(T(41), { from: 'a', to: 'b', id: 'SIBLING-OUTSIDE-WINDOW' }),
  ]),
  // 12. the same ts in two different groups
  'L. same ts in two different groups': conv([
    mail(T(0), { subject: 'RECEIPT for one', msg_id: 'o', ts: T(5) }),
    mail(T(1), { subject: 'RECEIPT for two', msg_id: 't', ts: T(5), from: 'a', to: 'b' }),
  ]),
  // 13. a group of 2 plus an ordinary row in the SAME conversation
  'M. ordinary row inside the receipted conversation': conv([
    mail(T(0)), mail(T(1)), ordinary(T(2), 1),
  ]),
  // 14. mixed ts formats in one group (date-only vs full datetime)
  'N. mixed ts formats in one group': conv([
    mail(T(0), { subject: 'RECEIPT for dateonly', msg_id: 'd1', ts: '2026-09-22' }),
    mail(T(1), { subject: 'RECEIPT for full', msg_id: 'f1', ts: '2026-09-22T00:05:00.000Z' }),
  ]),
  // 15. a receipt id that is only whitespace / a bare prefix
  'O. subject "RECEIPT for " with no id': conv([
    mail(T(0), { subject: 'RECEIPT for ', msg_id: 'ws' }),
    mail(T(1), { subject: 'RECEIPT for real', msg_id: 'r' }),
  ]),
  // 16. lowercase / leading-space subject (the regex is anchored, case-sensitive)
  'P. lowercase "receipt for" is not a receipt by this regex': conv([
    mail(T(0), { subject: 'receipt for lower', msg_id: 'l' }),
    mail(T(1), { subject: ' RECEIPT for spaced', msg_id: 's' }),
    mail(T(2), { subject: 'RECEIPT for upper', msg_id: 'u' }),
  ]),
  // 17. a channel group where every receipt is in the window and a channel
  //     ordinary row sits beside them
  'Q. channel group of 4 + channel ordinary row': conv([], { hello: [
    chanMsg(T(0), 1, { subject: 'RECEIPT for c1' }),
    chanMsg(T(1), 2, { subject: 'RECEIPT for c2' }),
    chanMsg(T(2), 3, { subject: 'RECEIPT for c3' }),
    chanMsg(T(3), 4, { subject: 'RECEIPT for c4' }),
    chanMsg(T(4), 5),
  ] }),
  // 18. the `room` shape: threadKey is `room:<channel>/<room>` while ChatPane
  //     keys rooms as `room:<channel>:<room>`. Two receipts in one room, so the
  //     group is collapsible, and an ordinary room row beside them that must not
  //     be swallowed.
  'R. room group of 2 + a room ordinary row': conv([], {}, [{
    id: 'r1', channel: 'hello', visibility: 'open',
    messages: [
      chanMsg(T(0), 1, { subject: 'RECEIPT for rm1', room: 'r1' }),
      chanMsg(T(1), 2, { subject: 'RECEIPT for rm2', room: 'r1' }),
      chanMsg(T(2), 3, { room: 'r1' }),
    ],
  }]),
  // 19. the same pair twice in one payload: an exact duplicate row. `msg_id` is
  //     what the template keys on, so a duplicate is one row rendered twice.
  'S. byte-identical duplicate rows': conv([
    mail(T(0), { subject: 'RECEIPT for dup', msg_id: 'DUP' }),
    mail(T(0), { subject: 'RECEIPT for dup', msg_id: 'DUP' }),
    mail(T(1), { subject: 'RECEIPT for dup', msg_id: 'DUP' }),
  ]),
  // 20. a whole group sharing one `ts`: the only way (given the store sorts by
  //     ts) for a group's designated `latest` to fall outside the window while
  //     older members of the same group are inside it.
  'T. six receipts all at the same ts': conv(
    Array.from({ length: 6 }, (_, i) => mail(T(5), { subject: `RECEIPT for tie-${i}`, msg_id: `t${i}` }))),
  // 20b. the same, five of them: `latest` is the first row and stays inside
  'T2. five receipts all at the same ts': conv(
    Array.from({ length: 5 }, (_, i) => mail(T(5), { subject: `RECEIPT for tie-${i}`, msg_id: `t${i}` }))),
  // 20c. six at one ts with one newer row after them
  'T3. six at one ts, one newer row after': conv([
    ...Array.from({ length: 6 }, (_, i) => mail(T(5), { subject: `RECEIPT for tie-${i}`, msg_id: `t${i}` })),
    ordinary(T(9), 1),
  ]),
}

// ------------------------------------------------------------------ loader --
function loadComponent() {
  const source = readFileSync(FILE, 'utf8')
  const script = /<script setup>([\s\S]*?)<\/script>/.exec(source)[1]
  const body = script.split('\n').filter((line) => !/^\s*import\s/.test(line)).join('\n')
  const computed = (fn) => ({ get value() { return fn() } })
  const ref = (value) => ({ value })
  const stub = {
    computed, ref, inject: () => ({ service: () => ({}) }), useBoard: () => globalThis.__board,
    isPromise: (t) => (t?.provenance || '').includes('seed'),
    isOverdue: () => false, PRIORITY_TYPE: {}, STATUS_TYPE: {},
    RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {}, TaskLink: {},
    days: () => 0, today: () => '2026-09-22',
  }
  const names = Object.keys(stub)
  const make = new Function(...names,
    `${body}\nreturn { recentConversations, receiptGroups, receiptedId, threadKey }`)
  return { source, make, names, stub }
}

async function realStore() {
  const { createPinia, setActivePinia } = await import('pinia')
  setActivePinia(createPinia())
  return import('/root/tmp/agent-im/web/.verifier-imports/board.js')
}

// ------------------------------------------------------------------- oracle --
/**
 * Two keys per row, deliberately different.
 *
 * `keyOf` is the group identity the CARD uses -- built from the row's `scope`
 * field, which is what the component's `threadKey` reads (a fact verified by
 * reading the component, not assumed: `threadKey` returns `dm:${scope}` for a
 * direct row). Using the same key here means an oracle disagreement is about the
 * window/absorption logic, not about which pair a row belongs to.
 *
 * `truePair` is the pair the row is *between*, from the row's own fields. When
 * two rows in the payload have different `truePair` but the same `keyOf`, the
 * card has merged two conversations, and one of them is counted against the
 * other. That is reported separately, by name, rather than folded into the row
 * comparison.
 */
const keyOf = (r) => (r.shape === 'channel' ? `ch:${r.channel}`
  : r.shape === 'room' ? `room:${r.channel}/${r.room}` : `dm:${r.scope}`)
const truePair = (r) => `dm:${[String(r.from), String(r.to)].sort().join('|')}`

/**
 * Brute force, from the docblock's stated intent.
 *
 * The window is taken FIRST (`rows.slice(-5)`), then its rows are absorbed,
 * because that is what both the old expression and the docblock's "there is no
 * row to draw it on" say the card is: a window over the record. Collapsing first
 * and then slicing would resurrect rows the window has already passed, which is
 * a different card; that variant is measured separately below.
 */
function oracle(rows) {
  const groups = new Map()
  for (const r of rows) {
    if (!receiptRe.test(r.subject || '')) continue
    const k = keyOf(r)
    const g = groups.get(k) || { size: 0, latest: null, ids: [] }
    g.size += 1
    g.ids.push((r.subject || '').replace(receiptRe, '').trim())
    if (!g.latest || (r.ts || '') > (g.latest.ts || '')) g.latest = r
    groups.set(k, g)
  }
  const inWindow = rows.slice(-TOP)
  const drawn = []
  for (const r of inWindow.slice().reverse()) {
    if (!receiptRe.test(r.subject || '')) { drawn.push(r); continue }
    const g = groups.get(keyOf(r))
    if (!g || g.size <= 1) { drawn.push(r); continue }
    if (r !== g.latest) continue
    drawn.push(Object.assign({}, r, { __count: g.size, __ids: g.ids }))
  }
  return { groups, drawn }
}

// ------------------------------------------------------------------ runner --
const { make, names, stub, source } = loadComponent()
const storeMod = await realStore()
const failures = []
const verbose = process.argv.includes('-v')

const brief = (r) => `${r.ts} ${keyOf(r)} :: ${r.receiptCount ? `[count ${r.receiptCount}] ` : ''}${JSON.stringify(r.subject)}${r.receipts ? ' links=' + r.receipts.map((x) => x.id).join(',') : ''}`

/**
 * What the card DRAWs, taken from the stated intent rather than from the
 * implementation: the question is "would a reader see the same thing", so the
 * card's own copy of a row is drawn as itself (a fresh object is what the DOM
 * needs), while the collapsed row is drawn as the count plus the ids behind it.
 * The label is deliberately NOT compared -- "N receipts arrived" is the title.
 */
const projection = (r) => (r.receiptCount
  ? { count: r.receiptCount, ts: r.ts, key: keyOf(r), ids: (r.receipts || []).map((x) => x.id).sort() }
  : { count: 0, ts: r.ts, key: keyOf(r), subject: r.subject })
const wantProjection = (r) => (r.__count
  ? { count: r.__count, ts: r.ts, key: keyOf(r), ids: r.__ids.slice().sort() }
  : { count: 0, ts: r.ts, key: keyOf(r), subject: r.subject })

for (const [label, doc] of Object.entries(ALL)) {
  const board = storeMod.useBoard()
  board.doc = doc
  globalThis.__board = board
  const rows = board.conversationRows
  if (!rows.length) { failures.push(`${label}: FIXTURE EMPTY, probe would be vacuous`); continue }
  const { recentConversations, receiptGroups, receiptedId } = make(...names.map((n) => stub[n]))
  const got = recentConversations.value
  const want = oracle(rows).drawn
  // Two separate questions, so a finding can say which one broke:
  //   - WHICH rows the five-row window selects (identity: ts + msg_id);
  //   - what the drawn row says once selected.
  const idn = (r) => `${r.ts}|${r.msg_id}`
  const gotIds = got.map(idn)
  const wantIds = want.map(idn)
  const sameSelection = JSON.stringify(gotIds) === JSON.stringify(wantIds)
  const sameContent = JSON.stringify(got.map(projection)) === JSON.stringify(want.map(wantProjection))
  if (!sameSelection) {
    failures.push(`${label}: window selection differs from oracle`)
  } else if (!sameContent) {
    failures.push(`${label}: drawn row content differs from oracle`)
  }

  if (verbose || !sameSelection || !sameContent) {
    console.log(`\n### ${label}`)
    console.log(`  payload: ${rows.length} rows, ${rows.filter((r) => receiptRe.test(r.subject || '')).length} receipts`)
    for (const r of rows) console.log(`   payload: ${r.ts} ${keyOf(r)} :: ${JSON.stringify(r.subject)}`)
    console.log(`  got  (${got.length}):`)
    for (const r of got) console.log(`   -> ${brief(r)}`)
    console.log(`  want (${want.length}):`)
    for (const r of want) console.log(`   -> ${r.ts} ${keyOf(r)} :: [count ${r.__count || 0}] ${JSON.stringify(r.subject)}`)
  }

  // Invariant 1: a collapsed count equals the whole-payload receipt count for
  // that conversation -- never the window's count.
  for (const r of got) {
    if (!r.receiptCount) continue
    const truth = rows.filter((x) => receiptRe.test(x.subject || '') && keyOf(x) === keyOf(r))
    if (r.receiptCount !== truth.length) {
      failures.push(`${label}: count ${r.receiptCount} != payload ${truth.length} for ${keyOf(r)}`)
    }
    // The row must be dated by its group's NEWEST receipt. (The popover's first
    // line is checked separately: the docblock promises "newest first", and on a
    // tie the group's `latest` and the reversed member list disagree, so that is
    // its own finding rather than a restatement of this one.)
    const newest = truth.map((x) => x.ts || '').sort().at(-1)
    if ((r.ts || '') !== newest) {
      failures.push(`${label}: drawn ts ${r.ts} is not the newest receipt ts ${newest} of ${keyOf(r)}`)
    }
    if (!r.receipts || r.receipts.length !== r.receiptCount) {
      failures.push(`${label}: row says ${r.receiptCount}, carries ${r.receipts?.length} links`)
    }
    // The id the card's own `latest` rule picked, recomputed from the payload
    // (the collapsed row's subject no longer carries it: it was rewritten).
    const latestRow = truth.reduce((best, x) => (!best || (x.ts || '') > (best.ts || '') ? x : best), null)
    const idTheCardDates = latestRow ? receiptedId(latestRow) : ''
    const idThePopoverOpensOn = (r.receipts || [])[0]?.id
    if (idThePopoverOpensOn !== idTheCardDates && idTheCardDates && idThePopoverOpensOn) {
      failures.push(`${label}: the card's newest is ${JSON.stringify(idTheCardDates)} but the popover's first line is ${JSON.stringify(idThePopoverOpensOn)} (tie on ts: the two "newest" rules disagree)`)
    }
    // The ids the reader can reach from this row: the popover's lines. They must
    // be exactly the payload's ids for this conversation -- a row that counts N
    // and names M < N leaves the reader a number with nothing behind it.
    const shown = new Set((r.receipts || []).map((x) => x.id))
    const held = new Set(truth.map((x) => receiptedId(x)))
    const missing = [...held].filter((id) => !shown.has(id))
    const extra = [...shown].filter((id) => !held.has(id))
    if (missing.length || extra.length) {
      failures.push(`${label}: count ${r.receiptCount} for ${keyOf(r)} names ${shown.size} ids; payload holds ${held.size} (missing ${JSON.stringify(missing)}, extra ${JSON.stringify(extra)})`)
    }
  }
  // Invariant 2: no raw `RECEIPT for ...` subject drawn beside a count for the
  // same conversation (the author's stated first-draft bug).
  for (const r of got) {
    if (!r.receiptCount) continue
    const rawSame = got.filter((o) => o !== r && receiptRe.test(o.subject || '') && keyOf(o) === keyOf(r))
    if (rawSame.length) failures.push(`${label}: raw RECEIPT rows drawn beside a count for ${keyOf(r)}: ${rawSame.map((o) => o.subject)}`)
  }
  // Invariant 3: nothing drawn that is not in the window, and nothing in the
  // window silently dropped. Identity is (ts, msg_id); a collapsed row is a copy
  // of its source row with the subject rewritten, so it keeps both.
  const idOf = (r) => `${r.ts}|${r.msg_id}`
  const inWindow = rows.slice(-TOP)
  const windowIds = new Set(inWindow.map(idOf))
  const drawnIds = new Set(got.map(idOf))
  for (const r of got) {
    if (!windowIds.has(idOf(r))) failures.push(`${label}: drew ${idOf(r)} (${JSON.stringify(r.subject)}), which is not in the five-row window`)
  }
  for (const r of inWindow) {
    const isReceipt = receiptRe.test(r.subject || '')
    const g = oracle(rows).groups.get(keyOf(r))
    const absorbed = isReceipt && g && g.size > 1 && r !== g.latest
    if (!absorbed && !drawnIds.has(idOf(r))) {
      failures.push(`${label}: window row ${idOf(r)} (${JSON.stringify(r.subject)}) was dropped`)
    }
    if (absorbed && drawnIds.has(idOf(r))) {
      failures.push(`${label}: absorbed receipt ${idOf(r)} was drawn raw beside the count`)
    }
  }
  // Invariant 4: row count. The card draws one row per surviving window row.
  const expectedRows = inWindow.filter((r) => {
    if (!receiptRe.test(r.subject || '')) return true
    const g = oracle(rows).groups.get(keyOf(r))
    return !(g && g.size > 1 && r !== g.latest)
  }).length
  if (got.length !== expectedRows) {
    failures.push(`${label}: drew ${got.length} rows, the window implies ${expectedRows}`)
  }

  // Invariant 5: one group key must not stand for two different pairs. When two
  // payload rows have different `truePair` but the same `keyOf`, the card is
  // counting one conversation's receipt against another's, and the "show them"
  // list names ids that never travelled in the thread the reader opens.
  const byKey = new Map()
  for (const r of rows) {
    if (!byKey.has(keyOf(r))) byKey.set(keyOf(r), new Set())
    byKey.get(keyOf(r)).add(truePair(r))
  }
  for (const [k, pairs] of byKey) {
    if (pairs.size > 1) {
      failures.push(`${label}: threadKey ${k} merges ${pairs.size} distinct pairs: ${[...pairs].join(' + ')}`)
    }
  }
}

console.log('\n================ summary ================')
console.log('fixtures:', Object.keys(ALL).length, '| failures:', failures.length)
for (const f of failures) console.log('  FAIL', f)
console.log('source still contains slice(-5):', /slice\(-5\)/.test(source))
