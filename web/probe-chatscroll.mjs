import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
const errs = []
p.on('pageerror', e => errs.push(String(e.message).slice(0, 140)))
await p.goto('http://127.0.0.1:8777/#/chat', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
const read = async (label) => {
  const r = await p.evaluate(() => {
    const h = document.querySelector('.aim-history') || document.querySelector('[class*=history]')
    if (!h) return { none: true }
    const msgs = [...h.querySelectorAll('.aim-msg')]
    const anchor = h.querySelector('.aim-anchor-message')
    const last = msgs.at(-1)
    const hb = h.getBoundingClientRect()
    return {
      cls: h.className, scrollTop: Math.round(h.scrollTop), scrollHeight: h.scrollHeight, clientHeight: h.clientHeight,
      atBottom: Math.abs(h.scrollHeight - h.clientHeight - h.scrollTop) < 4,
      gapToBottom: Math.round(h.scrollHeight - h.clientHeight - h.scrollTop),
      msgs: msgs.length,
      anchorIdx: anchor ? msgs.indexOf(anchor) : -1,
      lastMsgTopInView: last ? Math.round(last.getBoundingClientRect().top - hb.top) : null,
      lastMsgVisible: last ? (last.getBoundingClientRect().bottom <= hb.bottom + 2) : null,
    }
  })
  console.log(label, JSON.stringify(r))
  return r
}
await read('NO-PARAM /chat (auto-picked thread):')
// which thread is open
console.log('open thread header:', await p.evaluate(() => document.querySelector('.aim-chat-head, .aim-chat-main h3, .aim-chat-main h2')?.innerText.trim().slice(0, 80)))
// now click #hello explicitly
await p.evaluate(() => {
  const el = [...document.querySelectorAll('.aim-thread *')].find(e => e.children.length === 0 && e.textContent.trim() === '#hello')
  el?.closest('.aim-thread')?.click()
})
await p.waitForTimeout(1400)
console.log('url now:', p.url())
await read('#hello after click:')
// look for a scroll-to-bottom affordance
console.log('bottom affordance:', JSON.stringify(await p.evaluate(() => {
  const b = [...document.querySelectorAll('.aim-chat-main button, .aim-history ~ * button')].map(e => e.innerText.trim() || e.getAttribute('aria-label') || e.className).filter(Boolean)
  return b.slice(0, 12)
})))
console.log('chip strings on thread rows:', JSON.stringify(await p.evaluate(() => [...new Set([...document.querySelectorAll('.aim-thread .el-tag, .aim-thread [class*=chip]')].map(e => e.innerText.trim()))])))
console.log('errs', JSON.stringify(errs))
await b.close()
