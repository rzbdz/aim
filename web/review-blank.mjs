import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
p.on('pageerror', e => console.log('PAGEERROR:', e.message))
p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('CONSOLE', m.type(), ':', m.text().slice(0, 300)) })
for (const r of ['/', '/attention', '/overview']) {
  await p.goto('http://127.0.0.1:8777/#' + r, { waitUntil: 'networkidle' })
  await p.waitForTimeout(1000)
  const t = await p.evaluate(() => ({
    hash: location.hash,
    len: document.body.innerText.trim().length,
    head: document.body.innerText.trim().slice(0, 160).replace(/\n+/g, ' | '),
    mainHtmlLen: (document.querySelector('.el-main')?.innerHTML || '').length,
  }))
  console.log(r.padEnd(11), '-> hash', t.hash, '| text len', t.len, '| main html', t.mainHtmlLen, '|', t.head)
}
await b.close()
