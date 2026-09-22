import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/barrier', { waitUntil: 'networkidle' })
await p.waitForTimeout(1600)
console.log('url:', await p.evaluate(() => location.hash))
const r = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const top = main.getBoundingClientRect().top
  const secs = [...main.querySelectorAll(':scope > *')].map(el => {
    const rc = el.getBoundingClientRect()
    return { cls: (el.className||'').toString().slice(0,52), top: Math.round(rc.top - top + main.scrollTop), h: Math.round(rc.height),
             head: el.innerText.trim().split('\n').slice(0, 2).join(' / ').slice(0, 84) }
  })
  return {
    client: main.clientHeight, scroll: main.scrollHeight,
    tabs: [...main.querySelectorAll('.el-tabs__item')].map(e => ({ t: e.innerText.trim(), active: e.className.includes('is-active') })),
    headings: [...main.querySelectorAll('h1,h2,h3,h4')].map(e => e.innerText.replace(/\s+/g,' ').slice(0, 70)),
    buttons: [...main.querySelectorAll('button')].map(e => e.innerText.replace(/\s+/g,' ').trim().slice(0, 34)).filter(Boolean),
    selects: [...main.querySelectorAll('.el-select')].map(e => e.innerText.replace(/\s+/g,' ').trim().slice(0, 30)),
    textLen: main.innerText.length,
    secs,
  }
})
console.log('scroller', r.client, '/', r.scroll, 'textLen', r.textLen)
console.log('TABS:', JSON.stringify(r.tabs))
console.log('HEADINGS:', JSON.stringify(r.headings))
console.log('BUTTONS:', JSON.stringify(r.buttons))
console.log('SELECTS:', JSON.stringify(r.selects))
console.log('SECTIONS:')
for (const s of r.secs) console.log(' ', String(s.top).padStart(5), 'h=' + String(s.h).padStart(5), s.cls, '::', s.head)
await b.close()
