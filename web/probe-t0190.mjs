// T-0190 measurement: what /#/plan says about drift, and what it draws.
//
// Read-only. It prints the rendered alert sentence verbatim (the thing the card
// claims is false), then counts the drift rows the pane itself draws, then asks
// /api/state what the 87 actually are, so the sentence and the payload can be
// compared mechanically instead of by eye.
import { chromium } from 'playwright'

const url = process.env.AIM_URL || 'http://127.0.0.1:8777'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text().slice(0, 200)) })

await page.goto(`${url}/#/plan`, { waitUntil: 'domcontentloaded' })
// Wait for the thing being measured, not for a stopwatch. `networkidle` never
// settles on this board (the header polls) and a fixed sleep is what a build
// under this process can outlast: measured 2026-09-22, the same read returned
// "0 rows" three times in six until it waited on `#plan-drift article` instead.
try {
  await page.waitForSelector('#plan-drift article, .el-main .el-alert', { timeout: 20000 })
} catch { /* the run below reports the empty page as the measurement it is */ }

const rendered = await page.evaluate(() => {
  // textContent, not innerText: innerText is '' for anything the browser considers
  // not rendered yet, and this probe's job is to quote the sentence, not to guess
  // whether the pane had painted at the moment it was read.
  const alert = document.querySelector('.el-main .el-alert')
  const rows = [...document.querySelectorAll('.el-main article, .el-main tr')]
  const driftRows = [...document.querySelectorAll('.el-main article')].filter((a) => /plan says/.test(a.innerText))
  return {
    sentence: (alert?.textContent || '(no alert)').replace(/\s+/g, ' ').trim(),
    driftRowsDrawn: driftRows.length,
    rowCount: rows.length,
    // Does the pane name the absent-record case anywhere at all?
    saysNotRecorded: /not recorded/i.test(document.querySelector('.el-main')?.innerText || ''),
    promises: document.querySelectorAll('.aim-main .aim-promise').length,
  }
})

const state = await (await page.request.get(`${url}/api/state`)).json()
const drift = state.drift || []
const nullStore = drift.filter((d) => d.store === null || d.store === undefined)
const withStore = drift.filter((d) => d.store !== null && d.store !== undefined)
const tasks = Object.values(state.tasks || {})
const noDue = tasks.filter((t) => !t.due)
const seedNoDue = noDue.filter((t) => String(t.provenance || '').includes('seed')).length

console.log('rendered /#/plan alert:')
console.log('  ' + rendered.sentence)
console.log('  drift rows drawn by the pane:', rendered.driftRowsDrawn)
console.log('  pane text contains "not recorded":', rendered.saysNotRecorded)
console.log('  promise chips on the page:', rendered.promises)
console.log('api/state:')
console.log('  drift entries:', drift.length, '| store null:', nullStore.length, '| store has a value:', withStore.length)
console.log('  distinct field names:', [...new Set(drift.map((d) => d.field))].join(', '))
console.log('  without a due date:', noDue.length, '(seeds among them:', seedNoDue, ')')
await browser.close()
