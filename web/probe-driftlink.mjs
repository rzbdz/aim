import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1300)
const before = await p.evaluate(() => document.querySelector('.el-main').scrollTop)
await p.evaluate(() => {
  const a = [...document.querySelector('.aim-attention-signals').children].find(e => /Plan disagreements/.test(e.innerText))
  a.click()
})
await p.waitForTimeout(1500)
const after = await p.evaluate(() => ({ url: location.hash, scrollTop: document.querySelector('.el-main').scrollTop }))
console.log('clicking the "Plan disagreements" tile:')
console.log('  scrollTop before:', before, '-> after:', after.scrollTop)
console.log('  url:', after.url)
// does /plan render M0 as a link? compare with /attention
await p.goto('http://127.0.0.1:8777/#/plan', { waitUntil: 'networkidle' }); await p.waitForTimeout(1200)
const plan = await p.evaluate(() => {
  const main = document.querySelector('.el-main')
  const hits = []
  for (const el of main.querySelectorAll('*')) {
    if (el.children.length) continue
    if (!/^M\d+$/.test(el.textContent.trim())) continue
    const a = el.closest('a, button, [role=button]')
    hits.push({ id: el.textContent.trim(), wrapped: a ? a.tagName + '.' + (a.className||'').toString().split(' ')[0] : null, href: a?.getAttribute?.('href') || null })
  }
  return hits
})
console.log('/plan milestone identifiers:', JSON.stringify(plan, null, 1))
await b.close()
