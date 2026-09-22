import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
for (const url of ['#/barrier', '#/barrier?channel=hello', '#/barrier?channel=barrier-v0']) {
  await p.goto('http://127.0.0.1:8777/' + url, { waitUntil: 'networkidle' })
  await p.waitForTimeout(1000)
  const t = await p.evaluate(() => {
    const main = document.querySelector('.el-main')
    return {
      textLen: main.innerText.trim().length,
      activeTabs: [...document.querySelectorAll('.el-tabs__item')].filter(e => e.classList.contains('is-active')).length,
      head: main.innerText.replace(/\s+/g, ' ').slice(0, 130),
    }
  })
  console.log(url.padEnd(28), 'text', String(t.textLen).padStart(5), '| active tabs', t.activeTabs, '|', t.head)
}
await b.close()
