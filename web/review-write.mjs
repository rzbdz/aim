import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForTimeout(1000)
const state = await p.evaluate(() => ({
  composer: Boolean(document.querySelector('.aim-composer textarea')),
  sendButton: [...document.querySelectorAll('.aim-composer button')].map(b => b.textContent.trim()),
  readOnlyNotice: document.querySelector('.aim-composer')?.innerText.includes('without') || false,
  composerText: document.querySelector('.aim-composer')?.innerText.replace(/\s+/g, ' ').slice(0, 120),
  threadCount: document.querySelectorAll('.aim-thread').length,
  theme: document.documentElement.className || '(light)',
}))
console.log(JSON.stringify(state, null, 1))
await p.screenshot({ path: '/tmp/final-chat.png' })
await b.close()
