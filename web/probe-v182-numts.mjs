/**
 * Numeric-ish timestamps: does a row whose ts is a number / a Date ever become
 * the group's `latest`, and would the row still be dated by its newest receipt?
 */
import { readFileSync } from 'node:fs'
const src = readFileSync('/root/tmp/agent-im/web/src/panes/OverviewPane.vue', 'utf8')
const body = /<script setup>([\s\S]*?)<\/script>/.exec(src)[1].split('\n').filter((l) => !/^\s*import\s/.test(l)).join('\n')
const computed = (fn) => ({ get value() { return fn() } })
const ref = (v) => ({ value: v })
const stub = { computed, ref, inject: () => ({ service: () => ({}) }), useBoard: () => globalThis.__board,
  isPromise: () => false, isOverdue: () => false, PRIORITY_TYPE: {}, STATUS_TYPE: {},
  RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {}, TaskLink: {}, days: () => 0, today: () => '2026-09-22' }
const names = Object.keys(stub)
const make = new Function(...names, `${body}\nreturn { recentConversations, receiptGroups }`)
const { createPinia, setActivePinia } = await import('pinia'); setActivePinia(createPinia())
const mod = await import('/root/tmp/agent-im/web/.verifier-imports/board.js')
const row = (ts, subject, msg_id) => ({ from: 'codex', to: 'claude-session1', ts, subject, body: 'x',
  msg_id, ack_required: false, acked_at: '', bytes: 0, state: 'delivered' })

const CASES = {
  'newest receipt has a NUMBER ts': [
    row('2026-09-22T00:00:00.000Z', 'RECEIPT for early', 'e'),
    row(Date.parse('2026-09-22T00:10:00.000Z'), 'RECEIPT for numeric-newest', 'n'),
  ],
  'newest receipt has a Date object ts': [
    row('2026-09-22T00:00:00.000Z', 'RECEIPT for early', 'e'),
    row(new Date('2026-09-22T00:10:00.000Z'), 'RECEIPT for Date-newest', 'd'),
  ],
  'numeric ts where the LATER row has the SMALLER number (window reversed)': [
    row(3, 'RECEIPT for n3', 'i'), row(1, 'RECEIPT for n1', 'j'),
  ],
}
for (const [label, mail] of Object.entries(CASES)) {
  const doc = { conversation: { channels: [], rooms: [], mail, withheld: 0 } }
  const board = mod.useBoard(); board.doc = doc; globalThis.__board = board
  const { recentConversations, receiptGroups } = make(...names.map((n) => stub[n]))
  // sort order the real store produces for this payload
  const order = board.conversationRows.map((r) => r.subject.replace('RECEIPT for ', ''))
  let g, drawn
  try { g = [...receiptGroups.value.values()][0]; drawn = recentConversations.value[0] }
  catch (err) { console.log(`\n### ${label}\n  THREW: ${err.constructor.name}: ${err.message}`); continue }
  console.log(`\n### ${label}`)
  console.log('  store order      :', order.join(' -> '))
  console.log('  group.latest     :', g.latest.subject.replace('RECEIPT for ', ''))
  console.log('  drawn ts         :', JSON.stringify(drawn.ts), '| type', typeof drawn.ts)
  console.log('  popover newest   :', drawn.receipts[0].id)
}
