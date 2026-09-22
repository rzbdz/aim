/**
 * Standalone verification script (verifier, read-only): re-implements the pane's
 * `recentConversations` (both before and after the change) and the two specs'
 * fixtures, and prints the row counts / subjects / dates each expression yields.
 * No browser, no build, no server.
 */

const receiptRe = /^RECEIPT for\s+/
const receiptedId = (row) => (row.subject || '').replace(receiptRe, '').trim()
const directScope = (a, b) => [a, b].map(String).sort().join(' ⇄ ')
const threadKey = (m) => (m.shape === 'channel' ? `ch:${m.channel}`
  : m.shape === 'room' ? `room:${m.channel}/${m.room}` : `dm:${m.scope}`)

/** board.conversationRows for a mail-only payload (channels/rooms empty). */
const rowsOf = (mail) => mail
  .map((m) => ({ ...m, shape: 'direct', scope: directScope(m.from, m.to), channel: null, room: null }))
  .sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))

// --- the shipped expression (after the change) -------------------------------
function receiptGroups(convRows) {
  const byKey = new Map()
  for (const row of convRows) {
    if (!receiptRe.test(row.subject || '')) continue
    const key = threadKey(row)
    let group = byKey.get(key)
    if (!group) {
      group = { key, size: 0, latest: row, receipts: [] }
      byKey.set(key, group)
    }
    group.size += 1
    group.receipts.push({ id: receiptedId(row), from: row.from, ts: row.ts })
    if ((row.ts || '') > (group.latest.ts || '')) group.latest = row
  }
  for (const g of byKey.values()) g.receipts.reverse()
  return byKey
}

function recentAfter(convRows) {
  const groups = receiptGroups(convRows)
  const out = []
  for (const row of convRows.slice(-5).reverse()) {
    if (!receiptRe.test(row.subject || '')) { out.push(row); continue }
    const group = groups.get(threadKey(row))
    if (!group || group.size <= 1) { out.push(row); continue }
    if (row !== group.latest) continue
    out.push({ ...row, receiptCount: group.size, receipts: group.receipts,
               subject: `${group.size} receipts arrived` })
  }
  return out
}

// --- the expression this replaces (before the change) ------------------------
function recentBefore(convRows) {
  const rows = convRows.slice(-5).reverse()
  const receipts = rows.filter((row) => receiptRe.test(row.subject || ''))
  if (receipts.length <= 1) return rows
  const first = receipts[0]
  return rows
    .filter((row) => !receiptRe.test(row.subject || '') || row === first)
    .map((row) => (row === first
      ? { ...row, receiptCount: receipts.length, subject: `${receipts.length} receipts arrived` }
      : row))
}

