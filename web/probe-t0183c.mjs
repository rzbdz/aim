import { chromium } from 'playwright'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 700 } })
const read = (tag) => page.evaluate((t) => ({
  tag: t, url: location.hash,
  scrollTop: Math.round(document.querySelector('.aim-main').scrollTop),
  max: Math.round(document.querySelector('.aim-main').scrollHeight - document.querySelector('.aim-main').clientHeight),
}), tag)
await page.goto('http://127.0.0.1:8777/#/items')
await page.waitForSelector('.el-table__row')
await page.evaluate(() => { const m = document.querySelector('.aim-main'); m.scrollTop = m.scrollHeight })
await page.waitForTimeout(300)
console.log(await read('items at bottom'))
await page.locator('.el-menu-item').filter({ hasText: 'Help & concepts' }).click()
await page.waitForTimeout(800)
console.log(await read('-> help'))
await page.locator('.el-menu-item').filter({ hasText: 'Attention' }).click()
await page.waitForTimeout(800)
console.log(await read('-> attention'))
await browser.close()
