import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(900)
for (const id of ['T-0004', 'T-0035']) {
  await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
  await p.waitForTimeout(600)
  const row = p.locator('.aim-attention-row').filter({ hasText: id }).first()
  console.log('=== ' + id + ' row: ' + (await row.innerText()).replace(/\s+/g, ' ').slice(0, 110))
  await row.click()
  await p.waitForTimeout(900)
  const drawer = await p.evaluate(() => {
    const d = document.querySelector('.el-drawer, [class*=drawer]')
    if (!d) return { found: false }
    const panel = document.querySelector('.aim-action-panel')
    return {
      found: true,
      title: d.querySelector('h2, .el-drawer__title, h3')?.innerText.trim(),
      panelHeading: panel?.querySelector('h4')?.innerText.trim(),
      buttons: [...(panel?.querySelectorAll('button') || [])].map(b => ({ label: b.innerText.trim(), disabled: b.disabled })),
      panelText: panel?.innerText.replace(/\s+/g, ' ').slice(0, 200),
    }
  })
  console.log('   drawer:', JSON.stringify(drawer, null, 1))
}
await b.close()
