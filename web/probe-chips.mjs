import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
const both = await p.evaluate(() => {
  const h = document.querySelector('.aim-history')
  const out = []
  for (const m of h.querySelectorAll('.aim-msg')) {
    const chips = [...m.querySelectorAll('header .el-tag')].map(c => c.innerText.trim())
    if (chips.includes('acked') && chips.includes('receipt demanded')) {
      out.push({ head: m.querySelector('header').innerText.replace(/\s+/g,' ').slice(0,90), chips, body: m.querySelector('.aim-body')?.innerText.replace(/\s+/g,' ').slice(0, 80) })
    }
  }
  return { count: out.length, sample: out.slice(0, 2) }
})
console.log('messages showing BOTH acked and receipt-demanded:', both.count)
console.log(JSON.stringify(both.sample, null, 1))
await b.close()
