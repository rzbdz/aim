import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForSelector('.aim-thread')
const rows = await p.$$eval('.aim-thread', els => els.map(e => {
  const spans = e.querySelectorAll('span')
  return { label: spans[0]?.textContent?.trim(), ts: [...e.querySelectorAll('.aim-dim')].pop()?.textContent?.trim() }
}))
console.log('threads now:', rows.length)
for (const r of rows) console.log('  ', r.label, '|', r.ts)
const dm = rows.filter(r => r.label.includes('⇄'))
console.log('direct threads:', dm.length, '->', dm.map(r => r.label).join(' , '))
await b.close()
