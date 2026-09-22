/**
 * T-0160 -- "Make every dashboard route usable at 390px without page-level
 * horizontal overflow".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T02:54:40.989Z),
 * verbatim acceptance for the two clauses this file encodes:
 *
 *   "At a real 390x844 viewport every route has documentElement.scrollWidth <=
 *    clientWidth with no page-level horizontal scroll; the sidebar becomes a
 *    drawer or compact rail; ... Playwright checks all routes at 390px for
 *    overflow and accessible names."
 *
 * The card is wider than that -- it also asks for a deliberate mobile table
 * presentation, usable Kanban/Gantt/Chat/Barrier panes, and a sensible focus
 * order. Those are named here as *not measured*: this file asserts the two
 * clauses a single viewport probe can decide (overflow, and the sidebar being a
 * drawer rather than a squeezing column), and says so rather than implying the
 * rest passed. The scope the leader handed this file is those two halves.
 *
 * Revision measured for this file, from `GET http://127.0.0.1:8777/api/revision`
 * on 2026-09-22:
 *
 *   fabric 59c319b+dirty
 *   bundle 59c319b+dirty, built 2026-09-22T08:20:23.487Z, source "vite build"
 *   stale: true
 *
 * `stale` is true: `web/src` has been edited since the served bundle was built,
 * so this file measures the bundle a reader actually loads on 8777. A media
 * query that exists in `web/src` and not in the bundle is, from the reader's
 * chair, missing.
 *
 * Measurement on that revision, all nine routes, 390x844:
 *
 *   documentElement.scrollWidth 623 > clientWidth 390  (all routes)
 *   .aim-aside is a visible 216px column at x=0, on screen, in flow
 *   .el-main is squeezed to 174px (x=216)
 *   no control in the shell has an accessible name matching /menu|nav|sidebar/
 *
 * Both clauses failed on every route then, and each test carried a `test.fail()`
 * with that reason. Annotating rather than weakening was the point: when the fix
 * landed, every annotated test reported an *unexpected pass*, and the annotations
 * were deleted deliberately.
 *
 * Fixed 2026-09-22, re-measured on the rebuilt bundle, all nine routes, 390x844:
 *
 *   documentElement.scrollWidth 390 == clientWidth 390  (all routes)
 *   .el-main is 390px of 390 (share 1.00); the aside is not in flow
 *   the header wraps; a shell control is named "open/close the navigation menu"
 *
 * The assertions below are unchanged from the red revision; only the annotations
 * that said "this is broken today" are gone.
 *
 * Every number is read off the live board at the real viewport, because the
 * card's acceptance is about the live shell and its real content. The nav is
 * rendered by `App.vue` before `/api/state` resolves, so the shell chrome (the
 * sidebar, the overflow it causes) is measurable without depending on live data;
 * the panes below it are the live board the card names.
 */
import { expect, test } from '@playwright/test'

// "a real 390x844 viewport" -- an iPhone 12/13/14 logical size, set on the
// context, so `documentElement.clientWidth` is 390 and not a scaled number.
test.use({ viewport: { width: 390, height: 844 } })

/** The routes the card names, in its order. `#/` lands on the overview pane. */
const ROUTES = [
  { hash: '#/', name: 'landing' },
  { hash: '#/items', name: 'items' },
  { hash: '#/kanban', name: 'kanban' },
  { hash: '#/gantt', name: 'gantt' },
  { hash: '#/chat', name: 'chat' },
  { hash: '#/reports', name: 'reports' },
  { hash: '#/plan', name: 'plan' },
  { hash: '#/barrier', name: 'barrier' },
  { hash: '#/help', name: 'help' },
]

/**
 * The drawer handle's accessible name, if the shell has one.
 *
 * A drawer is opened by *something*, and that something has to have a name a
 * screen reader can read (the card's own accessible-name clause). Testing for
 * the handle is what separates "the sidebar is off-canvas and unreachable" from
 * "the sidebar is a drawer": an aside that hides itself with no way back is not
 * a drawer, it is a missing nav.
 */
const DRAWER_WORDS = /menu|nav|sidebar|hamburger|☰/i

