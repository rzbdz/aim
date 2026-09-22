import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1600)
const r = await p.evaluate(() => {
  const txt = document.body.innerText
  const m = txt.match(/Start here[\s\S]{0,200}/)
  const promise = txt.match(/planned \d+ promises[^\n]*/)
  return { startHere: (m ? m[0] : '').replace(/\n+/g, ' | ').slice(0, 200),
           promiseLine: promise ? promise[0] : null,
           saysDecisionForYou: (txt.match(/decision for you/g) || []).length,
           promisesDrawn: document.querySelectorAll('.aim-promise').length,
           rows: document.querySelectorAll('.aim-attention-row').length }
})
console.log(JSON.stringify(r, null, 1))
await b.close()
