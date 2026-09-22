import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const m = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const sec = document.querySelector('.aim-attention')
  const base = sec.getBoundingClientRect().top + main.scrollTop - main.scrollTop
  return [...sec.children].map(el => {
    const r = el.getBoundingClientRect()
    return { top: Math.round(r.top - sec.getBoundingClientRect().top), h: Math.round(r.height),
             cls: (el.className||'').toString().slice(0,44),
             head: el.innerText.trim().split('\n').slice(0,3).join(' / ').slice(0,80) }
  })
})
console.log('scroller visible height 951; sections inside .aim-attention (top is relative to that container)')
for (const s of m) console.log(String(s.top).padStart(5), 'h=' + String(s.h).padStart(5), s.cls, '::', s.head)
await b.close()
