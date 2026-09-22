import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1400)
console.log('=== signal tiles ===')
console.log(JSON.stringify(await p.evaluate(() => [...document.querySelector('.aim-attention-signals').children].map(e => ({
  tag: e.tagName, href: e.getAttribute('href'), head: e.innerText.split('\n')[0], rest: e.innerText.split('\n').slice(1).join(' '),
  aria: e.getAttribute('aria-disabled'),
}))), null, 1))
console.log('=== first screen text ===')
console.log(await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  return main.innerText.split('\n').slice(0, 46).join(' | ')
}))
console.log('=== do seed rows carry a marker? ===')
console.log(JSON.stringify(await p.evaluate(() => {
  const out = []
  for (const card of document.querySelectorAll('.el-card')) {
    const head = card.querySelector('.el-card__header')?.innerText.trim().split('\n')[0] || ''
    if (!/Work needing you now|promises in the plan/i.test(head)) continue
    for (const row of card.querySelectorAll('.aim-attention-row')) {
      out.push({ card: head.slice(0, 30), text: row.innerText.replace(/\s+/g,' ').slice(0, 96) })
    }
  }
  return out
}), null, 1))
await b.close()
