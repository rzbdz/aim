import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 90)) })
for (const route of ['#/kanban', '#/items', '#/gantt']) {
  await p.goto('http://127.0.0.1:8777/' + route, { waitUntil: 'networkidle' })
  await p.waitForTimeout(1100)
  const r = await p.evaluate(() => {
    const c = document.querySelector('.aim-card[data-id], tbody tr .aim-task-link, tbody tr button, .aim-task-link')
    if (!c) return 'no target'
    ;(c.closest('.aim-card') || c).click(); return 'clicked'
  })
  await p.waitForTimeout(900)
  const out = await p.evaluate(() => ({ drawer: document.querySelectorAll('.el-drawer').length, overlay: document.querySelectorAll('.el-overlay').length }))
  console.log(route, r, JSON.stringify(out))
}
console.log('sample console error:', errs[0] || 'none')
await b.close()
