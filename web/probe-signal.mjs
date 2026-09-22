import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const sig = await p.evaluate(() => {
  const box = document.querySelector('.aim-attention-signals')
  if (!box) return 'missing'
  return [...box.children].map(el => {
    const clickable = el.tagName === 'A' || el.tagName === 'BUTTON' || !!el.onclick || el.getAttribute('role') === 'button' || el.hasAttribute('tabindex')
    return { tag: el.tagName, clickable, text: el.innerText.trim().replace(/\s+/g, ' ').slice(0, 44) }
  })
})
console.log('signal tiles:'); console.log(JSON.stringify(sig, null, 1))
// click the Overdue tile
await p.evaluate(() => {
  const box = document.querySelector('.aim-attention-signals')
  const el = [...box.children].find(e => /Overdue/.test(e.innerText))
  el.click()
})
await p.waitForTimeout(1500)
console.log('after clicking Overdue ->', p.url())
const state = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  return { rows: (main.innerText.match(/^T-\d{4}/gm) || []).length, head: main.innerText.split('\n').slice(0, 8).join(' | ') }
})
console.log('items page:', JSON.stringify(state))
await b.close()
