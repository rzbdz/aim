import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const r = await p.evaluate(() => {
  const heads = [...document.querySelectorAll('.el-card')]
  const card = heads.find(c => /Latest conversation/i.test(c.innerText))
  if (!card) return 'no card'
  const rows = [...card.querySelectorAll('article, li, .aim-attention-row, tr')].map(e => e.innerText.replace(/\s+/g,' ').slice(0, 110))
  return { text: card.innerText.replace(/\s+/g,' ').slice(0, 500), rows }
})
console.log(JSON.stringify(r, null, 1))
const tail = await p.evaluate(async () => {
  const res = await fetch('/api/state'); const d = await res.json()
  const rows = (d.conversation && d.conversation.rows) || d.conversationRows || []
  return { keys: Object.keys(d.conversation || {}), n: rows.length, tail: rows.slice(-6).map(r => r.subject || (r.body||'').slice(0,40)) }
})
console.log('payload conversation:', JSON.stringify(tail, null, 1))
await b.close()
