import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
for (const url of ['#/items', '#/items?owner=codex', '#/items?owner=claude-session1']) {
  await p.goto('http://127.0.0.1:8777/' + url, { waitUntil: 'networkidle' })
  await p.waitForTimeout(1100)
  const r = await p.evaluate(() => {
    const main = document.querySelector('.el-main')
    const rows = [...main.querySelectorAll('tbody tr')]
    const ids = rows.map(t => t.innerText.trim().split(/\s|$/)[0]).filter(s => /^T-\d+/.test(s))
    const ownerSel = [...main.querySelectorAll('.el-select')].map(e => e.innerText.replace(/\s+/g,' ').trim().slice(0, 30))
    return { n: rows.length, first: ids.slice(0, 4), last: ids.slice(-2), selects: ownerSel.slice(0, 6),
             empty: /no work item|nothing|empty/i.test(main.innerText) ? (main.innerText.match(/no [^\n]{0,40}/i)||[''])[0] : '' }
  })
  console.log(url, JSON.stringify(r))
}
await b.close()
