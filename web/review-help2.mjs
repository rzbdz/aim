import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
p.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text().slice(0, 200)) })
await p.goto('http://127.0.0.1:8777/#/help', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
const info = await p.evaluate(() => ({
  mainText: (document.querySelector('.aim-main, main, #app')?.innerText || '').slice(0, 600),
  ids: [...document.querySelectorAll('[id]')].map(e => e.id).slice(0, 40),
  navLinks: [...document.querySelectorAll('a[href*="help"], .el-menu-item')].map(e => e.textContent.trim()),
  docHeight: document.documentElement.scrollHeight,
}))
console.log(JSON.stringify(info, null, 1))
await b.close()