// --- fixtures -----------------------------------------------------------------
const stamp = (ts) => ts.replace(/[-:]/g, '')
const receipt = (ts, { from = 'codex', to = 'claude-session1' } = {}) => ({
  from, to, ts, subject: `RECEIPT for ${stamp(ts)}-${to}`, msg_id: `${stamp(ts)}-${from}-receipt`,
  ack_required: false, acked_at: '', state: 'delivered',
})
const note = (ts, i) => ({
  from: 'claude-session1', to: 'codex', ts, subject: `routine note ${i}`, body: 'nothing to do',
  msg_id: `${stamp(ts)}-note-${i}`, ack_required: false, acked_at: '', state: 'delivered',
})
const original = (ts, { from = 'claude-session1', to = 'codex' } = {}) => ({
  from, to, ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-${from}`, ack_required: false, acked_at: '', state: 'delivered',
})

// card-t0182-receipt-window.spec.js
const BURST = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z',
  '2026-09-22T00:03:00.000Z'].map((ts) => receipt(ts))
const tail = (n) => Array.from({ length: n }, (_, i) => note(`2026-09-22T00:${String(10 + i).padStart(2, '0')}:00.000Z`, 100 + i))
const T0182 = [
  { name: 'BURST_ONLY', mail: [...BURST] },
  { name: 'PLUS_TWO', mail: [...BURST, ...tail(2)] },
  { name: 'PLUS_FOUR', mail: [...BURST, ...tail(4)] },
]

// receipts.spec.js
const X = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z',
  '2026-09-22T00:03:00.000Z']
const Y = ['2026-09-22T00:03:30.000Z', '2026-09-22T00:03:40.000Z', '2026-09-22T00:03:50.000Z']
const SPLIT_WINDOW = [...X.map((ts) => receipt(ts)),
  note('2026-09-22T00:04:00.000Z', 1), note('2026-09-22T00:05:00.000Z', 2), note('2026-09-22T00:06:00.000Z', 3)]
const TAIL_BURST = [original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'),
  original('2026-09-21T23:59:00.000Z'), ...X.map((ts) => receipt(ts))]
const TWO_PAIRS = [...X.map((ts) => receipt(ts)),
  ...Y.map((ts) => receipt(ts, { from: 'codex-orangement', to: 'human' }))]
const QUIET_TAIL = [...X.map((ts) => receipt(ts)),
  ...Array.from({ length: 15 }, (_, i) => note(`2026-09-22T00:${String(10 + i).padStart(2, '0')}:00.000Z`, 100 + i))]
const RECEIPTS_SPEC = [
  { name: 'SPLIT_WINDOW', mail: SPLIT_WINDOW },
  { name: 'TAIL_BURST', mail: TAIL_BURST },
  { name: 'TWO_PAIRS', mail: TWO_PAIRS },
  { name: 'QUIET_TAIL', mail: QUIET_TAIL },
]

const describe = (rows) => rows.map((r) => {
  const date = `${(r.ts || '').slice(0, 16).replace('T', ' ')}`
  return r.receiptCount
    ? `[COLLAPSED n=${r.receiptCount} subject="${r.subject}" date=${date} title="${(r.subject || '').slice(0, 20)}"]`
    : `[${r.shape} "${(r.subject || '').slice(0, 22)}" date=${date}${r.msg_id ? '' : ''}]`
})

function report(title, fixtures) {
  console.log(`\n================ ${title} ================`)
  for (const f of fixtures) {
    const conv = rowsOf(f.mail)
    const before = recentBefore(conv)
    const after = recentAfter(conv)
    console.log(`\n--- ${f.name} (mail ${f.mail.length}) ---`)
    console.log(`  BEFORE  rows=${before.length}: ${describe(before).join(' ')}`)
    console.log(`  AFTER   rows=${after.length}: ${describe(after).join(' ')}`)
    console.log(`  AFTER collapsed rows=${after.filter((r) => r.receiptCount).length} `
      + `collapsed counts=${JSON.stringify(after.filter((r) => r.receiptCount).map((r) => r.receiptCount))}`)
    for (const r of after.filter((x) => x.receiptCount)) {
      console.log(`    receipts newest-first: ${r.receipts.map((x) => x.id).join(', ')}`)
      console.log(`    row innerText-ish: "${r.from} ${r.scope} ${r.subject} · show them ${r.shape} ${(r.ts || '').slice(0, 16).replace('T', ' ')}"`)
    }
  }
}

report('card-t0182-receipt-window.spec.js fixtures', T0182)
report('receipts.spec.js fixtures', RECEIPTS_SPEC)

// What the committed spec asserts, evaluated against the measured row counts.
console.log('\n================ committed card-t0182 assertions ================')
for (const f of T0182) {
  const after = recentAfter(rowsOf(f.mail))
  const expected = Math.min(5, f.mail.length)
  console.log(`${f.name}: toHaveCount(Math.min(5, ${f.mail.length})=${expected}) -> measured ${after.length} `
    + `${after.length === expected ? 'PASS' : 'FAIL'}`)
}
const collapsedOf = (rows) => rows.filter((r) => r.receiptCount)
console.log('collapsed counts:', JSON.stringify(T0182.map((f) => collapsedOf(recentAfter(rowsOf(f.mail))).length)))
console.log('shownDate strings:', JSON.stringify(T0182.map((f) => {
  const c = collapsedOf(recentAfter(rowsOf(f.mail)))[0]
  return c ? /(\d{4}-\d{2}-\d{2} \d{2}:\d{2})/.exec(`${c.from} ${c.scope} ${c.subject} · show them ${c.shape} ${(c.ts || '').slice(0, 16).replace('T', ' ')}`)?.[1] : null
})))

console.log('\n================ receipts.spec.js assertions ================')
for (const f of RECEIPTS_SPEC) {
  const after = recentAfter(rowsOf(f.mail))
  const collapsed = collapsedOf(after)
  console.log(`${f.name}: rows=${after.length} collapsed=${collapsed.length} `
    + `counts=${JSON.stringify(collapsed.map((c) => c.receiptCount))} `
    + `notes=${after.filter((r) => !r.receiptCount && /routine note/.test(r.subject || '')).length} `
    + `rawReceiptsDrawn=${after.filter((r) => receiptRe.test(r.subject || '')).length}`)
  for (const c of collapsed) {
    console.log(`   collapsed scope="${c.scope}" date=${(c.ts || '').slice(0, 16).replace('T', ' ')} `
      + `ids0=${c.receipts[0]?.id} idsLast=${c.receipts[c.receipts.length - 1]?.id}`)
  }
}
