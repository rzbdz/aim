import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/gantt', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
const info = await p.evaluate(() => {
  const out = {}
  out.canvas = document.querySelectorAll('canvas').length
  out.svg = document.querySelectorAll('svg').length
  out.taskLinks = document.querySelectorAll('.aim-task-link').length
  out.clickable = document.querySelectorAll('[data-id], .aim-clickable').length
  const ech = document.querySelector('canvas')
  out.echartsCanvas = Boolean(ech)
  out.text = document.body.innerText.slice(0, 400)
  return out
})
console.log(JSON.stringify(info, null, 1))
// try clicking a bar area in the chart
const box = await p.locator('canvas').first().boundingBox().catch(() => null)
if (box) {
  for (const [dx, dy] of [[0.5, 0.2], [0.3, 0.3], [0.6, 0.45]]) {
    await p.mouse.click(box.x + box.width * dx, box.y + box.height * dy)
    await p.waitForTimeout(500)
    const r = await p.evaluate(() => ({ drawer: document.querySelectorAll('.el-drawer').length, hash: location.hash }))
    console.log('click', dx, dy, JSON.stringify(r))
    if (r.drawer) break
  }
}
await b.close()
