import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/items', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const r = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const ids = [...main.innerText.matchAll(/\bT-\d{4}\b/g)].map(m => m[0])
  const uniq = [...new Set(ids)]
  const ghostVisible = uniq.includes('T-0002') || uniq.includes('T-0005')
  const rowFor = (id) => {
    const el = [...main.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === id)
    if (!el) return null
    const tr = el.closest('tr') || el.closest('.aim-attention-row') || el.closest('article')
    return tr ? tr.innerText.trim().replace(/\s+/g, ' ').slice(0, 120) : '(no row)'
  }
  return {
    totalIds: uniq.length, ghostVisible,
    T0001: rowFor('T-0001'), T0002: rowFor('T-0002'), T0004: rowFor('T-0004'), T0156: rowFor('T-0156'),
    pagination: [...main.querySelectorAll('.el-pagination')].length,
    rowCount: [...main.querySelectorAll('tbody tr')].length,
    headers: [...main.querySelectorAll('thead th')].map(e => e.innerText.trim()),
  }
})
console.log(JSON.stringify(r, null, 1))
await b.close()
