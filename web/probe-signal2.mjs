import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const read = async () => p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const sw = [...main.querySelectorAll('.el-switch')].map(e => ({ on: e.classList.contains('is-checked'), label: e.closest('label')?.innerText.trim() }))
  const cbs = [...main.querySelectorAll('.el-checkbox')].map(e => ({ on: e.classList.contains('is-checked'), label: e.innerText.trim().replace(/\s+/g,' ') }))
  const bodyRows = [...main.querySelectorAll('tbody tr')].length
  const countTxt = (main.innerText.match(/[\d,]+\s*(item|work item)s?\b/i) || [])[0] || ''
  const chips = [...main.querySelectorAll('.el-tag, .aim-filter-chip')].map(e => e.innerText.trim()).slice(0, 6)
  return { sw, cbs, bodyRows, countTxt, chips }
})
await p.goto('http://127.0.0.1:8777/#/items', { waitUntil: 'networkidle' }); await p.waitForTimeout(1000)
const unfiltered = await read()
console.log('UNFILTERED /items:', JSON.stringify(unfiltered))
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' }); await p.waitForTimeout(1000)
await p.evaluate(() => { const box = document.querySelector('.aim-attention-signals'); [...box.children].find(e => /Overdue/.test(e.innerText)).click() })
await p.waitForTimeout(1400)
console.log('url:', p.url())
console.log('AFTER CLICK:', JSON.stringify(await read()))
await b.close()
