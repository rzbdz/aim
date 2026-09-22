import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
const r = await p.evaluate(() => {
  const rows = [...document.querySelectorAll('.aim-thread')].map(el => ({
    text: el.innerText.replace(/\s+/g, ' ').slice(0, 90),
    active: el.className.includes('active') || el.className.includes('is-'),
    cls: el.className,
  }))
  const head = document.querySelector('.aim-reader-head')?.innerText.replace(/\s+/g, ' ').slice(0, 120)
  const h = document.querySelector('.aim-history')
  return { head, rows, url: location.hash,
    gap: h ? Math.round(h.scrollHeight - h.clientHeight - h.scrollTop) : null,
    msgs: h ? h.querySelectorAll('.aim-msg').length : 0 }
})
console.log('url:', r.url)
console.log('reader head:', r.head)
console.log('gap to bottom:', r.gap, 'msgs:', r.msgs)
console.log('thread rows:')
for (const x of r.rows) console.log('  ', x.active ? 'OPEN' : '    ', x.text)
await b.close()
