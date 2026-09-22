import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForSelector('.aim-thread')
const rows = p.locator('.aim-thread')
const n = await rows.count()
for (let i = 0; i < n; i++) {
  const label = (await rows.nth(i).locator('span').first().textContent()).trim()
  if (label === 'codex ⇄ human') { await rows.nth(i).click(); break }
}
await p.waitForTimeout(600)
const chips = await p.$$eval('.aim-msg', els => els.map(e => ({
  by: e.querySelector('.aim-dim + .aim-dim')?.textContent?.trim() || e.querySelectorAll('.aim-dim')[0]?.textContent?.trim(),
  chips: [...e.querySelectorAll('.el-tag')].map(t => t.textContent.trim()),
})))
console.log('chips rendered in a DM thread:'); console.log(JSON.stringify(chips, null, 1))
await b.close()
