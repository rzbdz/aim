import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/gantt', { waitUntil: 'networkidle' })
await p.waitForTimeout(1600)
const box = await p.locator('canvas').first().boundingBox()
console.log('canvas', JSON.stringify(box))
for (const xr of [0.6, 0.75, 0.85, 0.95]) {
  for (const yr of [0.2, 0.5]) {
    await p.mouse.click(box.x + box.width * xr, box.y + box.height * yr)
    await p.waitForTimeout(400)
    const r = await p.evaluate(() => {
      const d = document.querySelector('.el-drawer')
      const vis = d && getComputedStyle(d).display !== 'none' && d.getBoundingClientRect().width > 50
      return { vis, title: (d?.querySelector('.el-drawer__title')?.textContent || '').trim().slice(0, 30) }
    })
    console.log(`x=${xr} y=${yr}`, JSON.stringify(r))
    if (r.vis) { await p.keyboard.press('Escape'); await p.waitForTimeout(250) }
  }
}
await b.close()
