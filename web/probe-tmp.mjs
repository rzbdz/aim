import { chromium } from '@playwright/test'
const chat = (digest, bodies, pad = '') => ({
  digest, statuses: ['backlog'], terminal: ['done'], phase: 'RESOLVE', milestones: {},
  agents: { human: { kind: 'human', model: '' } }, register: {}, tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [{ id: 'hello', phase: 'RESOLVE', gated: false, rule: 'f',
    messages: bodies.map((body, i) => ({ from: 'codex', to: 'hello', ts: `2026-09-22T01:${String(i).padStart(2,'0')}:00.000Z`, kind: 'note', body: body + pad })) }], rooms: [], mail: [] },
  unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
})
const sixty = Array.from({ length: 60 }, (_, i) => `fixture message ${i}`)
const box = { doc: chat('s1', sixty, ' .') }
const b = await chromium.launch()
const p = await b.newPage()
p.on('pageerror', (e) => console.log('PAGEERROR', e.message))
await p.route('**/api/state**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(box.doc) }))
await p.route('**/api/digest**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ digest: box.doc.digest }) }))
await p.goto('http://127.0.0.1:8777/#/chat')
await p.waitForTimeout(1200)
console.log('park:', await p.evaluate(() => { const e = document.querySelector('.aim-history'); e.scrollTop = 200; return e.scrollTop }))
box.doc = chat('s2', [...sixty, 'newer'], ' .')
await p.waitForTimeout(4000)
console.log('deferred:', await p.evaluate(() => ({ d: !!document.querySelector('.aim-deferred'), msgs: document.querySelectorAll('.aim-msg').length })))
const r = await p.evaluate(async () => {
  const el = document.querySelector('.aim-history')
  const before = el.scrollTop
  const btn = document.querySelector('.aim-deferred button')
  btn.click()
  await new Promise((r) => setTimeout(r, 600))
  return { before, after: el.scrollTop, msgs: document.querySelectorAll('.aim-msg').length,
           deferred: !!document.querySelector('.aim-deferred') }
})
console.log('click:', JSON.stringify(r))
await b.close()
