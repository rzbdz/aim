import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 120)) })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
const out = await p.evaluate(() => {
  const classes = {}
  for (const el of document.querySelectorAll('*')) {
    const c = typeof el.className === 'string' ? el.className : ''
    for (const k of c.split(/\s+/)) if (k) classes[k] = (classes[k] || 0) + 1
  }
  return {
    text: document.body.innerText.slice(0, 1200),
    top: Object.entries(classes).sort((a, b) => b[1] - a[1]).slice(0, 25),
    selects: [...document.querySelectorAll('select')].map(s => ({ name: s.name || s.id, opts: [...s.options].map(o => o.value) })),
    buttons: [...document.querySelectorAll('button')].map(x => x.textContent.trim()).slice(0, 20),
  }
})
console.log('TEXT:\n' + out.text)
console.log('\nTOP CLASSES:', JSON.stringify(out.top))
console.log('\nSELECTS:', JSON.stringify(out.selects).slice(0, 600))
console.log('\nBUTTONS:', JSON.stringify(out.buttons))
console.log('errors:', errs.slice(0, 3))
await b.close()