/** The measurement, taken from the live page at 390x844. */
async function measure(page) {
  return page.evaluate(() => {
    const de = document.documentElement
    const aside = document.querySelector('.aim-aside')
    const main = document.querySelector('.el-main') || document.querySelector('.aim-main')
    const rect = (el) => {
      if (!el) return null
      const b = el.getBoundingClientRect()
      const s = getComputedStyle(el)
      return {
        x: Math.round(b.x), width: Math.round(b.width), height: Math.round(b.height),
        right: Math.round(b.right), display: s.display, visibility: s.visibility,
        inViewport: b.right > 0 && b.x < window.innerWidth && s.display !== 'none' && s.visibility !== 'hidden',
      }
    }
    const name = (el) => (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || '').trim()
    const controls = [...document.querySelectorAll('button, [role="button"], a, .el-button')]
    const drawerControls = controls.map(name).filter((t) => /menu|nav|sidebar|hamburger|☰/i.test(t))
    return {
      hash: location.hash,
      clientWidth: de.clientWidth,
      scrollWidth: de.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      scrollX: window.scrollX,
      aside: rect(aside),
      main: rect(main),
      drawerControls: [...new Set(drawerControls)],
    }
  })
}

/** `scrollWidth <= clientWidth`, stated with both numbers in the failure. */
function overflowMessage(m, route) {
  return `${route.hash} at 390x844: documentElement.scrollWidth ${m.scrollWidth} > clientWidth `
    + `${m.clientWidth} (body ${m.bodyScrollWidth}, window.scrollX ${m.scrollX}); `
    + `aside ${JSON.stringify(m.aside)}, main ${JSON.stringify(m.main)}`
}

for (const route of ROUTES) {
  test(`T-0160 ${route.name} (${route.hash}) at 390x844: no page-level horizontal overflow`, async ({ page }) => {
    await page.goto(`/${route.hash}`)
    // Wait on the shell, never on `.aim-aside` being *visible*: a fix that makes
    // the aside a hidden drawer would time out on that wait and be swallowed by
    // an expected failure instead of reported as the defect it is.
    await page.waitForSelector('.aim-shell', { state: 'visible' })
    await page.waitForTimeout(300)
    const m = await measure(page)

    // The card's first clause, both numbers exactly.
    expect(m.scrollWidth, overflowMessage(m, route)).toBeLessThanOrEqual(m.clientWidth)

    // "no page-level horizontal scroll": scrolling the window right must be a
    // no-op. Asserting only `scrollWidth` would miss a document that scrolls a
    // hidden overflow without widening the element's scrollWidth.
    await page.evaluate(() => window.scrollTo(9999, 0))
    const after = await page.evaluate(() => window.scrollX)
    expect(after, `${route.hash}: the window scrolled to scrollX ${after}; page-level horizontal scroll is forbidden`).toBe(0)
  })

  test(`T-0160 ${route.name} (${route.hash}) at 390x844: the sidebar is a drawer, not a squeezing column`, async ({ page }) => {
    await page.goto(`/${route.hash}`)
    await page.waitForSelector('.aim-shell', { state: 'visible' })
    await page.waitForTimeout(300)
    const m = await measure(page)

    // A drawer needs a handle with an accessible name; that name is the card's
    // own accessible-name clause, checked here rather than assumed.
    expect(
      m.drawerControls.length,
      `${route.hash} at 390x844: no shell control names a drawer/nav toggle `
      + `(searched aria-label/title/text for /menu|nav|sidebar/). aside ${JSON.stringify(m.aside)}`,
    ).toBeGreaterThan(0)

    // "rather than squeezing the content": a drawer overlays, so the reading
    // pane keeps (nearly) the full viewport width. A permanent 216px column
    // leaves the pane at 174/390 = 45%, which is the measured defect.
    const share = m.main ? m.main.width / m.clientWidth : 0
    expect(
      share,
      `${route.hash} at 390x844: .el-main is ${m.main && m.main.width}px of ${m.clientWidth} `
      + `(${Math.round(share * 100)}%); a drawer leaves the pane the full width instead of the `
      + `216px column measured (aside ${JSON.stringify(m.aside)})`,
    ).toBeGreaterThanOrEqual(0.85)
  })
}
