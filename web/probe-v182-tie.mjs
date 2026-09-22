/**
 * Addendum: what `receiptGroups` picks as `latest` on a tie, and what the row's
 * popover would open on. Read-only; executes the component's real script.
 */
import { readFileSync } from 'node:fs'
const FILE = '/root/tmp/agent-im/web/src/panes/OverviewPane.vue'
const source = readFileSync(FILE, 'utf8')
const script = /<script setup>([\s\S]*?)<\/script>/.exec(source)[1]
const body = script.split('\n').filter((l) => !/^\s*import\s/.test(l)).join('\n')
const computed = (fn) => ({ get value() { return fn() } })
const ref = (v) => ({ value: v })
const stub = { computed, ref, inject: () => ({ service: () => ({}) }), useBoard: () => globalThis.__board,
  isPromise: () => false, isOverdue: () => false, PRIORITY_TYPE: {}, STATUS_TYPE: {},
  RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {}, TaskLink: {}, days: () => 0, today: () => '2026-09-22' }
const names = Object.keys(stub)
const make = new Function(...names, `${body}\nreturn { recentConversations, receiptGroups, threadKey }`)
const { createPinia, setActivePinia } = await import('pinia'); setActivePinia(createPinia())
const mod = await import('/root/tmp/agent-im/web/.verifier-imports/board.js')

const row = (ts, subject, msg_id, over = {}) => ({ from: 'codex', to: 'claude-session1', ts, subject,
  body: 'x', msg_id, ack_required: false, acked_at: '', bytes: 0, state: 'delivered', ...over })

const CASES = {
  'tie on ts': [row('2026-09-22T00:00:05.000Z', 'RECEIPT for FIRST', 'a'),
                row('2026-09-22T00:00:05.000Z', 'RECEIPT for SECOND', 'b')],
  'tie on ts, three rows': [row('2026-09-22T00:00:05.000Z', 'RECEIPT for A', 'a'),
                            row('2026-09-22T00:00:05.000Z', 'RECEIPT for B', 'b'),
                            row('2026-09-22T00:00:05.000Z', 'RECEIPT for C', 'c')],
  'all ts empty': [row('', 'RECEIPT for A', 'a'), row('', 'RECEIPT for B', 'b'), row('', 'RECEIPT for C', 'c')],
  'ts missing': [row(undefined, 'RECEIPT for A', 'a'), row(undefined, 'RECEIPT for B', 'b')],
}
for (const [label, mail] of Object.entries(CASES)) {
  const doc = { conversation: { channels: [], rooms: [], mail, withheld: 0 } }
  const board = mod.useBoard(); board.doc = doc; globalThis.__board = board
  const { recentConversations, receiptGroups } = make(...names.map((n) => stub[n]))
  const g = [...receiptGroups.value.values()][0]
  const drawn = recentConversations.value[0]
  console.log(`\n### ${label}`)
  console.log('  payload order       :', mail.map((m) => m.subject.replace('RECEIPT for ', '')).join(' -> '))
  console.log('  sorted (store order):', board.conversationRows.map((r) => r.subject.replace('RECEIPT for ', '')).join(' -> '))
  console.log('  group.latest        :', g.latest.subject.replace('RECEIPT for ', ''))
  console.log('  group.receipts[0]   :', drawn.receipts[0].id, '(what the popover opens on)')
  console.log('  drawn row ts        :', JSON.stringify(drawn.ts), '| count', drawn.receiptCount)
}
