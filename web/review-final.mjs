import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(900)
await p.screenshot({ path: '/tmp/light-attention.png' })
console.log('theme class on <html>:', JSON.stringify(await p.evaluate(() => document.documentElement.className)))
await b.close()
