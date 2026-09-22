import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForTimeout(900)
// thread rows in the sidebar
const rows = await p.evaluate(() => {
  return [...document.querySelectorAll('.aim-main *')]
    .filter(e => e.children.length === 0 && /^#/.test(e.textContent.trim()))
    .slice(0, 12)
    .map(e => e.textContent.trim())
})
console.log('label-like:', JSON.stringify(rows))
const notes = await p.evaluate(() => {
  const out = []
  for (const el of document.querySelectorAll('.aim-main *')) {
    const t = el.textContent.trim()
    if (el.children.length === 0 && /in this phase|sealed to you/.test(t)) out.push(t)
  }
  return [...new Set(out)]
})
console.log('note strings:', JSON.stringify(notes, null, 1))
// open first channel thread and read the header note
await p.evaluate(() => {
  const el = [...document.querySelectorAll('.aim-main *')].find(e => e.children.length === 0 && e.textContent.trim() === '#hello')
  if (el) el.click()
})
await p.waitForTimeout(700)
const header = await p.evaluate(() => document.querySelector('.aim-main')?.innerText.split('\n').slice(0, 12))
console.log('header after opening #hello:', JSON.stringify(header, null, 1))
await b.close()
