import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
const routes = ['/', '/kanban', '/gantt', '/items', '/chat', '/reports', '/barrier', '/plan', '/help']
const IDENT = /\b(T-\d{3,4}|M\d{1,2}|D\d{1,2}|R\d{1,2}|msg-\d+|m\d{4})\b/
for (const r of routes) {
  await p.goto('http://127.0.0.1:8777/#' + r, { waitUntil: 'networkidle' })
  await p.waitForTimeout(800)
  const res = await p.evaluate((IDENT_SRC) => {
    const re = new RegExp(IDENT_SRC)
    const main = document.querySelector('.el-main') || document.body
    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT)
    const dead = [], live = []
    let n
    while ((n = walker.nextNode())) {
      const t = n.textContent.trim()
      if (!re.test(t) || t.length > 40) continue
      let el = n.parentElement, actionable = false, why = ''
      while (el && el !== main) {
        if (el.tagName === 'A' || el.getAttribute('role') === 'button' || el.hasAttribute('tabindex')) {
          actionable = true; why = el.tagName + (el.getAttribute('role') ? '[role=button]' : ''); break
        }
        el = el.parentElement
      }
      const ctx = (n.parentElement.closest('.el-card, article, tr') || n.parentElement)
        .innerText.replace(/\s+/g, ' ').slice(0, 70)
      ;(actionable ? live : dead).push({ id: t.slice(0, 30), ctx })
    }
    const controls = [...main.querySelectorAll('button, .el-select, .el-checkbox, input')]
      .filter(e => e.offsetParent !== null)
    return {
      deadCount: dead.length, liveCount: live.length,
      deadExamples: dead.slice(0, 6),
      disabled: controls.filter(e => e.disabled || e.getAttribute('aria-disabled') === 'true').length,
      controls: controls.length,
    }
  }, IDENT.source)
  console.log(r.padEnd(9), 'identifiers: live', String(res.liveCount).padStart(3), '| DEAD', String(res.deadCount).padStart(3),
    '| controls', String(res.controls).padStart(3), 'disabled', res.disabled)
  for (const d of res.deadExamples) console.log('        dead:', d.id, '  in:', d.ctx)
}
await b.close()
