import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/gantt', { waitUntil: 'networkidle' })
await p.waitForTimeout(1600)
const box = await p.locator('canvas').first().boundingBox()
const probe = { x: box.x + box.width * 0.45, y: box.y }
for (let i = 1; i <= 8; i += 1) {
  const y = box.y + (box.height * i) / 9
  await p.mouse.click(box.x + box.width * 0.45, y)
  await p.waitForTimeout(500)
  const r = await p.evaluate(() => {
    const d = document.querySelector('.el-drawer')
    return {
      open: Boolean(d) && getComputedStyle(d).display !== 'none',
      title: (d?.querySelector('.el-drawer__title')?.textContent || '').trim().slice(0, 40),
      first: (d?.innerText || '').replace(/\s+/g, ' ').slice(0, 70),
      buttons: [...document.querySelectorAll('.el-drawer button')].map(x => x.textContent.trim()).filter(Boolean).slice(0, 5),
    }
  })
  console.log(`y=${(i / 9).toFixed(2)}`, JSON.stringify(r))
  if (r.open) { await p.keyboard.press('Escape'); await p.waitForTimeout(300) }
}
await b.close()
