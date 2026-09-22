import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 120)) })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const before = await p.evaluate(() => ({
  rows: document.querySelectorAll('.aim-attention-row').length,
  promises: document.querySelectorAll('.aim-promise').length,
  selects: [...document.querySelectorAll('.el-select')].map(s => s.textContent.trim().slice(0, 30)),
  hash: location.hash,
}))
console.log('before:', JSON.stringify(before))
// open the owner select (first el-select) and pick codex
const sel = p.locator('.el-select').first()
await sel.click()
await p.waitForTimeout(400)
const opts = await p.evaluate(() => [...document.querySelectorAll('.el-select-dropdown__item')].map(o => o.textContent.trim()))
console.log('options:', JSON.stringify(opts))
const codexOpt = p.locator('.el-select-dropdown__item', { hasText: 'codex' }).first()
if (await codexOpt.count()) { await codexOpt.click(); await p.waitForTimeout(900) } else console.log('no codex option')
const after = await p.evaluate(() => ({
  rows: document.querySelectorAll('.aim-attention-row').length,
  rowsText: [...document.querySelectorAll('.aim-attention-row')].map(r => r.innerText.replace(/\s+/g, ' ').slice(0, 70)).slice(0, 6),
  hash: location.hash,
  body: document.body.innerText.slice(0, 0),
}))
console.log('after:', JSON.stringify(after, null, 1))
console.log('errors:', errs.slice(0, 2))
await b.close()
