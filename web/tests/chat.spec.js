import { expect, test } from '@playwright/test'

test('conversation history and pinned input never overlap or reload the page', async ({ page }) => {
  let navigations = 0
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) navigations += 1
  })

  await page.goto('/#/chat')
  const groups = await page.locator('.el-menu-item-group__title').allTextContents()
  expect(groups).toEqual([
    'Work · 工作',
    'Conversation · 会话',
    'Insight · 报表',
    'Governance · 治理',
  ])
  expect(await page.locator('.el-menu-item').count()).toBe(8)
  await expect(page.locator('.aim-reader')).toBeVisible()
  await expect(page.locator('.aim-msg').first()).toBeVisible()
  const navigationsAfterLoad = navigations

  const layout = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    const composer = document.querySelector('.aim-composer')
    const input = document.querySelector('#aim-composer')
    if (!history || !composer || !input) throw new Error('the conversation layout is incomplete')
    const historyBox = history.getBoundingClientRect()
    const composerBox = composer.getBoundingClientRect()
    return {
      historyOverflow: getComputedStyle(history).overflowY,
      historyCanScroll: history.scrollHeight > history.clientHeight,
      composerInsideHistory: history.contains(composer),
      historyEnd: historyBox.bottom,
      composerStart: composerBox.top,
      composerBottom: composerBox.bottom,
      viewportHeight: window.innerHeight,
      inputVisible: input.getBoundingClientRect().height > 0,
    }
  })

  expect(layout.historyOverflow).toBe('auto')
  expect(layout.historyCanScroll).toBe(true)
  expect(layout.composerInsideHistory).toBe(false)
  expect(layout.historyEnd).toBeLessThanOrEqual(layout.composerStart)
  expect(layout.inputVisible).toBe(true)
  expect(layout.composerBottom).toBeLessThanOrEqual(layout.viewportHeight + 1)

  const pinned = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    const composer = document.querySelector('.aim-composer')
    const before = composer.getBoundingClientRect().top
    history.scrollTop = history.scrollHeight
    return {
      before,
      after: composer.getBoundingClientRect().top,
      scrollTop: history.scrollTop,
      scrollHeight: history.scrollHeight,
    }
  })

  expect(pinned.scrollTop).toBeGreaterThan(0)
  expect(Math.abs(pinned.after - pinned.before)).toBeLessThanOrEqual(1)

  const marker = await page.evaluate(() => window.__aimConversationRegressionMarker = 'still-mounted')
  await page.waitForTimeout(16_000)
  await expect(page.locator('.aim-reader')).toBeVisible()
  await expect.poll(() => page.evaluate(() => window.__aimConversationRegressionMarker)).toBe(marker)
  expect(navigations).toBe(navigationsAfterLoad)
})
