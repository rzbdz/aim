import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/items', { waitUntil: 'networkidle' })
await p.waitForTimeout(1300)
const rows = await p.evaluate(() => {
  return [...document.querySelectorAll('tbody tr')].slice(0, 12).map((tr, i) => {
    const ctrl = tr.querySelector('.aim-task-link, button, a')
    return {
      i,
      rowText: tr.innerText.replace(/\s+/g, ' ').slice(0, 34),
      ctrlTag: ctrl ? ctrl.tagName + '.' + (ctrl.className || '').toString().split(' ')[0] : null,
      ctrlText: ctrl ? ctrl.innerText.trim() : null,
      ctrlTitle: ctrl ? (ctrl.getAttribute('title') || ctrl.getAttribute('aria-label') || '') : null,
      ctrlHref: ctrl ? ctrl.getAttribute('href') : null,
    }
  })
})
console.log(JSON.stringify(rows, null, 1))
await b.close()
