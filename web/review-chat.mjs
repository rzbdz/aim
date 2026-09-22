import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
const errs = []
p.on('pageerror', e => errs.push('pageerror: ' + e.message))
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForSelector('.aim-thread', { timeout: 15000 })
const rows = await p.$$eval('.aim-thread', els => els.map(e => ({
  label: e.querySelector('span')?.textContent?.trim(),
  preview: e.querySelectorAll('.aim-dim')[1]?.textContent?.trim()?.slice(0, 60),
  ts: e.querySelectorAll('.aim-dim')[0]?.textContent?.trim(),
})))
console.log(JSON.stringify(rows, null, 1))
console.log('pageerrors:', errs)
await p.screenshot({ path: '/tmp/chat.png', fullPage: false })
await b.close()
