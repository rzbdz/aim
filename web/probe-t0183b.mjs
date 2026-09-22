import { chromium } from 'playwright'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 700 } })
await page.goto('http://127.0.0.1:8777/#/attention')
await page.waitForSelector('.aim-attention-signals .aim-signal')
const read = () => page.evaluate(() => ({
  url: location.hash,
  scrollTop: Math.round(document.querySelector('.aim-main').scrollTop),
}))
const tile = page.locator('.aim-signal').filter({ hasText: 'Plan disagreements' })
console.log('empty state ', await read())
await tile.first().click()
await page.waitForTimeout(700)
console.log('click 1     ', await read())
// the reader scrolls back up, then clicks the same tile again: same URL, so does
// the router run scrollBehavior at all?
await page.evaluate(() => { document.querySelector('.aim-main').scrollTop = 0 })
await page.waitForTimeout(200)
console.log('parked up   ', await read())
await tile.first().click()
await page.waitForTimeout(700)
console.log('click 2     ', await read())
await browser.close()
