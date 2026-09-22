import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('pageerror', e => errs.push(String(e.message).slice(0, 140)))
await p.goto('http://127.0.0.1:8777/#/items', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
async function openRow(id) {
  await p.evaluate((id) => {
    const el = [...document.querySelectorAll('.el-main *')].find(e => e.children.length === 0 && e.textContent.trim() === id)
    const row = el?.closest('tr') || el?.closest('.aim-attention-row')
    const btn = el?.closest('button') || row?.querySelector('button')
    ;(btn || row || el)?.click()
  }, id)
  await p.waitForTimeout(900)
  const d = await p.evaluate(() => {
    const drawer = document.querySelector('.el-drawer, .el-dialog')
    if (!drawer) return { open: false }
    return {
      open: true, title: (drawer.querySelector('.el-drawer__title, .el-dialog__title')?.innerText || '').trim(),
      buttons: [...drawer.querySelectorAll('button')].map(e => e.innerText.trim()).filter(Boolean),
      text: drawer.innerText.replace(/\s+/g, ' ').slice(0, 400),
    }
  })
  await p.keyboard.press('Escape'); await p.waitForTimeout(500)
  return d
}
console.log('GHOST T-0004 (plan only, owner human):'); console.log(JSON.stringify(await openRow('T-0004'), null, 1))
console.log('GHOST T-0011 (plan only):'); console.log(JSON.stringify(await openRow('T-0011'), null, 1))
console.log('RECORD T-0176 (in store):'); console.log(JSON.stringify(await openRow('T-0176'), null, 1))
console.log('errs', JSON.stringify(errs))
await b.close()
