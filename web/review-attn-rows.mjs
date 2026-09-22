import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1000)
const rows = await p.evaluate(() => {
  const out = []
  for (const card of document.querySelectorAll('.el-card')) {
    const head = card.querySelector('.el-card__header')?.innerText.replace(/\s+/g, ' ').trim()
    if (!head) continue
    const items = [...card.querySelectorAll('.aim-attention-row')].map(r => ({
      text: r.innerText.replace(/\s+/g, ' ').slice(0, 96),
      button: r.querySelector('button')?.innerText.trim() || null,
      clickable: r.getAttribute('role'),
    }))
    if (items.length) out.push({ head, items })
  }
  return out
})
for (const c of rows) {
  console.log('## ' + c.head)
  for (const i of c.items) console.log('   [btn:' + String(i.button).padEnd(16) + '] ' + i.text)
}
await b.close()
