import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/items', { waitUntil: 'networkidle' })
await p.waitForTimeout(1300)
const cols = await p.evaluate(() => {
  const tr = [...document.querySelectorAll('tbody tr')].find(r => r.innerText.trim().startsWith('T-0004'))
  if (!tr) return 'no row'
  return {
    rowText: tr.innerText.replace(/\s+/g, ' ').slice(0, 90),
    cells: [...tr.querySelectorAll('td')].map((td, i) => ({
      i, text: td.innerText.trim().slice(0, 22),
      ctrls: [...td.querySelectorAll('button,a')].map(c => c.tagName + '|' + c.innerText.trim() + '|' + (c.getAttribute('title') || c.getAttribute('aria-label') || '')).slice(0, 3),
    })),
  }
})
console.log('ROW T-0004:', JSON.stringify(cols, null, 1))
async function open(id) {
  await p.evaluate((id) => {
    const tr = [...document.querySelectorAll('tbody tr')].find(r => r.innerText.trim().startsWith(id))
    const td = tr.querySelector('td')                       // the ID column
    const c = td.querySelector('button,a') || tr.querySelector('td:last-child button')
    c.click()
  }, id)
  await p.waitForTimeout(900)
  const d = await p.evaluate(() => {
    const dr = document.querySelector('.el-drawer')
    if (!dr) return { open: false }
    return { title: (dr.querySelector('.el-drawer__title')?.innerText || '').trim(),
             buttons: [...dr.querySelectorAll('.el-drawer__body button')].map(e => e.innerText.trim()).filter(Boolean) }
  })
  await p.keyboard.press('Escape'); await p.waitForTimeout(400)
  return d
}
for (const id of ['T-0004', 'T-0035', 'T-0002', 'T-0176']) console.log(id, JSON.stringify(await open(id)))
await b.close()
