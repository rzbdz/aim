import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
const lum = (c) => {
  const [r, g, bl] = c.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number).map(v => {
    v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * bl
}
const ratio = (a, bg) => { const [l1, l2] = [lum(a), lum(bg)].sort((x, y) => y - x); return ((l1 + 0.05) / (l2 + 0.05)).toFixed(2) }
for (const r of ['/kanban', '/chat', '/items', '/help']) {
  await p.goto('http://127.0.0.1:8777/#' + r, { waitUntil: 'networkidle' }); await p.waitForTimeout(700)
  const samples = await p.evaluate(() => {
    const back = (el) => {
      let e = el
      while (e) { const bg = getComputedStyle(e).backgroundColor
        const m = bg.match(/rgba?\(([\d.]+), ([\d.]+), ([\d.]+)(?:, ([\d.]+))?/)
        if (m && (m[4] === undefined || parseFloat(m[4]) > 0.9)) return bg
        e = e.parentElement }
      return 'rgb(255,255,255)'
    }
    const pick = ['.aim-dim', '.aim-thread .aim-dim', '.aim-card .aim-accept', '.el-table__cell', '.markdown-body p', 'h2', 'h3']
    return pick.flatMap(s => {
      const el = document.querySelector(s)
      if (!el) return []
      const cs = getComputedStyle(el)
      return [{ s, color: cs.color, bg: back(el), size: cs.fontSize }]
    })
  })
  console.log('== ' + r)
  for (const x of samples) console.log('  ', x.s.padEnd(24), ratio(x.color, x.bg).padStart(6), x.size, x.color)
}
await b.close()
