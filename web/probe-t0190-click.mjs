import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)) })
p.on('pageerror', (e) => errs.push('PAGEERROR ' + String(e.message).slice(0, 200)))
await p.goto('http://127.0.0.1:8777/#/plan', { waitUntil: 'domcontentloaded' })
// Wait on the control, not on a stopwatch: `networkidle` never settles on this
// board, and this probe once read `rows: 0` off a card that had 20 rows a moment
// later. A probe that reports an unpainted page as a measurement is the same
// class of error as the sentence T-0190 is about.
await p.waitForSelector('#plan-drift article', { timeout: 20000 })
const card = p.locator('#plan-drift')
const read = async () => ({
  rows: await card.locator('article').count(),
  chips: await card.locator('article .aim-promise').count(),
  control: (await card.getByRole('button', { name: /show (all|only)/ }).innerText()).trim(),
})
console.log('collapsed:', JSON.stringify(await read()))
await card.getByRole('button', { name: /show (all|only)/ }).click()
await p.waitForTimeout(400)
console.log('expanded :', JSON.stringify(await read()))
await card.getByRole('button', { name: /show (all|only)/ }).click()
await p.waitForTimeout(300)
console.log('re-collapsed:', JSON.stringify(await read()))
console.log('differing card rows:', await p.locator('#plan-drift-differs article').count())
console.log('console errors:', errs.length ? errs : 'none')
await b.close()
