import { chromium } from 'playwright'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.on('pageerror', (e) => console.log('PAGEERROR', String(e).slice(0, 200)))
await page.goto('http://127.0.0.1:8777/#/chat')
await page.waitForSelector('.aim-msg', { timeout: 20000 })
await page.waitForTimeout(1500)
const read = () => page.evaluate(() => {
  const h = document.querySelector('.aim-history')
  const rows = [...document.querySelectorAll('.aim-thread')].map((r) => ({
    label: r.querySelector('span')?.textContent?.trim(),
    unread: r.querySelector('.aim-unread')?.textContent?.trim() || '',
  }))
  const anchor = document.querySelector('.aim-anchor-message')
  const idx = [...document.querySelectorAll('.aim-msg')].indexOf(anchor)
  return {
    thread: document.querySelector('.aim-reader-head strong')?.textContent,
    msgs: document.querySelectorAll('.aim-msg').length,
    anchorIdx: idx,
    gapToBottom: Math.round(h.scrollHeight - h.clientHeight - h.scrollTop),
    lastBottomVisible: (() => {
      const nodes = [...document.querySelectorAll('.aim-msg')]
      const last = nodes[nodes.length - 1]
      if (!last) return null
      const box = h.getBoundingClientRect()
      const at = last.getBoundingClientRect()
      return { belowFoldBy: Math.round(at.bottom - box.bottom), visible: at.bottom <= box.bottom + 1 }
    })(),
    scrollTop: Math.round(h.scrollTop),
    scrollHeight: Math.round(h.scrollHeight),
    clientHeight: h.clientHeight,
    rows,
  }
})
const out = await read()
console.log(JSON.stringify({ ...out, rows: undefined }, null, 1))
console.log('thread rows with unread:', out.rows.filter((r) => r.unread))
console.log('total rows:', out.rows.length)
// now open the leader's own thread
const dm = await page.locator('.aim-thread').filter({ hasText: '⇄' }).first()
await dm.click()
await page.waitForTimeout(1500)
const two = await read()
console.log('second thread:', JSON.stringify({ ...two, rows: undefined }, null, 1))
await browser.close()
