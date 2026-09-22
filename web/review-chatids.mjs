import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForTimeout(1000)
const res = await p.evaluate(() => {
  const re = /\b(T-\d{3,4}|M\d{1,2}|D\d{1,2}|R\d{1,2})\b/
  const out = { chips: [], chipRows: 0, deadInUi: [] }
  for (const msg of document.querySelectorAll('.aim-msg')) {
    for (const tag of msg.querySelectorAll('.el-tag')) {
      const txt = tag.textContent.trim()
      out.chipRows++
      out.chips.push(txt)
    }
  }
  for (const a of document.querySelectorAll('.aim-msg header a, .aim-thread')) void a
  // UI text outside message bodies and outside the sidebar nav
  const walker = document.createTreeWalker(document.querySelector('.aim-reader-head') || document.body, NodeFilter.SHOW_TEXT)
  let n
  while ((n = walker.nextNode())) {
    const t = n.textContent.trim()
    if (re.test(t) && t.length < 40) out.deadInUi.push(t.slice(0, 30))
  }
  return out
})
const uniq = {}
for (const c of res.chips) uniq[c] = (uniq[c] || 0) + 1
console.log('chips rendered in the open thread:', res.chipRows)
console.log('distinct chips:', JSON.stringify(uniq, null, 1))
console.log('identifier-like text in the reader header (non-body):', JSON.stringify(res.deadInUi))
await b.close()
