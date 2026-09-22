import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
const probe = () => {
  const el = document.querySelector('#phase-cross_examine')
  if (!el) return { anchorExists: false }
  let s = el.parentElement, scroller = null
  while (s) {
    if (s.scrollHeight > s.clientHeight + 4) { scroller = s; break }
    s = s.parentElement
  }
  const box = el.getBoundingClientRect()
  return {
    anchorExists: true,
    anchorTopInViewport: Math.round(box.top),
    onScreen: box.top < innerHeight && box.bottom > 0,
    scrollerClass: scroller ? scroller.className.split(' ').slice(0, 3).join('.') : null,
    scrollerScrollTop: scroller ? Math.round(scroller.scrollTop) : null,
    scrollerHeight: scroller ? scroller.scrollHeight : null,
  }
}
for (const url of [
  'http://127.0.0.1:8777/#/help#phase-cross_examine',
  'http://127.0.0.1:8777/#/help',
]) {
  await p.goto(url, { waitUntil: 'networkidle' }); await p.waitForTimeout(1200)
  console.log(url.split('8777/')[1], '->', JSON.stringify(await p.evaluate(probe)))
}
// and clicking a chip from a page that has one
await p.goto('http://127.0.0.1:8777/#/barrier', { waitUntil: 'networkidle' }); await p.waitForTimeout(1200)
const chip = p.locator('.aim-phase-chip-link').first()
console.log('chips on #/barrier:', await p.locator('.aim-phase-chip-link').count())
if (await chip.count()) {
  console.log('chip href:', await chip.getAttribute('href'))
  await chip.click(); await p.waitForTimeout(1200)
  console.log('after chip click:', JSON.stringify(await p.evaluate(probe)), 'hash=', await p.evaluate(() => location.hash))
}
await b.close()
