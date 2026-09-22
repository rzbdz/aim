import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1400)
const before = await p.evaluate(() => document.elementFromPoint(720, 500)?.className)
await p.evaluate(() => {
  const card = [...document.querySelectorAll('.el-card')].find(c => /Work needing you now/i.test(c.innerText))
  card.querySelector('.aim-attention-row').click()
})
await p.waitForTimeout(1000)
const after = await p.evaluate(() => {
  const el = document.elementFromPoint(720, 500)
  const ov = document.querySelector('.el-overlay')
  return { topElement: el?.tagName + '.' + (el?.className || '').toString().slice(0, 40),
           overlayCount: document.querySelectorAll('.el-overlay').length,
           overlayVisible: ov ? getComputedStyle(ov).display !== 'none' : false,
           drawerCount: document.querySelectorAll('.el-drawer').length,
           navReachable: !!document.elementFromPoint(60, 300)?.closest('.el-menu') }
})
console.log('element at centre before click:', before)
console.log('after click:', JSON.stringify(after, null, 1))
// can the reader click nav to get away?
await p.mouse.click(60, 300)
await p.waitForTimeout(800)
console.log('url after clicking nav through the overlay:', p.url())
await b.close()
