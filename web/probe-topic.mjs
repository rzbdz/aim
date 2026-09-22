import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForTimeout(900)
const r = await p.evaluate(() => {
  const hits = []
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue
    const t = el.textContent.trim()
    if (!t.includes('Transport test') && !t.includes('file-first, phase-gated')) continue
    const chain = []
    let n = el
    while (n && n !== document.body) { chain.push(n.tagName + '.' + (n.className || '').toString().split(' ').filter(Boolean).join('.')); n = n.parentElement }
    hits.push({ text: t.slice(0, 120), chain: chain.slice(0, 6) })
  }
  return hits
})
console.log(JSON.stringify(r, null, 1))
await b.close()
