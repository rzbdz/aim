import { chromium } from 'playwright'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await page.goto('http://127.0.0.1:8777/#/chat')
await page.waitForSelector('.aim-thread')
console.log(await page.evaluate(() => [...document.querySelectorAll('.aim-thread')].map((r) => {
  const spans = [...r.querySelectorAll('span')].map((s) => s.textContent.trim())
  return { text: r.textContent.trim().slice(0, 70), spans, unread: r.querySelector('.aim-unread')?.textContent?.trim() || '' }
})))
await browser.close()
