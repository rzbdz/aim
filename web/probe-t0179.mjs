// Probe only -- not a deliverable. Measures what a 404 chunk does in the CURRENT dist.
import { chromium } from 'playwright'

const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const logs = []
p.on('console', (m) => logs.push(`${m.type()}: ${m.text().slice(0, 160)}`))
p.on('pageerror', (e) => logs.push(`PAGEERROR: ${String(e.message).slice(0, 200)}`))

await p.route('**/assets/ChatPane-*.js', (route) => route.fulfill({ status: 404, body: 'nope' }))
await p.goto('http://127.0.0.1:8941/#/kanban', { waitUntil: 'networkidle' })
await p.waitForTimeout(400)
console.log('before:', p.url(), await p.locator('.aim-card').count(), 'cards')

await p.locator('.el-menu-item').filter({ hasText: 'Conversations' }).click()
await p.waitForTimeout(1500)
console.log('after :', p.url(), await p.locator('.aim-chat').count(), '.aim-chat')
console.log('page h2:', await p.locator('.aim-page h2').textContent().catch(() => '(none)'))
console.log('cards still there:', await p.locator('.aim-card').count())
console.log('deferred banner:', await p.locator('.aim-deferred').count())
console.log('--- console ---')
for (const l of logs) console.log('  ' + l)
const rejected = await p.evaluate(() => {
  window.__rejected = []
  window.addEventListener('unhandledrejection', (e) => window.__rejected.push(String(e.reason)))
  return true
})
await b.close()
