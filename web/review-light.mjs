import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
const routes = ['/', '/kanban', '/gantt', '/items', '/chat', '/reports', '/barrier', '/plan', '/help']
for (const r of routes) {
  await p.goto('http://127.0.0.1:8777/#' + r, { waitUntil: 'networkidle' })
  await p.waitForTimeout(700)
  const info = await p.evaluate(() => {
    const html = document.documentElement
    const body = document.body
    const main = document.querySelector('.el-main')
    const dark = [...document.querySelectorAll('*')].filter(e => {
      const bg = getComputedStyle(e).backgroundColor
      const m = bg.match(/rgba?\((\d+), (\d+), (\d+)/)
      if (!m) return false
      const [r2, g, b2] = [+m[1], +m[2], +m[3]]
      const a = bg.includes('rgba') ? parseFloat(bg.split(',')[3]) : 1
      if (a < 0.5) return false
      return (r2 + g + b2) / 3 < 90 && e.clientHeight > 40 && e.clientWidth > 200
    }).map(e => e.className?.toString?.().slice(0, 40))
    return {
      htmlClass: html.className,
      bodyBg: getComputedStyle(body).backgroundColor,
      mainBg: main ? getComputedStyle(main).backgroundColor : null,
      text: getComputedStyle(body).color,
      darkSurfaces: [...new Set(dark)].slice(0, 6),
    }
  })
  console.log(r.padEnd(9), info.htmlClass || '(none)', '| body', info.bodyBg, '| main', info.mainBg, '| dark surfaces:', JSON.stringify(info.darkSurfaces))
}
await p.goto('http://127.0.0.1:8777/#/kanban', { waitUntil: 'networkidle' }); await p.waitForTimeout(900)
await p.screenshot({ path: '/tmp/light-kanban.png' })
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' }); await p.waitForTimeout(900)
await p.screenshot({ path: '/tmp/light-chat.png' })
await b.close()
