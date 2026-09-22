import { chromium } from 'playwright'
const routes = ['#/overview','#/attention','#/items','#/kanban','#/gantt','#/plan','#/reports','#/chat','#/barrier','#/help']
const b = await chromium.launch(); const p = await b.newPage({ viewport:{width:1440,height:1000} })
const errs = []
p.on('pageerror', e => errs.push(String(e).slice(0,160)))
p.on('console', m => { if (m.type()==='error') errs.push('console: '+m.text().slice(0,160)) })
for (const r of routes) {
  await p.goto('http://127.0.0.1:8777/'+r)
  await p.waitForTimeout(700)
  const h = await p.evaluate(() => ({ overlays: [...document.querySelectorAll('.el-overlay')].filter(e=>getComputedStyle(e).display!=='none').length, h2: document.querySelector('h2')?.textContent || '', h: document.querySelector('.aim-page')?.scrollHeight || 0 }))
  console.log(r.padEnd(12), 'blockingOverlays', h.overlays, '| h2:', h.h2.slice(0,40))
}
console.log('errors:', [...new Set(errs)])
await b.close()
