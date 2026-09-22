import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('pageerror', e => errs.push(String(e.message).slice(0, 200)))
p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)) })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1400)
const target = await p.evaluate(() => {
  const card = [...document.querySelectorAll('.el-card')].find(c => /promises in the plan/i.test(c.innerText))
  const row = [...card.querySelectorAll('.aim-attention-row')].find(r => /T-0004/.test(r.innerText))
  const btn = [...row.querySelectorAll('button')].find(e => /open it/i.test(e.innerText))
  const r = btn.getBoundingClientRect()
  return { rowHTML: row.outerHTML.slice(0, 400), btnRect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }, btnDisabled: btn.disabled }
})
console.log('target:', JSON.stringify(target, null, 1))
await p.mouse.click(target.btnRect.x + target.btnRect.w / 2, target.btnRect.y + target.btnRect.h / 2)
await p.waitForTimeout(1500)
console.log('after mouse click on "open it":', JSON.stringify(await p.evaluate(() => ({
  drawer: !!document.querySelector('.el-drawer'),
  drawerTitle: document.querySelector('.el-drawer__title')?.innerText.trim() || null,
  overlay: !!document.querySelector('.el-overlay'),
})), null, 1))
console.log('errs:', JSON.stringify(errs, null, 1))
await b.close()
