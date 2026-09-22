import { chromium } from 'playwright'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 700 } })
await page.goto('http://127.0.0.1:8777/#/kanban')
await page.waitForSelector('.aim-header .aim-phase-chip-link')
const sample = async (tag) => {
  const v = await page.evaluate((t) => ({
    t, hash: location.hash,
    top: Math.round(document.querySelector('.aim-main').scrollTop),
    off: (() => { const el = document.getElementById('phase-cross_examine'); const s = document.querySelector('.aim-main')
      return el ? Math.round(el.getBoundingClientRect().top - s.getBoundingClientRect().top) : null })(),
    sh: Math.round(document.querySelector('.aim-main').scrollHeight),
  }), tag)
  console.log(v)
}
await page.locator('.aim-header .aim-phase-chip-link').click()
for (const ms of [0, 30, 80, 150, 300, 600, 1200]) {
  await page.waitForTimeout(ms === 0 ? 0 : ms)
  await sample(`+${ms}`)
}
await browser.close()
