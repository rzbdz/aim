import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForSelector('.aim-attention')
const state = async (label) => {
  const nodes = await p.evaluate(() => [...document.querySelectorAll('.el-popper, [role=tooltip]')].map((el) => ({
    cls: el.className.slice(0, 60),
    display: getComputedStyle(el).display,
    visibility: getComputedStyle(el).visibility,
    w: el.getBoundingClientRect().width, h: el.getBoundingClientRect().height,
    text: (el.innerText || '').replace(/\s+/g, ' ').slice(0, 60),
    ariaHidden: el.getAttribute('aria-hidden'),
  })))
  console.log(label, JSON.stringify(nodes, null, 1))
}
const row = p.locator('.el-card').filter({ hasText: 'Latest conversation' }).locator('.aim-attention-row').filter({ hasText: 'receipts arrived' }).first()
const btn = row.getByRole('button')
await state('initial:')
await btn.click(); await p.waitForTimeout(500)
await state('after click 1:')
await btn.click(); await p.waitForTimeout(500)
await state('after click 2 (toggle):')
await btn.click(); await p.waitForTimeout(400)
await p.keyboard.press('Escape'); await p.waitForTimeout(400)
await state('after Escape:')
await p.locator('.aim-attention-hero h3').click(); await p.waitForTimeout(400)
await state('after outside click:')
await b.close()
