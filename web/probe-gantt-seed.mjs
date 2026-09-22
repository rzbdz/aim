import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/gantt', { waitUntil: 'networkidle' })
await p.waitForTimeout(1600)
const box = await p.locator('canvas').first().boundingBox()
await p.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.2)
await p.waitForTimeout(700)
const r = await p.evaluate(() => {
  const d = document.querySelector('.el-drawer')
  if (!d) return 'no drawer'
  return {
    title: (d.querySelector('.el-drawer__title')?.textContent || '').trim(),
    body: (d.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 500),
    buttons: [...d.querySelectorAll('button')].map(x => x.textContent.trim()).filter(Boolean),
    links: [...d.querySelectorAll('a[href]')].map(x => x.getAttribute('href')).slice(0, 5),
    height: Math.round(d.getBoundingClientRect().height),
  }
})
console.log(JSON.stringify(r, null, 1))
const state = await p.evaluate(async () => {
  const s = await (await fetch('/api/state')).json()
  const t = s.tasks['T-0147']
  return t ? { status: t.status, owner: t.owner, provenance: t.provenance, comments: (t.comments || []).length } : 'not in payload'
})
console.log('T-0147 in payload:', JSON.stringify(state))
await b.close()
