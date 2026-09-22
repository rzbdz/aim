import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/barrier', { waitUntil: 'networkidle' })
await p.waitForTimeout(1600)
const r = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const pane = [...document.querySelectorAll('.el-tab-pane')].find(e => e.offsetParent !== null && e.innerText.trim())
  if (!pane) return 'no visible pane'
  const base = pane.getBoundingClientRect().top + main.scrollTop
  const kids = [...pane.children].map(el => {
    const rc = el.getBoundingClientRect()
    return { cls: (el.className||'').toString().slice(0,46), top: Math.round(rc.top + main.scrollTop - base), h: Math.round(rc.height),
             text: el.innerText.replace(/\s+/g,' ').slice(0, 150) }
  })
  return { paneText: pane.innerText.replace(/\s+/g,' ').slice(0, 1400), kids,
           cards: [...pane.querySelectorAll('.el-card__header')].map(e => e.innerText.replace(/\s+/g,' ').slice(0, 70)),
           tables: [...pane.querySelectorAll('table')].map(t => (t.querySelector('thead')?.innerText || '').replace(/\s+/g,' ').slice(0, 120)) }
})
if (typeof r === 'string') { console.log(r) } else {
  console.log('CARDS:', JSON.stringify(r.cards, null, 1))
  console.log('TABLES:', JSON.stringify(r.tables, null, 1))
  console.log('CHILDREN:')
  for (const k of r.kids) console.log('  ', String(k.top).padStart(5), 'h=' + String(k.h).padStart(5), k.cls, '::', k.text)
  console.log('\nPANE TEXT (first 1400):\n', r.paneText)
}
await b.close()
