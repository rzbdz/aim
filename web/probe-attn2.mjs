import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const m = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const txt = main.innerText
  const rows = txt.split('\n').filter(l => /^T-\d{4}$/.test(l.trim()))
  return {
    scrollHeight: main.scrollHeight,
    clientHeight: main.clientHeight,
    screens: +(main.scrollHeight / main.clientHeight).toFixed(1),
    driftRows: rows.length,
    totalChars: txt.length,
    headings: [...main.querySelectorAll('h1,h2,h3,h4,.el-card__header,.aim-section-title')].map(e => e.innerText.trim().replace(/\s+/g,' ').slice(0,60)),
  }
})
console.log(JSON.stringify(m, null, 1))
// are the drift rows clickable?
const click = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const el = [...main.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === 'T-0001')
  if (!el) return 'no row'
  let n = el, path = []
  while (n && n !== main) { path.push(n.tagName + (n.className ? '.' + n.className.toString().split(' ')[0] : '')); n = n.parentElement }
  const row = el.closest('tr,.el-card,[class*=row],li')
  return { path: path.slice(0, 5), rowTag: row?.tagName, rowClickable: !!(row && (row.onclick || row.getAttribute('role') === 'button' || row.tagName === 'A')), rowClasses: row?.className }
})
console.log('T-0001 element:', JSON.stringify(click, null, 1))
await b.close()
