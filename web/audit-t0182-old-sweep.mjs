/**
 * Auditor's check of the report's section-1 "7 answers" table.
 *
 * Runs the OLD `recentConversations` (dbdd04e:web/src/panes/OverviewPane.vue) and
 * the NEW one (working tree) over the same fixture: seven receipts of one pair,
 * ts 00:00:00 .. 00:03:00, followed by n ordinary rows.
 *
 * Fixture construction follows probe-t0182-before.mjs: each of the seven receipts
 * is stamped at a whole minute -- RE(ts, i) builds the subject from
 * `20260922T00${i}000.000Z`, with i = 0..3, so the seven receipts carry FOUR
 * distinct ids (00, 01, 02, 03) and the three duplicated ids are 00, 01, 02.
 */
import { readFileSync } from 'node:fs'

const receiptRe = /^RECEIPT for\s+/
const RE = (ts, i) => ({
  from: 'codex', to: 'claude-session1', ts,
  subject: `RECEIPT for 20260922T00${i}000.000Z-claude-session1`,
  body: `codex received 20260922T00${i}000.000Z-claude-session1 from claude-session1.\nbytes: 100\n`,
  msg_id: `20260922T00${i}000.000Z-codex-receipt`,
  ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
})
// probe-t0182-before.mjs's own ts list: 00:00:00, 00:00:30, 00:01:00, 00:01:30,
// 00:02:00, 00:02:30, 00:03:00 -> mapped through RE(ts, i) with i = index => 0,0,1,1,2,2,3.
const RECEIPTS = [
  '2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z',
  '2026-09-22T00:03:00.000Z',
].map(RE)
const OLD_NOISE = Array.from({ length: 3 }, (_, i) => ({
  from: 'claude-session1', to: 'codex', ts: `2026-09-21T23:5${i}:00.000Z`,
  subject: `routine note ${i}`, body: 'nothing to do', msg_id: `old-${i}`,
  ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
}))
// probe-t0182-before.mjs builds NEW_NOISE at 00:1X:00 with subjects `routine note 100+X`.
const NEW_NOISE = Array.from({ length: 15 }, (_, i) => ({
  from: 'claude-session1', to: 'codex', ts: `2026-09-22T00:1${String(i).padStart(2, '0')}:00.000Z`,
  subject: `routine note ${i + 100}`, body: 'nothing to do', msg_id: `new-${i}`,
  ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
}))

const rowsOf = (mail) => mail
  .map((m) => ({ ...m, shape: 'direct', scope: [m.from, m.to].map(String).sort().join(' ⇄ ') }))
  .sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))

const scriptOf = (file) => {
  const src = /<script setup>([\s\S]*?)<\/script>/.exec(readFileSync(file, 'utf8'))[1]
  return src.split('\n').filter((line) => !/^\s*import\s/.test(line)).join('\n')
}
const stubs = {
  computed: (fn) => ({ get value() { return fn() } }),
  ref: (v) => ({ value: v }), inject: () => ({ service: () => ({}) }),
  useBoard: () => globalThis.__board,
  isPromise: () => false, isOverdue: () => false, PRIORITY_TYPE: {}, STATUS_TYPE: {},
  RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {}, TaskLink: {},
  days: () => 0, today: () => '2026-09-22',
}
const names = Object.keys(stubs)
const build = (file) => new Function(...names,
  `${scriptOf(file)}\nreturn { recentConversations }`)(...names.map((n) => stubs[n]))

const OLD = build('/tmp/old-OverviewPane.vue')
const NEW = build('/root/tmp/agent-im/web/src/panes/OverviewPane.vue')

console.log('OLD expression: 7 receipts, then n ordinary rows')
console.log('  the seven receipt ids, in ts order:',
  RECEIPTS.map((r) => r.subject.replace(receiptRe, '').trim()).join(' '))
for (let n = 0; n <= 7; n += 1) {
  const mail = [...OLD_NOISE, ...RECEIPTS, ...NEW_NOISE.slice(0, n)]
  const boardRows = rowsOf(mail)
  globalThis.__board = { conversationRows: boardRows }
  const oldRows = build('/tmp/old-OverviewPane.vue').recentConversations.value
  const newRows = build('/root/tmp/agent-im/web/src/panes/OverviewPane.vue').recentConversations.value
  const fmt = (rows) => rows.map((r) => (r.receiptCount ? `${r.receiptCount} receipts arrived`
    : receiptRe.test(r.subject || '') ? `RAW: ${r.subject.replace(receiptRe, '').trim()}` : r.subject))
  console.log(`  ordinary -- ${n}`)
  console.log(`    OLD rows: ${JSON.stringify(fmt(oldRows))}`)
  console.log(`    NEW rows: ${JSON.stringify(fmt(newRows))}`)
  // the two things the report claims about the date of the collapsed row
  const oldFirst = oldRows.find((r) => r.receiptCount)
  const newFirst = newRows.find((r) => r.receiptCount)
  if (oldFirst) console.log(`    OLD collapsed row from=${oldFirst.from} ts=${oldFirst.ts} subject=${oldFirst.subject.replace(receiptRe, '').trim()}`)
  if (newFirst) console.log(`    NEW collapsed row from=${newFirst.from} ts=${newFirst.ts} names=${newFirst.receipts.map((x) => x.id).join(',')}`)
}

// The identity question the report pushes back on: with `receipts.length > 1`, is
// the surviving row the NEWEST or the EARLIEST receipt of the window?
console.log('\nidentity / which member survives (n = 0, window = the whole burst):')
const mail0 = [...OLD_NOISE, ...RECEIPTS]
const boardRows = rowsOf(mail0)
const window = boardRows.slice(-5).reverse()
const receiptsInWindow = window.filter((r) => receiptRe.test(r.subject || ''))
console.log('  window size:', window.length, '| receipts in window:', receiptsInWindow.length)
console.log('  receiptsInWindow[0] is the', window.indexOf(receiptsInWindow[0]) === 0 ? 'NEWEST' : 'not-newest',
  'row of the window -> ts', receiptsInWindow[0].ts, 'id', receiptsInWindow[0].subject.replace(receiptRe, '').trim())
console.log('  receiptsInWindow[last] -> ts', receiptsInWindow.at(-1).ts,
  'id', receiptsInWindow.at(-1).subject.replace(receiptRe, '').trim())
