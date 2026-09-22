import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
for (const url of [
  'http://127.0.0.1:8777/#/help#phase-CROSS_EXAMINE',
  'http://127.0.0.1:8777/#/help',
]) {
  await p.goto(url, { waitUntil: 'networkidle' })
  await p.waitForTimeout(900)
  const r = await p.evaluate(() => {
    const el = document.querySelector('#phase-CROSS_EXAMINE')
    const box = el?.getBoundingClientRect()
    return {
      locationHash: location.hash,
      windowScrollY: Math.round(window.scrollY),
      anchorExists: Boolean(el),
      anchorTopInViewport: box ? Math.round(box.top) : null,
      anchorVisibleOnScreen: box ? (box.top < innerHeight && box.bottom > 0) : null,
      scrollableHeight: document.documentElement.scrollHeight,
    }
  })
  console.log(url.replace('http://127.0.0.1:8777/', ''), '->', JSON.stringify(r))
}
await b.close()
