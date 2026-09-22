import { chromium } from 'playwright'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 700 } })
const read = (t) => page.evaluate((tag) => ({
  tag, scrollTop: Math.round(document.querySelector('.aim-main').scrollTop),
  max: Math.round(document.querySelector('.aim-main').scrollHeight - document.querySelector('.aim-main').clientHeight),
}), t)
await page.goto('http://127.0.0.1:8777/#/items')
await page.waitForSelector('.el-table__row')
await page.waitForTimeout(1200)
console.log(await read('settled'))
await page.evaluate(() => { const m = document.querySelector('.aim-main'); m.scrollTop = 800 })
console.log(await read('set 800'))
await page.waitForTimeout(400)
console.log(await read('after 400ms'))
await page.waitForTimeout(2000)
console.log(await read('after 2.4s'))
await browser.close()
