/**
 * T-0182 "after" probe. It executes the real `<script setup>` block of
 * `src/panes/OverviewPane.vue` -- read from disk, imports stubbed, nothing
 * copied by hand -- against the same fixtures the "before" probe used, and
 * prints what `recentConversations` now produces.
 *
 * Why it is done this way: the bundle 8777 serves is built by the coordinator
 * (`npm run build` is not mine to run), so the running page still holds the old
 * expression. What can be measured here is the code in the file, on the same
 * inputs; what cannot be measured here is the rendered DOM of the built bundle,
 * and the report says so.
 */
import { readFileSync } from 'node:fs'

const receiptRe = /^RECEIPT for\s+/
const stamp = (ts) => ts.replace(/[-:]/g, '')
const receipt = (ts, { from = 'codex', to = 'claude-session1' } = {}) => ({
  from, to, ts,
  subject: `RECEIPT for ${stamp(ts)}-${to}`,
  body: `${from} received ${stamp(ts)}-${to} from ${to}.\nbytes: 100\n`,
  msg_id: `${stamp(ts)}-${from}-receipt`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
})
const original = (ts) => ({
  from: 'claude-session1', to: 'codex', ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-codex`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
})
const note = (ts, i) => ({
  from: 'claude-session1', to: 'codex', ts, subject: `routine note ${i}`, body: 'nothing to do',
  msg_id: `${stamp(ts)}-note-${i}`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
})

const X = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z',
  '2026-09-22T00:03:00.000Z']
const Y = ['2026-09-22T00:03:30.000Z', '2026-09-22T00:03:40.000Z', '2026-09-22T00:03:50.000Z']

const FIXTURES = {
  'seven receipts, window holds 2 + 3 notes': [...X.map((ts) => receipt(ts)),
    note('2026-09-22T00:04:00.000Z', 1), note('2026-09-22T00:05:00.000Z', 2), note('2026-09-22T00:06:00.000Z', 3)],
  'seven receipts, window holds 5 of them': [
    original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'), original('2026-09-21T23:59:00.000Z'),
    ...X.map((ts) => receipt(ts))],
  'seven receipts, 15 notes after them': [...X.map((ts) => receipt(ts)),
    ...Array.from({ length: 15 }, (_, i) => note(`2026-09-22T00:${String(10 + i).padStart(2, '0')}:00.000Z`, 100 + i))],
  'two conversations, 7 + 3 receipts': [...X.map((ts) => receipt(ts)),
    ...Y.map((ts) => receipt(ts, { from: 'codex-orangement', to: 'human' }))],
}

// --- load the component's real script, with the framework stubbed out -------
const source = readFileSync('/root/tmp/agent-im/web/src/panes/OverviewPane.vue', 'utf8')
const script = /<script setup>([\s\S]*?)<\/script>/.exec(source)[1]
const body = script
  .split('\n')
  .filter((line) => !/^\s*import\s/.test(line))
  .join('\n')

const computed = (fn) => ({ get value() { return fn() } })
const ref = (value) => ({ value })
const stubFns = {
  computed, ref, inject: () => ({ service: () => ({}) }), useBoard: () => globalThis.__board,
  isPromise: (task) => (task?.provenance || '').includes('seed'),
  isOverdue: () => false, PRIORITY_TYPE: {}, STATUS_TYPE: {},
  RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {}, TaskLink: {},
  days: () => 0, today: () => '2026-09-22',
}
// A direct translation of the store's `conversationRows` (board.js:310-349).
// The getter is the coordinator's file, so the probe reads the same rule rather
// than a second one: flatten channels, rooms and mail, then sort by `ts`.
function conversationRows(mail) {
  const rows = []
  for (const m of mail) {
    rows.push({ ...m, shape: 'direct', scope: [m.from, m.to].map(String).sort().join(' ⇄ '), channel: null, room: null })
  }
  return rows.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
}

// `board` is not a parameter: the component's own `const board = useBoard()`
// declares it, and the stub above returns the current fixture.
const names = ['computed', 'ref', 'inject', 'useBoard', 'isPromise', 'isOverdue', 'PRIORITY_TYPE',
  'STATUS_TYPE', 'RouterLink', 'PhaseApprovalCard', 'PromiseTag', 'TaskLink', 'days', 'today']
const make = new Function(...names, `${body}\nreturn { recentConversations, receiptGroups, receiptedId, receiptRe }`)

const hasWindowSlice = /slice\(-5\)/.test(source)
console.log('source still contains a five-row window:', hasWindowSlice,
  '(the window decides which rows are drawn; it must not decide the count)')
console.log('source still has `receipts arrived`:', /receipts arrived/.test(source))

for (const [label, mail] of Object.entries(FIXTURES)) {
  globalThis.__board = { conversationRows: conversationRows(mail) }
  const { recentConversations } = make(...names.map((n) => stubFns[n]))
  const rows = recentConversations.value
  const out = rows.map((r) => ({
    subject: r.subject === r.subject && /receipts arrived/.test(r.subject || '')
      ? `${r.receiptCount} receipts arrived`
      : (receiptRe.test(r.subject || '') ? `raw: ${r.subject.slice(0, 34)}` : `row: ${r.subject}`),
    ts: (r.ts || '').slice(0, 16),
    links: r.receiptCount ? r.receipts.map((x) => x.id) : null,
  }))
  console.log(`\n${label}`)
  console.log('  payload receipts:', mail.filter((m) => receiptRe.test(m.subject || '')).length,
    '| rows drawn:', rows.length)
  for (const r of out) {
    console.log('   -', r.subject, '| date', r.ts,
      r.links ? `| names ${r.links.length} receipted ids, newest ${r.links[0]}, oldest ${r.links.at(-1)}` : '')
  }
}
