import { chromium } from 'playwright'
import { unlinkSync } from 'node:fs'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const logs = []
p.on('console', m => logs.push(m.type() + ': ' + m.text().slice(0, 200)))
p.on('pageerror', e => logs.push('PAGEERROR: ' + String(e.message).slice(0, 200)))
await p.goto('http://127.0.0.1:8931/#/', { waitUntil: 'networkidle' })
await p.waitForTimeout(500)
unlinkSync('/tmp/aim-head/web/dist/assets/ChatPane-DfLN8GUl.js')
await p.evaluate(() => { location.hash = '#/chat' })
await p.waitForTimeout(1500)
console.log('url:', p.url())
console.log('console during failure:')
for (const l of logs) console.log('  ' + l)
const preload = await p.evaluate(() => window.__preloadErrSeen === true)
console.log('vite:preloadError listener present in app?', await p.evaluate(() => !!window.__vite_preload_error_handled))
await b.close()
