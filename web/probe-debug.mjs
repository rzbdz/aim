/**
 * What does the browser report as the pointer's offsetY inside the canvas, and
 * does the y-axis label the pointer is next to agree with the row that opens?
 * No pane changes needed: the listener is on the canvas the board already serves.
 */
import { chromium } from 'playwright-core'

const browser = await chromium.launch({ channel: 'chromium-headless-shell' })
for (const vp of [{ w: 1440, h: 1000 }, { w: 1024, h: 800 }]) {
  const context = await browser.newContext({ viewport: { width: vp.w, height: vp.h } })
  const page = await context.newPage()
  await page.goto('http://127.0.0.1:8777/#/gantt', { waitUntil: 'networkidle' })
  for (let i = 0; i < 10; i++) {
    if (await page.locator('canvas').count()) break
    await page.waitForTimeout(1200)
    await page.reload({ waitUntil: 'networkidle' })
  }
  if (!(await page.locator('canvas').count())) { console.log('NO CANVAS', vp); await context.close(); continue }
  await page.waitForTimeout(1500)
  const g = await page.evaluate(() => {
    const cv = document.querySelector('canvas')
    const r = cv.getBoundingClientRect()
    const main = document.querySelector('.el-main')
    const mb = main.getBoundingClientRect()
    const card = cv.closest('.el-card')
    const head = card ? card.querySelector('.el-card__header') : null
    return {
      canvas: { w: cv.width, h: cv.height, top: r.top, left: r.left },
      mainTop: mb.top, scrollTop: main.scrollTop, scrollerH: main.clientHeight,
      canvasTopInDoc: (r.top - mb.top) + main.scrollTop,
      headH: head ? Math.round(head.getBoundingClientRect().height) : null,
      headStyle: head ? getComputedStyle(head).position : null,
    }
  })
  console.log(`\n== ${vp.w}x${vp.h}`, JSON.stringify(g))
  // Listen for the real pointer events on the canvas and report offsetY.
  await page.evaluate(() => {
    window.__ev = []
    const cv = document.querySelector('canvas')
    cv.addEventListener('mousemove', (e) => { window.__ev.push({ t: 'move', offsetY: e.offsetY, clientY: e.clientY, targetOffsetY: e.target === cv }) }, true)
    cv.addEventListener('click', (e) => { window.__ev.push({ t: 'click', offsetY: e.offsetY, clientY: e.clientY }) }, true)
  })
  const probe = async (rowIdx, canvasY, note) => {
    const at = await page.evaluate((y) => {
      const cv = document.querySelector('canvas')
      const r = cv.getBoundingClientRect()
      const main = document.querySelector('.el-main')
      const mb = main.getBoundingClientRect()
      const topInDoc = (r.top - mb.top) + main.scrollTop
      return { x: Math.round(r.left + r.width * 0.8), y: Math.round(mb.top + topInDoc + y - main.scrollTop) }
    }, canvasY)
    await page.evaluate(() => { window.__ev = [] })
    await page.mouse.move(at.x, at.y)
    await page.waitForTimeout(450)
    const tip = await page.evaluate(() => {
      const cands = [...document.querySelectorAll('div')].filter((d) => /^T-\d{4}/.test((d.textContent || '').trim()) && (d.textContent || '').length < 200)
      return cands.length ? (cands[cands.length - 1].textContent || '').trim().slice(0, 40) : null
    })
    await page.mouse.click(at.x, at.y)
    await page.waitForTimeout(700)
    const dr = await page.evaluate(() => {
      const d = document.querySelector('.el-drawer')
      const r = d ? d.getBoundingClientRect() : null
      const ev = window.__ev
      return {
        events: ev.slice(0, 3),
        drawerVisible: !!r && getComputedStyle(d).visibility !== 'hidden' && r.height > 0,
        drawerH: r ? Math.round(r.height) : null,
        drawerTitle: d ? (d.querySelector('h3')?.textContent || '').trim().slice(0, 40) : '',
      }
    })
    console.log(`  ${note} canvasY=${canvasY} viewport=${at.x},${at.y} tooltip=${JSON.stringify(tip)} ${JSON.stringify(dr)}`)
    await page.keyboard.press('Escape')
    await page.waitForTimeout(300)
  }
  // Row 0 band is at canvas y ~36..49 (measured before); row 20 at 36+20*21=456.
  await probe(0, 44, 'row0')
  await probe(5, 149, 'row5')
  await probe(20, 464, 'row20')
  await probe(40, 884, 'row40')
  await context.close()
}
await browser.close()
