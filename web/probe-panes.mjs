import { chromium } from 'playwright'
const CHANNEL = (id, phase, refusals) => ({
  id, phase, topic: `${id} topic`, leader: 'human', participants: ['codex'], round: 0,
  sealed: [], concessions: 0, tasks_recorded: 0, tasks_unknown_events: 0,
  chain: { 'log.jsonl': { state: 'OK', records: 2, why: 'fixture' } },
  refusals, history: [{ at: '2026-09-22T00:00:00.000Z', phase, by: 'human', note: '' }],
})
const REF = (agent, action, cls = 'barrier') => ({ ts: '2026-09-22T00:00:30.000Z', agent, action, class: cls, phase: 'SEALED_DIVERGENT', reason: `${agent} may not ${action}` })
const STATE = {
  digest: 'p', generated_at: '2026-09-22T00:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog','done'], terminal: ['done'], phase: 'SEALED_DIVERGENT', milestones: {},
  agents: { human: { kind: 'human', model: '' } }, register: {}, tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [CHANNEL('alpha','SEALED_DIVERGENT',[REF('codex','read_others')]),
             CHANNEL('hello','COMMIT',[REF('codex','read_others'),REF('codex','channel_say'),REF('claude-session1','advance'),REF('human','advance','form')]),
             CHANNEL('scratch','SYNTHESIS',[])],
  unacked: [], drift: [], withheld_tasks: 0, write: { enabled: false, as: '' },
}
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await page.route('**/api/state**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(STATE) }))
await page.route('**/api/digest**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }) }))
await page.goto('http://127.0.0.1:8777/#/barrier')
await page.waitForSelector('.el-tabs__item')
const sel = (css) => page.locator(css).count()
console.log('panes:', await page.evaluate(() => [...document.querySelectorAll('.el-tab-pane')].map((p) => ({
  cls: p.className, display: getComputedStyle(p).display,
  refusalRows: p.querySelectorAll('.aim-refusal-table .el-table__body tr').length,
}))))
for (const css of [
  '.aim-refusal-table .el-table__body tr',
  '.el-tab-pane:visible .aim-refusal-table .el-table__body tr',
  '.el-tab-pane:visible .el-table__body tr',
]) console.log(css, '=>', await sel(css))
await browser.close()
