import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1400)
// click the "open it" on T-0004 in the promise card
const clicked = await p.evaluate(() => {
  const card = [...document.querySelectorAll('.el-card')].find(c => /promises in the plan/i.test(c.innerText))
  const row = [...card.querySelectorAll('.aim-attention-row')].find(r => /T-0004/.test(r.innerText))
  const btn = [...row.querySelectorAll('button')].find(e => /open it/i.test(e.innerText))
  btn.click(); return row.innerText.replace(/\s+/g,' ').slice(0, 90)
})
await p.waitForTimeout(1000)
console.log('clicked row:', clicked)
console.log(JSON.stringify(await p.evaluate(() => {
  const dr = document.querySelector('.el-drawer')
  if (!dr) return { open: false }
  return { title: dr.querySelector('.el-drawer__title')?.innerText.trim(),
           buttons: [...dr.querySelectorAll('.el-drawer__body button')].map(e => e.innerText.trim()).filter(Boolean),
           text: dr.innerText.replace(/\s+/g, ' ').slice(0, 260) }
}), null, 1))
await b.close()
