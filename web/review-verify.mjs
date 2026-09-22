import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
let errs = []
p.on('pageerror', e => errs.push(e.message))
p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)) })
for (const r of ['/', '/kanban', '/chat', '/items', '/gantt', '/reports', '/barrier', '/plan', '/help']) {
  errs = []
  await p.goto('http://127.0.0.1:8777/#' + r, { waitUntil: 'networkidle' })
  await p.waitForTimeout(800)
  const t = await p.evaluate(() => ({
    text: document.body.innerText.trim().length,
    main: (document.querySelector('.el-main')?.innerHTML || '').length,
  }))
  console.log(r.padEnd(9), 'text', String(t.text).padStart(6), 'main', String(t.main).padStart(7), errs.length ? '  ERRORS: ' + errs[0] : '')
}
await b.close()
