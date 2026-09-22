/**
 * Cross-check: run the fixtures that `tests/receipts.spec.js` literally defines
 * through the component's real `recentConversations`, so every count and date
 * asserted in that file is derived here rather than trusted.
 *
 * The spec's helper section is evaluated as it is written (its `test`/`expect`
 * uses are stubbed), so a fixture edited in the spec is picked up here without a
 * second copy of the data existing anywhere.
 */
import { readFileSync } from 'node:fs'

const specPath = '/root/tmp/agent-im/web/tests/receipts.spec.js'
const source = readFileSync(specPath, 'utf8')
const helpers = source.slice(0, source.indexOf('test.describe('))
  .replace(/^import .*$/gm, '')

const fixtureKeys = ['BURST', 'LATE', 'SPLIT_WINDOW', 'TAIL_BURST', 'TWO_PAIRS', 'QUIET_TAIL']
const fixtures = new Function('expect', 'test',
  `${helpers}\nreturn { ${fixtureKeys.join(', ')}, stamp }`)(() => {}, {})

const script = /<script setup>([\s\S]*?)<\/script>/.exec(
  readFileSync('/root/tmp/agent-im/web/src/panes/OverviewPane.vue', 'utf8'))[1]
const body = script.split('\n').filter((line) => !/^\s*import\s/.test(line)).join('\n')
const computed = (fn) => ({ get value() { return fn() } })
const stubs = {
  computed, ref: (v) => ({ value: v }), inject: () => ({ service: () => ({}) }),
  useBoard: () => globalThis.__board,
  isPromise: () => false, isOverdue: () => false, PRIORITY_TYPE: {}, STATUS_TYPE: {},
  RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {}, TaskLink: {},
  days: () => 0, today: () => '2026-09-22',
}
const names = Object.keys(stubs)
const make = new Function(...names,
  `${body}\nreturn { recentConversations, receiptGroups }`)
// Built per fixture: the component's `const board = useBoard()` is evaluated when
// the script block runs, so the fixture has to be in place before that.
const build = () => make(...names.map((n) => stubs[n]))

// board.js:310-349, the store rule the pane reads.
const rowsOf = (mail) => mail
  .map((m) => ({ ...m, shape: 'direct', scope: [m.from, m.to].map(String).sort().join(' ⇄ ') }))
  .sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))

const receiptRe = /^RECEIPT for\s+/
const expectRows = {
  SPLIT_WINDOW: { rows: 4, receipts: 7, date: '2026-09-22 00:03', notes: 3 },
  TAIL_BURST: { rows: 1, receipts: 7, date: '2026-09-22 00:03', notes: 0 },
  TWO_PAIRS: { rows: 2, receipts: 10, date: '2026-09-22 00:03', notes: 0 },
  QUIET_TAIL: { rows: 5, receipts: 7, date: null, notes: 5 },
}

let bad = 0
for (const key of Object.keys(expectRows)) {
  const payload = fixtures[key]
  const payloadReceipts = payload.filter((m) => receiptRe.test(m.subject || '')).length
  globalThis.__board = { conversationRows: rowsOf(payload) }
  const api = build()
  const rows = api.recentConversations.value
  const counted = rows.filter((r) => r.receiptCount)
  const notes = rows.filter((r) => /routine note/.test(r.subject || '')).length
  const raw = rows.filter((r) => receiptRe.test(r.subject || '')).length
  const date = counted.length ? (counted[0].ts || '').slice(0, 16).replace('T', ' ') : null
  const want = expectRows[key]
  const ok = rows.length === want.rows && notes === want.notes && raw === 0
    && date === want.date && payloadReceipts === want.receipts
    && counted.every((c) => c.receipts.length === c.receiptCount)
  if (!ok) bad += 1
  console.log(`${ok ? 'ok  ' : 'BAD '} ${key.padEnd(13)}`,
    `rows ${rows.length}/${want.rows}`, `notes ${notes}/${want.notes}`,
    `date ${date || '-'}/${want.date || '-'}`, `raw receipts drawn ${raw}`,
    `payload receipts ${payloadReceipts}/${want.receipts}`,
    counted.length ? `count ${counted[0].receiptCount} lists ${counted[0].receipts.length}` : '')
}

// The two assertions that are about the *set* of counts, not one row.
globalThis.__board = { conversationRows: rowsOf(fixtures.TWO_PAIRS) }
const counts = build().recentConversations.value.filter((r) => r.receiptCount)
  .map((r) => `${r.receiptCount} receipts arrived`).sort()
console.log('TWO_PAIRS counts:', JSON.stringify(counts),
  JSON.stringify(counts) === JSON.stringify(['3 receipts arrived', '7 receipts arrived']) ? 'ok' : 'BAD')

console.log(bad ? `${bad} fixture(s) disagree with the spec` : 'every spec fixture checked out')
