import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1400)
const card = await p.evaluate(() => {
  const c = [...document.querySelectorAll('.el-card')].find(x => /Work needing you now/i.test(x.innerText))
  if (!c) return 'no card'
  return {
    header: c.querySelector('.el-card__header')?.innerHTML.slice(0, 500),
    controls: [...c.querySelectorAll('input,select,button,.el-select,.el-checkbox,.el-radio,.el-tag')].map(e => e.tagName + '.' + (e.className||'').toString().split(' ')[0] + ' :: ' + (e.innerText||e.getAttribute('placeholder')||'').trim().slice(0,40)),
    rows: [...c.querySelectorAll('.aim-attention-row')].map(r => r.innerText.replace(/\s+/g,' ').slice(0, 70)),
  }
})
console.log(JSON.stringify(card, null, 1))
await b.close()
