import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1300)
await p.click('.el-select'); await p.waitForTimeout(600)
await p.evaluate(() => {
  const o = [...document.querySelectorAll('.el-select-dropdown__item')].find(e => /^codex/.test(e.innerText.trim()))
  o.click()
})
await p.waitForTimeout(1600)
console.log('hash:', await p.evaluate(() => location.hash))
console.log('viewer chip:', await p.evaluate(() => document.querySelector('.el-select')?.innerText.trim()))
const r = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const card = [...document.querySelectorAll('.el-card')].find(x => /Work needing you now/i.test(x.innerText))
  return {
    heroLine: main.innerText.split('\n').slice(0, 12).join(' | '),
    cardRows: card ? [...card.querySelectorAll('.aim-attention-row')].map(x => x.innerText.replace(/\s+/g,' ').slice(0, 60)) : 'no card',
    empties: [...main.querySelectorAll('.el-empty')].map(e => e.innerText.replace(/\s+/g,' ').slice(0, 90)),
  }
})
console.log(JSON.stringify(r, null, 1))
await b.close()
