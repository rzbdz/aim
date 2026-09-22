/**
 * The template keys each drawn row as `${shape}:${msg_id || hash || ts}`. This
 * asks whether two DIFFERENT drawn convsersation rows can carry the same key.
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
const make = new Function(...names, `${body}\nreturn { recentConversations, threadKey }`)
const { createPinia, setActivePinia } = await import('pinia'); setActivePinia(createPinia())
const mod = await import('/root/tmp/agent-im/web/.verifier-imports/board.js')
const T = (i) => `2026-09-22T00:00:${String(i).padStart(2, '0')}.000Z`
const mail = (ts, over = {}) => ({ from: 'codex', to: 'claude-session1', ts, subject: 'RECEIPT for x',
  body: 'x', msg_id: `${ts}-id`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered', ...over })
// gate.py builds a nested room message as {from, ts, body, mentions} -- there is
// no msg_id and no hash anywhere in it (aimboard/gate.py:143-153).
const nestedRoom = (ts, body) => ({ from: 'codex', ts, body, mentions: [] })

const CASES = {
  'two receipts in different pairs with the SAME msg_id': {
    conversation: { channels: [], rooms: [], mail: [
      mail(T(1), { from: 'a', to: 'b', msg_id: 'SAME', subject: 'RECEIPT for r1' }),
      mail(T(2), { from: 'c', to: 'd', msg_id: 'SAME', subject: 'RECEIPT for r2' }),
    ], withheld: 0 },
  },
  'two nested room messages with no msg_id, same ts': {
    conversation: { channels: [], rooms: [{ id: 'r1', channel: 'hello', visibility: 'open', messages: [
      nestedRoom(T(1), 'first room message'), nestedRoom(T(1), 'second room message'),
    ] }], mail: [], withheld: 0 },
  },
}
for (const [label, doc] of Object.entries(CASES)) {
  const board = mod.useBoard(); board.doc = doc; globalThis.__board = board
  const { recentConversations } = make(...names.map((n) => stub[n]))
  const got = recentConversations.value
  const keys = got.map((r) => `${r.shape}:${r.msg_id || r.hash || r.ts}`)
  console.log(`\n### ${label}`)
  console.log('  rows drawn:', got.length, '| keys:', JSON.stringify(keys))
  console.log('  distinct keys:', new Set(keys).size, '->', new Set(keys).size === keys.length ? 'ok' : 'DUPLICATE KEY')
  for (const r of got) console.log('   -', JSON.stringify({ from: r.from, to: r.to, ts: r.ts, subject: r.subject, body: r.body, msg_id: r.msg_id }))
}
