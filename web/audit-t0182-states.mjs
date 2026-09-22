/**
 * Auditor: compare every `/tmp/aim-tasks/state-*.json` dump against the report's
 * live numbers (197 rows / 53 receipts / 46-6-1; 207 rows / 57).
 */
import { readFileSync } from 'node:fs'

const re = /^RECEIPT for\s+/
const files = process.argv.slice(2)
for (const p of files) {
  let d
  try { d = JSON.parse(readFileSync(p, 'utf8')) } catch (e) { console.log(p, 'ERR', e.message); continue }
  const c = d.conversation || {}
  const flat = []
  for (const ch of c.channels || []) for (const m of ch.messages || []) flat.push(m)
  for (const rm of c.rooms || []) for (const m of rm.messages || []) flat.push(m)
  for (const m of c.mail || []) flat.push(m)
  flat.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
  const recs = flat.filter((r) => re.test(r.subject || ''))
  const by = new Map()
  for (const m of c.mail || []) {
    if (!re.test(m.subject || '')) continue
    const k = [m.from, m.to].map(String).sort().join(' ⇄ ')
    by.set(k, (by.get(k) || 0) + 1)
  }
  const pair = recs.filter((r) => [r.from, r.to].map(String).sort().join(' ⇄ ') === 'claude-session1 ⇄ codex')
  const ts = pair.map((r) => r.ts).sort()
  const tasks = Object.values(d.tasks || {})
  const recorded = tasks.filter((t) => !(t.provenance || '').includes('seed'))
  const ids = recs.map((r) => (r.subject || '').replace(re, '').trim())
  const mailIds = new Set((c.mail || []).map((m) => m.msg_id))
  console.log(p.split('/').pop(),
    '| generated', d.generated_at,
    '| rows', flat.length,
    '| receipts', recs.length,
    '| last5', flat.slice(-5).filter((r) => re.test(r.subject || '')).length,
    '| byScope', JSON.stringify([...by].sort((a, b) => b[1] - a[1])),
    '| c1<->codex span', ts[0], '->', ts.at(-1),
    '| ids in mail', ids.filter((i) => mailIds.has(i)).length, '/', ids.length,
    '| tasks', tasks.length, 'recorded', recorded.length)
}
