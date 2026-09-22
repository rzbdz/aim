/**
 * T-0182 follow-up: the counted row's control, in the browser.
 *
 * The count now opens a popover. Three things that a `<RouterLink>` used to give
 * free and a `<button>`+popover has to earn: it has to be reachable by keyboard,
 * it must not put its content off-screen (the popper is 420px wide and the row
 * sits in a card), and it must close.
 *
 * Run against the live board on 8777 (read-only; the click opens a popover, it
 * issues no command).
 */
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:8777'
const browser = await chromium.launch()

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 800 }]) {
  const page = await browser.newPage({ viewport })
  await page.goto(`${BASE}/#/attention`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.aim-attention')
  const row = page.locator('.el-card').filter({ hasText: 'Latest conversation' })
    .locator('.aim-attention-row').filter({ hasText: 'receipts arrived' }).first()
  const present = await row.count()
  console.log(`\nviewport ${viewport.width}x${viewport.height} -- collapsed rows: ${present}`)
  if (!present) continue

  // Keyboard reach, not a mouse click: the old control was an <a>.
  const button = row.getByRole('button')
  console.log('  button count in the row:', await button.count(),
    '| tag:', await button.evaluate((el) => el.tagName),
    '| text:', (await button.innerText()).slice(-24))
  await button.focus()
  const focused = await page.evaluate(() => ({
    active: document.activeElement.tagName,
    text: (document.activeElement.textContent || '').slice(-24),
    outline: getComputedStyle(document.activeElement).outlineStyle,
  }))
  console.log('  after focus():', JSON.stringify(focused))
  await page.keyboard.press('Enter')
  const popper = page.locator('.el-popper:visible')
  await popper.waitFor({ state: 'visible', timeout: 5000 })
  const box = await popper.boundingBox()
  const body = await page.locator('body').evaluate((el) => ({
    scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
  }))
  console.log('  popper box:', JSON.stringify(box))
  console.log('  popper inside the viewport:',
    box.x >= 0 && box.y >= 0 && box.x + box.width <= viewport.width + 1 && box.y + box.height <= viewport.height + 1)
  console.log('  page scrollWidth vs clientWidth:', body.scrollWidth, body.clientWidth,
    body.scrollWidth <= body.clientWidth ? '(no horizontal scroll)' : '(HORIZONTAL SCROLL)')
  console.log('  rows on the page:', await row.count(), '| lines listed:', (await popper.innerText()).split('\n').length)

  await page.keyboard.press('Escape')
  await page.waitForTimeout(300)
  console.log('  after Escape, visible poppers:', await page.locator('.el-popper:visible').count())
  // The row sits in a card; the other way out is a click anywhere else.
  await page.locator('.aim-attention-hero h3').click()
  await page.waitForTimeout(300)
  console.log('  after an outside click, visible poppers:', await page.locator('.el-popper:visible').count())
  await page.close()
}

await browser.close()
