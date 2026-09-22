/**
 * Auditor: does the report's §4 store getter reproduce the pane's own grouping?
 *
 * Extracts the `receiptGroups(s)` body verbatim from /tmp/aim-tasks/reports/T-0182.md
 * (§4 fenced block), rewrites `this.` to a local, runs it against the spec's own
 * fixtures, and diffs the full group contents against the pane's local
 * `receiptGroups` computed (whose `threadKey` is mirrored from the pane).
 */
import { readFileSync } from 'node:fs'

const report = readFileSync('/tmp/aim-tasks/reports/T-0182.md', 'utf8')
const fence = /```js\n([\s\S]*?)```/.exec(report)
const getterSrc = fence[1]
console.log('getter bytes:', getterSrc.length)

const inner = getterSrc.slice(getterSrc.indexOf('{') + 1, getterSrc.lastIndexOf('}'))
const runGetter = new Function('ROWS', `
  const self = { conversationRows: ROWS }
  ${inner.replace(/\bthis\./g, 'self.')}
`)
void runGetter

// --- the pane's own computed, from the real file -------------------------
const script = /<script setup>([\s\S]*?)<\/script>/.exec(
  readFileSync('/root/tmp/agent-im/web/src/panes/OverviewPane.vue', 'utf8'))[1]
const body = script.split('\n').filter((line) => !/^\s*import\s/.test(line)).join('\n')
const stubs = {
  computed: (fn) => ({ get value() { return fn() } }),
  ref: (v) => ({ value: v }), inject: () => ({ service: () => ({}) }),
  useBoard: () => globalThis.__board,
  isPromise: () => false, isOverdue: () => false, PRIORITY_TYPE: {}, STATUS_TYPE: {},
  RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {}, TaskLink: {},
  days: () => 0, today: () => '2026-09-22',
}
const names = Object.keys(stubs)
const paneGroups = (rows) => {
  globalThis.__board = { conversationRows: rows }
  const api = new Function(...names, `${body}\nreturn { receiptGroups }`)(...names.map((n) => stubs[n]))
  return api.receiptGroups.value
}
// The pane's own threadKey, copied verbatim from OverviewPane.vue:218-222.
const threadKey = (message) => {
  if (message.shape === 'channel') return `ch:${message.channel}`
  if (message.shape === 'room') return `room:${message.channel}/${message.room}`
  return `dm:${message.scope}`
}

const spec = readFileSync('/root/tmp/agent-im/web/tests/receipts.spec.js', 'utf8')
const helpers = spec.slice(0, spec.indexOf('test.describe(')).replace(/^import .*$/gm, '')
const fixtures = new Function('expect', 'test',
  `${helpers}\nreturn { BURST, SPLIT_WINDOW, TAIL_BURST, TWO_PAIRS, QUIET_TAIL }`)(() => {}, {})
const rowsOf = (mail) => mail
  .map((m) => ({ ...m, shape: 'direct', scope: [m.from, m.to].map(String).sort().join(' ⇄ '), channel: null, room: null }))
  .sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))

const shape = (map) => [...map.entries()].map(([k, g]) => ({
  key: k, size: g.size, latest: g.latest.ts,
  ids: g.receipts.map((r) => `${r.id}|${r.ts}|${r.from}|${r.msg_id}`),
})).sort((a, b) => (a.key < b.key ? -1 : 1))

let bad = 0
for (const [key, mail] of Object.entries(fixtures)) {
  const rows = rowsOf(mail)
  const a = JSON.stringify(shape(runGetter(rows)))
  const b = JSON.stringify(shape(paneGroups(rows)))
  const same = a === b
  if (!same) bad += 1
  console.log(`${same ? 'SAME ' : 'DIFF '} ${key}`)
  if (!same) { console.log('  getter:', a); console.log('  pane  :', b) }
}

// And the live payload, where threadKey is exercised for real shapes.
const state = JSON.parse(readFileSync('/tmp/aim-tasks/state-flow.json', 'utf8')).conversation || {}
const liveRows = []
for (const ch of state.channels || []) for (const m of ch.messages || []) liveRows.push({ ...m, shape: 'channel', scope: ch.id, channel: ch.id, room: null })
for (const rm of state.rooms || []) for (const m of rm.messages || []) liveRows.push({ ...m, shape: 'room', scope: `${rm.channel}/${rm.id}`, channel: rm.channel, room: rm.id })
for (const m of state.mail || []) liveRows.push({ ...m, shape: 'direct', scope: [m.from, m.to].map(String).sort().join(' ⇄ '), channel: null, room: null })
liveRows.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
const la = JSON.stringify(shape(runGetter(liveRows)))
const lb = JSON.stringify(shape(paneGroups(liveRows)))
console.log(`${la === lb ? 'SAME ' : 'DIFF '} live state-flow payload (${liveRows.length} rows)`)
if (la !== lb) { console.log('  getter:', la.slice(0, 400)); console.log('  pane  :', lb.slice(0, 400)) }
// Cross-check the pane's map key against the pane's own threadKey for each group.
const pg = paneGroups(liveRows)
console.log('keys match threadKey(row) for the group\'s latest row:',
  [...pg.values()].every((g) => pg.has(threadKey(g.latest))))
console.log(bad ? `${bad} fixture(s) differ` : 'getter and pane agree on every fixture')
