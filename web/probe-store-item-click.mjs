import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('pageerror', e => errs.push(String(e.message).slice(0, 160)))
p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 140)) })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1400)
// a recorded item from "Work needing you now"
const t = await p.evaluate(() => {
  const card = [...document.querySelectorAll('.el-card')].find(c => /Work needing you now/i.test(c.innerText))
  const row = card.querySelector('.aim-attention-row')
  const btn = [...row.querySelectorAll('button')].find(e => !/open it/i.test(e.innerText))
  const r = (btn || row).getBoundingClientRect()
  return { text: row.innerText.replace(/\s+/g,' ').slice(0, 60), x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2) }
})
await p.mouse.click(t.x, t.y)
await p.waitForTimeout(1200)
console.log('clicked:', t.text)
console.log('drawer:', JSON.stringify(await p.evaluate(() => ({
  drawer: !!document.querySelector('.el-drawer'),
  title: document.querySelector('.el-drawer__title')?.innerText.trim() || null,
  buttons: [...document.querySelectorAll('.el-drawer__body button')].map(e => e.innerText.trim()).filter(Boolean),
}))))
console.log('errs:', JSON.stringify(errs))
await b.close()
