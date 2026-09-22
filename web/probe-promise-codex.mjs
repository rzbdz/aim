import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
for (const who of ['human', 'codex', 'claude-session1']) {
  await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
  await p.waitForTimeout(1200)
  await p.click('.el-select'); await p.waitForTimeout(500)
  await p.evaluate((w) => {
    const o = [...document.querySelectorAll('.el-select-dropdown__item')].find(e => e.innerText.trim().startsWith(w))
    o.click()
  }, who)
  await p.waitForTimeout(1500)
  const r = await p.evaluate(() => {
    const card = [...document.querySelectorAll('.el-card')].find(x => /promises in the plan/i.test(x.innerText))
    const work = [...document.querySelectorAll('.el-card')].find(x => /Work needing you now/i.test(x.innerText))
    return {
      promise: card ? card.innerText.replace(/\s+/g,' ').slice(0, 150) : 'no promise card',
      promiseRows: card ? [...card.querySelectorAll('.aim-attention-row')].map(x => x.innerText.replace(/\s+/g,' ').slice(0, 70)) : [],
      workEmpty: work ? (work.querySelector('.el-empty')?.innerText.replace(/\s+/g,' ') || `${work.querySelectorAll('.aim-attention-row').length} rows`) : 'no work card',
    }
  })
  console.log('=== viewer', who, '===')
  console.log(JSON.stringify(r, null, 1))
}
await b.close()
