import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForSelector('.aim-thread')

// 1. anchor on the busiest agent-to-agent DM thread
const rows = p.locator('.aim-thread')
const n = await rows.count()
let target = null
for (let i = 0; i < n; i++) {
  const label = (await rows.nth(i).locator('span').first().textContent()).trim()
  if (label === 'codex ⇄ claude-session1') target = rows.nth(i)
}
await target.click()
await p.waitForTimeout(600)
const anchor = await p.evaluate(() => {
  const h = document.querySelector('.aim-history')
  const marked = h.querySelector('.aim-anchor-message')
  const msgs = [...h.querySelectorAll('.aim-msg')]
  const idx = msgs.indexOf(marked)
  return {
    total: msgs.length,
    anchorIndex: idx,
    anchorStamp: marked?.querySelector('.aim-dim')?.textContent?.trim(),
    anchorIsInView: marked ? (marked.getBoundingClientRect().top - h.getBoundingClientRect().top) : null,
    scrollTop: Math.round(h.scrollTop),
    scrollHeight: h.scrollHeight,
    atBottom: Math.round(h.scrollTop + h.clientHeight) >= h.scrollHeight - 8,
  }
})
console.log('DM anchor:', JSON.stringify(anchor))

// 2. what does "needs me" leave on screen?
const before = await rows.count()
await p.getByText('needs me', { exact: true }).click()
await p.waitForTimeout(400)
const after = await rows.count()
const left = await p.$$eval('.aim-thread', els => els.map(e => e.querySelector('span')?.textContent?.trim()))
console.log(`needs-me: ${before} threads -> ${after}:`, JSON.stringify(left))
await b.close()
