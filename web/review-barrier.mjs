import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
await p.goto('http://127.0.0.1:8777/#/barrier', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const info = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const tabs = [...document.querySelectorAll('.el-tabs__item')].map(t => ({
    label: t.textContent.trim(), active: t.classList.contains('is-active'), cls: t.className,
  }))
  return {
    hash: location.hash,
    mainText: main.innerText.replace(/\s+/g, ' ').slice(0, 400),
    textLen: main.innerText.trim().length,
    tabs,
    inputs: document.querySelectorAll('.el-main input, .el-main textarea').length,
    cards: document.querySelectorAll('.el-main .el-card').length,
    panels: document.querySelectorAll('.el-tab-pane').length,
  }
})
console.log(JSON.stringify(info, null, 1))
await b.close()
