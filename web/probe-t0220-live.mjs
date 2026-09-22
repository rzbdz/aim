/* T-0220 acceptance, on the live board: click the #hello tab, read the URL and the rows. */
import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/barrier', { waitUntil: 'networkidle' })
await p.waitForTimeout(1200)
const before = { url: p.url(), rows: await p.locator('.el-tab-pane:visible .aim-refusal-table .el-table__body tr').count() }
await p.locator('.el-tabs__item').filter({ hasText: '#hello' }).click()
await p.waitForTimeout(1200)
const after = { url: p.url(), rows: await p.locator('.el-tab-pane:visible .aim-refusal-table .el-table__body tr').count(),
                header: (await p.locator('.el-tab-pane:visible .el-card__header').filter({ hasText: 'refusals' }).innerText()).replace(/\s+/g, ' ') }
console.log('before:', JSON.stringify(before))
console.log('after :', JSON.stringify(after))
console.log('verdict:', after.url.includes('channel=hello') && after.rows > 0 ? 'PASS' : 'FAIL')
await b.close()
