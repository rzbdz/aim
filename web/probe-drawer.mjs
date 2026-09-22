import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('pageerror', e => errs.push(String(e.message).slice(0, 140)))
await p.goto('http://127.0.0.1:8777/#/items', { waitUntil: 'networkidle' })
await p.waitForTimeout(1300)
async function open(id) {
  const ok = await p.evaluate((id) => {
    const tr = [...document.querySelectorAll('tbody tr')].find(r => r.innerText.trim().startsWith(id))
    if (!tr) return 'no row'
    const btn = tr.querySelector('button, a')
    if (!btn) return 'no control in row'
    btn.click(); return 'clicked:' + btn.tagName + '.' + (btn.className || '').toString().split(' ')[0]
  }, id)
  await p.waitForTimeout(900)
  const d = await p.evaluate(() => {
    const dr = document.querySelector('.el-drawer')
    if (!dr) return { open: false }
    return {
      title: (dr.querySelector('.el-drawer__title')?.innerText || '').trim(),
      buttons: [...dr.querySelectorAll('.el-drawer__body button')].map(e => e.innerText.trim()).filter(Boolean),
      prov: (dr.innerText.match(/provenance[^\n]*\n?[^\n]*/) || [''])[0].replace(/\s+/g, ' ').slice(0, 70),
    }
  })
  await p.keyboard.press('Escape'); await p.waitForTimeout(400)
  return { ok, ...d }
}
for (const id of ['T-0004', 'T-0035', 'T-0002', 'T-0176', 'T-0183']) {
  console.log(id, JSON.stringify(await open(id)))
}
console.log('errs', JSON.stringify(errs))
await b.close()
