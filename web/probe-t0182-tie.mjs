/**
 * The tie case the adversarial verifier found, and the rule it settled.
 *
 * Two receipts of one conversation sharing a `ts` have two candidate "newest"
 * rows. Before: `latest` was the first of the tie (`>` refuses to replace on an
 * equal ts) while the panel was headed by the last (a plain `reverse()` of
 * payload order). After: one rule -- the list is sorted newest-first by the same
 * comparator, so the head of the list is the row `latest` points at.
 */
import { readFileSync } from 'node:fs'

const src = readFileSync('/root/tmp/agent-im/web/src/panes/OverviewPane.vue', 'utf8')
const body = /<script setup>([\s\S]*?)<\/script>/.exec(src)[1]
  .split('\n').filter((l) => !/^\s*import\s/.test(l)).join('\n')
const computed = (fn) => ({ get value() { return fn() } })
const stubs = {
  computed, ref: (v) => ({ value: v }), inject: () => ({ service: () => ({}) }),
  useBoard: () => globalThis.__board, isPromise: () => false, isOverdue: () => false,
  PRIORITY_TYPE: {}, STATUS_TYPE: {}, RouterLink: {}, PhaseApprovalCard: {}, PromiseTag: {},
  TaskLink: {}, days: () => 0, today: () => '2026-09-22',
}
const names = Object.keys(stubs)
const build = () => new Function(...names,
  `${body}\nreturn { recentConversations, receiptGroups }`)(...names.map((n) => stubs[n]))

const dm = (ts, subject, i) => ({
  from: 'codex', to: 'claude-session1', ts, subject, msg_id: `tie-${i}`,
  shape: 'direct', scope: 'claude-session1 ⇄ codex', ack_required: false, acked_at: '',
})
const run = (label, mail) => {
  globalThis.__board = { conversationRows: [...mail].sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0)) }
  const api = build()
  const rows = api.recentConversations.value
  const group = [...api.receiptGroups.value.values()][0]
  const counted = rows.find((r) => r.receiptCount)
  console.log(label)
  console.log('  payload order   :', mail.map((m) => m.msg_id).join(', '))
  console.log('  group.latest    :', group?.latest?.msg_id)
  console.log('  panel head      :', group?.receipts?.[0]?.msg_id,
    '| panel tail:', group?.receipts?.at(-1)?.msg_id)
  console.log('  head === latest :', group?.receipts?.[0]?.msg_id === group?.latest?.msg_id)
  console.log('  drawn           :', counted ? `${counted.receiptCount} receipts arrived @ ${counted.ts}` : '(no counted row)')
}

run('two receipts at one ts', [
  dm('2026-09-22T00:00:05.000Z', 'RECEIPT for FIRST', 0),
  dm('2026-09-22T00:00:05.000Z', 'RECEIPT for SECOND', 1),
])
run('five receipts at one ts, plus one ordinary row', [
  ...Array.from({ length: 5 }, (_, i) => dm('2026-09-22T00:00:05.000Z', `RECEIPT for tie-${i}`, i)),
  dm('2026-09-22T00:01:00.000Z', 'an ordinary message', 9),
])
run('distinct ts still newest-first', [
  dm('2026-09-22T00:00:00.000Z', 'RECEIPT for a', 0),
  dm('2026-09-22T00:02:00.000Z', 'RECEIPT for c', 2),
  dm('2026-09-22T00:01:00.000Z', 'RECEIPT for b', 1),
])
