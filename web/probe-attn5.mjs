import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1300)
const r = await p.evaluate(() => {
  const card = [...document.querySelectorAll('.el-card')].find(c => /Next milestones/i.test(c.innerText))
  if (!card) return 'no milestones card'
  const rows = [...card.querySelectorAll('article, li, tr, .aim-attention-row')].map(el => {
    const interactive = el.querySelector('a, button, [role=button], [tabindex]')
    return { text: el.innerText.replace(/\s+/g,' ').slice(0, 80), interactive: interactive ? interactive.tagName + '.' + (interactive.className||'').toString().split(' ')[0] : null }
  })
  const links = [...card.querySelectorAll('a')].map(a => ({ t: a.innerText.trim(), href: a.getAttribute('href') }))
  return { rows, links, text: card.innerText.replace(/\s+/g,' ').slice(0, 300) }
})
console.log(JSON.stringify(r, null, 1))
console.log('=== signal tile tags ===')
console.log(JSON.stringify(await p.evaluate(() => [...document.querySelector('.aim-attention-signals').children].map(e => ({ tag: e.tagName, href: e.getAttribute('href'), head: e.innerText.split('\n')[0], rest: e.innerText.split('\n').slice(1).join(' ') }))), null, 1))
await b.close()
