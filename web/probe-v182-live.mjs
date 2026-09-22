/**
 * The live payload: what the changed card draws for the state 8777 is serving
 * right now (/api/state, read-only), and whether its count for a conversation
 * equals the number of receipts in that conversation in the payload.
 */
import { readFileSync } from 'node:fs'
const state = JSON.parse(readFileSync('/tmp/state.json', 'utf8'))
const source = readFileSync('/root/tmp/agent-im/web/src/panes/OverviewPane.vue', 'utf8')
const body = /<script setup>([\s\S]*?)<\/script>/.exec(source)[1]
  .split('\n').filter((l) => !/^\s*import\s/.test(l)).join('\n')
const computed = (fn) => ({ get value() { return fn() } })
const ref = (v) => ({ value: v })
const stub = { computed, ref, inject: () => ({ service: () => ({}) }), useBoard: () => globalThis.__board,
  isPromise: () => false, isOverdue: () => false, PRIORITY_TYPE: {}, STATUS_TYPE: {},
  RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {}, TaskLink: {}, days: () => 0, today: () => '2026-09-22' }
const names = Object.keys(stub)
const make = new Function(...names, `${body}\nreturn { recentConversations, receiptGroups, threadKey }`)
const { createPinia, setActivePinia } = await import('pinia'); setActivePinia(createPinia())
const mod = await import('/root/tmp/agent-im/web/.verifier-imports/board.js')
const board = mod.useBoard(); board.doc = state; globalThis.__board = board
const rows = board.conversationRows
const re = /^RECEIPT for\s+/
const { recentConversations, receiptGroups } = make(...names.map((n) => stub[n]))
console.log('payload rows', rows.length, '| receipts', rows.filter((r) => re.test(r.subject || '')).length)
console.log('window (last 5):')
for (const r of rows.slice(-5)) console.log('  ', r.ts, JSON.stringify(r.scope), re.test(r.subject || '') ? 'RECEIPT' : JSON.stringify(r.subject))
console.log('groups the component holds:')
for (const g of receiptGroups.value.values()) {
  const truth = rows.filter((r) => re.test(r.subject || '') && `${r.shape}:${r.shape === 'direct' ? r.scope : r.channel}` === `${g.shape}:${g.shape === 'direct' ? g.scope : g.key.split(':')[1]}`)
  console.log(`  ${g.key} size=${g.size} latest=${g.latest.ts} newestOfGroupInPayload=${truth.map(r => r.ts).sort().at(-1)} ids=${new Set(g.receipts.map(x => x.id)).size} distinct`)
}
console.log('rows the card draws:')
for (const r of recentConversations.value) console.log('  ', r.ts, JSON.stringify(r.scope), r.receiptCount ? `${r.receiptCount} receipts arrived -> ${r.receipts.map(x => x.id).join(', ')}` : JSON.stringify(r.subject))

// --- invariant sweep over the live payload -----------------------------------
const re2 = /^RECEIPT for\s+/
let bad = 0
for (const r of recentConversations.value) {
  if (!r.receiptCount) continue
  const truth = rows.filter((x) => re2.test(x.subject || '') && x.scope === r.scope && x.shape === r.shape)
  const ids = new Set(truth.map((x) => (x.subject || '').replace(re2, '').trim()))
  const shown = new Set(r.receipts.map((x) => x.id))
  const newest = truth.map((x) => x.ts || '').sort().at(-1)
  const okCount = r.receiptCount === truth.length
  const okNewest = r.ts === newest
  const okIds = ids.size === shown.size && [...ids].every((i) => shown.has(i))
  const keys = r.receipts.map((x) => x.msg_id)
  const dupKeys = keys.length !== new Set(keys).size
  console.log(`  ${r.scope}: count ok=${okCount} newest ok=${okNewest} names every id=${okIds} duplicate Vue keys=${dupKeys}`)
  if (!(okCount && okNewest && okIds) || dupKeys) bad++
}
console.log('live invariant violations:', bad)
