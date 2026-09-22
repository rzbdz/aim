import { chromium } from 'playwright'
const BASE = 'http://127.0.0.1:8777'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const rev = await (await fetch(BASE + '/api/revision')).json()
console.log('REVISION', rev.bundle.revision, 'stale=', rev.stale, 'built', rev.bundle.built_at)

// --- Help: does it name the product surfaces? ---
await p.goto(BASE + '/#/help', { waitUntil: 'networkidle' }); await p.waitForTimeout(1200)
const named = await p.evaluate(() => {
  const t = document.body.innerText
  const words = ['Kanban','Gantt','Conversations','chat','drawer','Attention','Reports','Plan','barrier','Audit','milestone','cycle','project','epic','hours','estimate','priority','unread','M0','D7','R1']
  const out = {}
  for (const w of words) out[w] = t.includes(w)
  const anchors = [...document.querySelectorAll('[id]')].map(e=>e.id).filter(i=>/^(concept|phase|access|independent|human|acting)/.test(i))
  return { out, anchors, len: t.length }
})
console.log('HELP names:', JSON.stringify(named.out))
console.log('HELP anchors:', named.anchors.length, JSON.stringify(named.anchors))
// deep-link test
for (const frag of ['#/help#concept-drift','#/help#phase-commit','#/help#acting-on-an-item','#/help#no-such-anchor']) {
  await p.goto(BASE + '/' + frag, { waitUntil: 'networkidle' }); await p.waitForTimeout(900)
  const r = await p.evaluate(() => {
    const m = document.querySelector('.el-main')
    const has = location.hash.split('#')[2]
    const el = has ? document.getElementById(has) : null
    return { hash: location.hash, scrollTop: Math.round(m.scrollTop), target: !!el, targetY: el ? Math.round(el.getBoundingClientRect().top) : null }
  })
  console.log('DEEPLINK', frag, JSON.stringify(r))
}

// --- Barrier: per channel tab, the refusals card and the leader's lever ---
await p.goto(BASE + '/#/barrier', { waitUntil: 'networkidle' }); await p.waitForTimeout(1400)
const tabs = await p.evaluate(() => [...document.querySelectorAll('.el-tabs__item')].map(t => t.innerText.trim()))
console.log('BARRIER tabs:', JSON.stringify(tabs))
for (const t of tabs) {
  const tab = p.locator('.el-tabs__item', { hasText: t }).first()
  if (await tab.count()) { await tab.click(); await p.waitForTimeout(900) } else continue
  const r = await p.evaluate(() => {
    const vis = (sel) => [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().height > 0)
    const heads = vis('.aim-card, .el-card, section').map(e => ({ t: (e.innerText||'').replace(/\s+/g,' ').slice(0,60), h: Math.round(e.getBoundingClientRect().height) }))
    const refl = [...document.querySelectorAll('*')].filter(e => /^refusals —/.test((e.innerText||'').trim()) && e.children.length < 3).map(e => e.innerText.replace(/\s+/g,' ').slice(0,60))
    const seals = document.body.innerText.match(/seals —[^\n]*/g)
    return { heads: heads.slice(0,8), refl: [...new Set(refl)].slice(0,3), seals: [...new Set(seals||[])].slice(0,2),
             sh: Math.round(document.querySelector('.el-main').scrollHeight) }
  })
  console.log('TAB', t, JSON.stringify(r))
}
const acts = await p.evaluate(() => [...document.querySelectorAll('button')].filter(e=>e.offsetParent!==null)
  .map(e => ({ t: e.innerText.trim().slice(0,40), y: Math.round(e.getBoundingClientRect().top), dis: e.disabled||e.getAttribute('aria-disabled')==='true' })))
console.log('BARRIER buttons (final tab):', JSON.stringify(acts))
await b.close()
