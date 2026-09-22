import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
const total = await p.evaluate(() => document.querySelectorAll('.aim-thread').length)
// find and click the "needs me" filter
const filters = await p.evaluate(() => [...document.querySelectorAll('.aim-chat-side .el-checkbox, .aim-chat-side .el-select, .aim-chat-side .el-radio-group')].map(e => e.innerText.replace(/\s+/g,' ').trim()))
console.log('sidebar filters:', JSON.stringify(filters))
await p.evaluate(() => {
  const cb = [...document.querySelectorAll('.aim-chat-side .el-checkbox')].find(e => /needs me/i.test(e.innerText))
  cb?.click()
})
await p.waitForTimeout(1200)
const after = await p.evaluate(() => ({
  url: location.hash,
  rows: [...document.querySelectorAll('.aim-thread')].map(e => e.innerText.replace(/\s+/g,' ').slice(0, 60)),
}))
console.log('total threads:', total, '-> needs me:', after.rows.length)
console.log('url', after.url)
for (const r of after.rows) console.log('   ', r)
// chips actually rendered in the open reader
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' }); await p.waitForTimeout(1200)
const chips = await p.evaluate(() => {
  const out = {}
  for (const t of document.querySelectorAll('.aim-msg header .el-tag')) out[t.innerText.trim()] = (out[t.innerText.trim()]||0)+1
  return out
})
console.log('message chips rendered:', JSON.stringify(chips))
const sample = await p.evaluate(() => {
  const h = document.querySelector('.aim-history')
  const withChip = [...h.querySelectorAll('.aim-msg')].filter(m => m.querySelector('header .el-tag')).slice(0, 3)
  return withChip.map(m => ({ ts: m.querySelector('header')?.innerText.replace(/\s+/g,' ').slice(0,70), chips: [...m.querySelectorAll('header .el-tag')].map(c=>c.innerText.trim()) }))
})
console.log('sample chipped messages:', JSON.stringify(sample, null, 1))
await b.close()
