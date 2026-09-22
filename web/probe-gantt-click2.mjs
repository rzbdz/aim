import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/gantt', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
const box = await p.locator('canvas').first().boundingBox()
await p.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.2)
await p.waitForTimeout(700)
const r = await p.evaluate(() => {
  const d = document.querySelector('.el-drawer')
  return { title: (d?.querySelector('.el-drawer__title, h2, h3, .aim-drawer__title')?.textContent || '').trim().slice(0, 60),
           buttons: [...document.querySelectorAll('.el-drawer button')].map(x => x.textContent.trim()).filter(Boolean).slice(0, 8),
           canTab: Boolean(document.querySelector('.el-drawer [tabindex]')) }
})
console.log(JSON.stringify(r))
await b.close()
