import { chromium } from 'playwright'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 700 } })
page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text().slice(0, 160)) })
await page.goto('http://127.0.0.1:8777/#/attention')
await page.waitForSelector('.aim-attention-signals .aim-signal')
const read = () => page.evaluate(() => ({
  url: location.hash,
  scrollTop: Math.round(document.querySelector('.aim-main').scrollTop),
  driftTop: document.getElementById('drift')
    ? Math.round(document.getElementById('drift').getBoundingClientRect().top - document.querySelector('.aim-main').getBoundingClientRect().top)
    : null,
}))
console.log('before  ', await read())
const tile = page.locator('.aim-signal').filter({ hasText: 'Plan disagreements' })
console.log('tiles matching:', await tile.count(), 'url(href):', await tile.first().getAttribute('href'))
await tile.first().click()
await page.waitForTimeout(900)
console.log('after   ', await read())
// And the phase-requests tile, whose target is likewise already on this page.
const phase = page.locator('.aim-signal').filter({ hasText: 'Phase requests' })
console.log('phase tile count:', await phase.count(), 'href:', await phase.first().getAttribute('href'))
await browser.close()
