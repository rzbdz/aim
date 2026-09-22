import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForSelector('.aim-thread')
const rows = p.locator('.aim-thread')
for (let i = 0; i < await rows.count(); i++) {
  if ((await rows.nth(i).locator('span').first().textContent()).trim() === 'codex ⇄ human') {
    await rows.nth(i).click(); break
  }
}
await p.waitForTimeout(700)
const out = await p.evaluate(() => {
  const h = document.querySelector('.aim-history')
  const msgs = [...h.querySelectorAll('.aim-msg')].map(e => {
    const dims = [...e.querySelectorAll('.aim-dim')].map(d => d.textContent.trim())
    return { dir: dims.slice(0, 3).join(' '), ts: dims.find(d => /\d{4}-\d{2}-\d{2}/.test(d)) }
  })
  return {
    count: msgs.length,
    msgs,
    composer: document.querySelector('.aim-composer')?.innerText.replace(/\s+/g, ' ').slice(0, 130),
  }
})
console.log('messages in the merged thread:', out.count)
for (const m of out.msgs) console.log('  ', m.ts, '|', m.dir)
console.log('composer says:', out.composer)
await b.close()
