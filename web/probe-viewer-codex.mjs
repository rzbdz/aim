import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1400)
const hdr = await p.evaluate(() => {
  const sel = document.querySelector('.el-aside .el-select, .el-header .el-select, header .el-select')
  return { html: sel?.outerHTML.slice(0, 300), label: sel?.previousElementSibling?.innerText || sel?.parentElement?.innerText.replace(/\s+/g,' ').slice(0,60) }
})
console.log('header select:', JSON.stringify(hdr, null, 1))
// open it and read the options
await p.click('.el-select')
await p.waitForTimeout(700)
console.log('options:', JSON.stringify(await p.evaluate(() => [...document.querySelectorAll('.el-select-dropdown__item')].map(e => ({ t: e.innerText.trim(), sel: e.className.includes('selected') })))))
await b.close()
