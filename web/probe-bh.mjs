import { chromium } from 'playwright'
const BASE = 'http://127.0.0.1:8777'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0,160)) })

const rev = await (await fetch(BASE + '/api/revision')).json()
console.log('REVISION', JSON.stringify(rev))

async function scope() {
  return await p.evaluate(() => {
    const scrollers = [...document.querySelectorAll('div,main,section')]
      .filter(e => e.scrollHeight - e.clientHeight > 40)
      .map(e => ({ cls: (e.className||'').toString().slice(0,60), sh: e.scrollHeight, ch: e.clientHeight, top: Math.round(e.getBoundingClientRect().top) }))
      .sort((a,b) => b.sh - a.sh)
    const s = scrollers[0] || null
    const root = s ? [...document.querySelectorAll('div,main,section')].find(e => (e.className||'').toString() === s.cls) : null
    const headings = [...document.querySelectorAll('h1,h2,h3,h4,.aim-card__title,.el-card__header,.el-collapse-item__header')]
      .map(e => ({ tag: e.tagName.toLowerCase(), t: (e.innerText||'').replace(/\s+/g,' ').trim().slice(0,90),
                   y: Math.round(e.getBoundingClientRect().top), h: Math.round(e.getBoundingClientRect().height) }))
    const controls = [...document.querySelectorAll('button,a.el-link,button.el-button,.el-button')]
      .filter(e => e.offsetParent !== null)
      .map(e => ({ t: (e.innerText||'').replace(/\s+/g,' ').trim().slice(0,60),
                   y: Math.round(e.getBoundingClientRect().top),
                   href: e.getAttribute('href') || '',
                   disabled: e.disabled === true || e.getAttribute('aria-disabled') === 'true',
                   cls: (e.className||'').toString().slice(0,40) }))
    const ids = [...document.querySelectorAll('[id]')].map(e => e.id).slice(0, 80)
    const enums = (document.body.innerText.match(/\b[A-Z][A-Z_]{3,}\b/g) || [])
    const counts = [...new Set(enums)].slice(0, 20)
    const rows = [...document.querySelectorAll('table')].map(t => ({ rows: t.querySelectorAll('tbody tr').length,
      head: [...t.querySelectorAll('thead th')].map(h => h.innerText.trim().slice(0,24)) }))
    const ofN = (document.body.innerText.match(/\b\d+\s+(of|more,)\s+\d+\b/g) || []).slice(0,12)
    const text = document.body.innerText
    return { scrollers: scrollers.slice(0,4), headings, controls, ids, enumCounts: counts, rows, ofN,
             textLen: text.length, textHead: text.slice(0, 1200) }
  })
}

for (const route of ['#/barrier', '#/help']) {
  await p.goto(BASE + '/' + route, { waitUntil: 'networkidle' })
  await p.waitForTimeout(1500)
  const s = await scope()
  console.log('\n===== ' + route + ' =====')
  console.log('SCROLLERS', JSON.stringify(s.scrollers))
  console.log('HEADINGS', JSON.stringify(s.headings, null, 1))
  console.log('CONTROLS', JSON.stringify(s.controls, null, 1))
  console.log('ROWS', JSON.stringify(s.rows))
  console.log('OF-N', JSON.stringify(s.ofN))
  console.log('ENUMS', JSON.stringify(s.enumCounts))
  console.log('IDS', JSON.stringify(s.ids))
  console.log('TEXT', JSON.stringify(s.textHead))
  console.log('TEXTLEN', s.textLen)
}
console.log('\nERRORS', JSON.stringify(errs.slice(0,4)))
await b.close()
