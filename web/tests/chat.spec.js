import { expect, test } from '@playwright/test'

test('conversation reads as a scrollable page without reloading itself', async ({ page }) => {
  let navigations = 0
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) navigations += 1
  })

  await page.goto('/#/chat')
  await expect(page.locator('.aim-reader')).toBeVisible()
  await expect(page.locator('.aim-msg').first()).toBeVisible()
  const navigationsAfterLoad = navigations

  const scroll = await page.evaluate(() => {
    const main = document.querySelector('.el-main')
    if (!main) throw new Error('the Element Plus main pane is missing')
    main.scrollTop = main.scrollHeight
    return {
      scrollTop: main.scrollTop,
      scrollHeight: main.scrollHeight,
      insideNestedScrollbar: Boolean(document.querySelector('.aim-msg')?.closest('.el-scrollbar')),
    }
  })

  expect(scroll.insideNestedScrollbar).toBe(false)
  expect(scroll.scrollTop).toBeGreaterThan(0)

  const marker = await page.evaluate(() => window.__aimConversationRegressionMarker = 'still-mounted')
  await page.waitForTimeout(16_000)
  await expect(page.locator('.aim-reader')).toBeVisible()
  await expect.poll(() => page.evaluate(() => window.__aimConversationRegressionMarker)).toBe(marker)
  expect(navigations).toBe(navigationsAfterLoad)
})
