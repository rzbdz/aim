import { expect, test } from '@playwright/test'

test('overview names the product concepts and summarizes conversation shapes', async ({ page }) => {
  await page.goto('/#/overview')
  await expect(page.locator('.aim-page h2')).toHaveText('概览')
  await expect(page.locator('.el-menu-item').filter({ hasText: '看板' })).toBeVisible()
  await expect(page.locator('.el-menu-item').filter({ hasText: '甘特图' })).toBeVisible()
  const shapes = await page.locator('.el-card:has-text("latest on the record") .el-tag').allTextContents()
  expect(shapes.length).toBeGreaterThan(0)
  expect(shapes.map((shape) => shape.trim())).toContain('direct')
})

test('conversation history and pinned input never overlap or reload the page', async ({ page }) => {
  let navigations = 0
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) navigations += 1
  })

  await page.goto('/#/chat')
  await expect(page.locator('.aim-page h2')).toHaveText('会话')
  const groups = await page.locator('.el-menu-item-group__title').allTextContents()
  expect(groups).toEqual([
    '工作',
    '会话',
    '洞察',
    '治理',
  ])
  expect(await page.locator('.el-menu-item').count()).toBe(8)
  await expect(page.locator('.aim-reader')).toBeVisible()
  await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    if (!history) throw new Error('the conversation history is missing')
    const message = document.createElement('article')
    message.className = 'aim-msg'
    message.dataset.testid = 'layout-fixture'
    message.textContent = 'layout fixture'
    const filler = document.createElement('div')
    filler.dataset.testid = 'layout-filler'
    filler.style.height = '2000px'
    history.append(message, filler)
  })
  await expect(page.locator('.aim-msg').first()).toBeVisible()
  const navigationsAfterLoad = navigations

  const layout = await page.evaluate(() => {
    const history = document.querySelector('.aim-history')
    const composer = document.querySelector('.aim-composer')
    const input = document.querySelector('.aim-composer textarea')
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
  await page.evaluate(() => {
    document.querySelectorAll('[data-testid="layout-fixture"], [data-testid="layout-filler"]')
      .forEach((node) => node.remove())
  })
})
