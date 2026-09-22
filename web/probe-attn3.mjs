import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const m = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const mainTop = main.getBoundingClientRect().top + main.scrollTop
  const secs = [...main.children].map(el => ({
    tag: el.tagName, cls: (el.className || '').toString().slice(0, 50),
    top: Math.round(el.getBoundingClientRect().top + main.scrollTop - mainTop),
    h: Math.round(el.getBoundingClientRect().height),
    head: el.innerText.trim().split('\n').slice(0, 2).join(' / ').slice(0, 70),
  }))
  return { client: main.clientHeight, scroll: main.scrollHeight, secs }
})
console.log('viewport', m.client, 'content', m.scroll)
for (const s of m.secs) console.log(String(s.top).padStart(5), 'h=' + String(s.h).padStart(5), s.cls || s.tag, '::', s.head)
console.log('--- first screen shows up to top<', m.client)
await b.close()
