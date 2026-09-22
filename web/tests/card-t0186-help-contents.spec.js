/**
 * T-0186 -- "Help is a 4564px wall with no table of contents, and never says what
 * any pane is for".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T07:12:32.018Z,
 * actor codex, owner claude-session1, tags frontend/help), verbatim acceptance:
 *
 *   1. "Help opens with a map of the panes: every route in the shell, its purpose
 *      sentence, and a link to it. The sentences come from `views/*.js`, not from
 *      a second copy."
 *   2. "A reader can reach any section of Help in one click from the top, and the
 *      current section is indicated. Scroll-spy comes from Element Plus, not from
 *      a hand-rolled listener."
 *   3. "No raw protocol enum renders in Help's own prose without its English label
 *      beside it."
 *
 * Revision measured for this file -- `GET http://127.0.0.1:8777/api/revision` on
 * 2026-09-22:
 *
 *   fabric fac2a0c+dirty
 *   bundle 870b282+dirty, built 2026-09-22T08:40:07.787Z, source "vite build"
 *   stale: true
 *
 * `stale` is true: `web/src` has been edited since the served bundle was built, so
 * every assertion below is a verdict about the bundle a reader actually loads on
 * 8777 -- a table of contents that exists in `web/src` and not in the bundle is,
 * from the reader's chair, still missing.
 *
 * Measurement on that revision, viewport 1440x1000:
 *
 *   `.el-anchor` elements in the pane ......... 0
 *   links inside `.aim-help` .................. 30, all to `#/help#...` or the six
 *                                               concept links (no `#/gantt`, no
 *                                               `#/chat`, no `#/help` link)
 *   the nine arrival sentences from `views/*.js` on the page ... 0
 *   bare protocol enums without the English label in the same row ... 5
 *     (the "usually next" cell of each phase row: COMMIT, SYNTHESIS,
 *      CROSS_EXAMINE, RESOLVE, CLOSED -- the same enum the row above it links as
 *      "Committed", "Synthesising", ...)
 *
 * Clauses 2 and 3 fail on that revision. Since then clauses 1 and 3 have landed,
 * so only clause 2 still carries `test.fail()` with its measured reason. That is
 * not a weakened assertion: when a section list appears the test that measures it
 * starts passing, which Playwright reports as an *unexpected pass* -- the
 * annotation has to be removed deliberately.
 *
 * Two of the three assertions are written to compare the page against itself:
 *   * clause 1 compares the sentence in Help with the hint the shell shows on
 *     arrival at that route (`App.vue` renders `current.hint`), so a Help page that
 *     copied the sentences once and drifted is caught rather than blessed;
 *   * clause 3 takes the English label for each enum from the phases table's own
 *     `el-tag` cell, so it is the page's mapping that is enforced, not this file's.
 */
import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 1440, height: 1000 } })

/** The nine phases, as `bin/aim` spells them. */
const PHASE_ENUMS = ['SEALED_DIVERGENT', 'COMMIT', 'SYNTHESIS', 'CROSS_EXAMINE', 'RESOLVE', 'CLOSED']

/**
 * Every route the shell's own nav offers, and the purpose sentence the shell
 * shows when the reader arrives there.
 *
 * The routes are read by clicking the nav rather than written down here, so
 * "every route in the shell" means what the shell has today, not what it had when
 * this file was committed. The sentence is `.aim-page .aim-sub` -- the hint
 * `App.vue` renders from the view's own `hint`, which is the string clause 1 says
 * the map has to reuse.
 */
async function shellRoutes(page) {
  await page.goto('/#/attention')
  await page.waitForSelector('.aim-aside .el-menu-item', { state: 'visible' })
  const count = await page.locator('.aim-aside .el-menu-item').count()
  const routes = []
  for (let index = 0; index < count; index += 1) {
    const item = page.locator('.aim-aside .el-menu-item').nth(index)
    const label = (await item.innerText()).trim()
    await item.click()
    // The nav marks the item the current route belongs to, so waiting for its
    // `is-active` is how this knows the click landed -- including the click on
    // the route the reader is already on, where the hash does not change at all.
    try {
      await page.waitForFunction((i) => {
        const clicked = document.querySelectorAll('.aim-aside .el-menu-item')[i]
        return !!clicked && clicked.classList.contains('is-active')
      }, index, { timeout: 5000 })
    } catch {
      throw new Error(
        `clicking nav item ${index} ("${label}") left the menu without an active item for it `
        + `(hash is ${await page.evaluate(() => location.hash)}), so the list of shell routes cannot be read`,
      )
    }
    await page.waitForTimeout(80)
    routes.push(await page.evaluate(() => ({
      hash: location.hash,
      hint: (document.querySelector('.aim-page .aim-sub')?.textContent || '').trim(),
    })))
  }
  return routes
}

async function openHelp(page) {
  await page.goto('/#/help')
  await page.waitForSelector('.aim-help', { state: 'visible' })
  await page.waitForTimeout(300)
}

/**
 * Clause 1. Every route, a link to it, and the shell's own sentence for it on the
 * same line as that link.
 */
test('T-0186: Help opens with a map of every pane, in the shell\'s own words', async ({ page }) => {
  // Clause 1's defect was measured 2026-09-22 on bundle 870b282+dirty: Help linked
  // 7 of the 9 shell routes (no #/gantt, no #/chat) and none of the 9 arrival
  // sentences appeared anywhere in its 4308px. `HelpPane.vue` grew its PANE_GROUPS
  // directory afterwards, and on the bundle built 2026-09-22T10:44Z this test runs
  // "Expected to fail, but passed" -- so the marker is gone and the assertions are
  // untouched. Clauses 2 and 3 below still fail for real and keep their markers.
  const routes = await shellRoutes(page)
  expect(routes.length, 'the shell rendered no nav items, so "every route in the shell" is not measurable').toBeGreaterThan(0)
  // A route with no arrival sentence would make the comparison below pass by
  // comparing against the empty string, which is how a test can be green and
  // measure nothing. The sentence is the thing clause 1 is about, so its absence
  // is a failure here.
  expect(
    routes.filter((route) => !route.hint).map((route) => route.hash),
    'the shell rendered no purpose sentence for these routes, so there is nothing for the map to reuse',
  ).toEqual([])

  await openHelp(page)
  const map = await page.evaluate((shellRoutesList) => {
    const pane = document.querySelector('.aim-help')
    const links = [...pane.querySelectorAll('a')].map((a) => ({
      href: a.getAttribute('href') || '',
      text: a.textContent.trim(),
      line: (a.closest('li, p, div')?.textContent || a.textContent).replace(/\s+/g, ' ').trim(),
    }))
    return shellRoutesList.map((route) => {
      // `#/barrier?channel=barrier-v0` is the barrier route with its channel in
      // the query: the link a map draws is to the path, so only the path counts.
      const key = route.hash.replace(/^#\/?/, '').split(/[?#]/)[0] || 'attention'
      const forRoute = links.filter((l) => l.href.split('#').slice(0, 2).join('#') === `#/${key}`)
      return {
        hash: route.hash,
        hint: route.hint,
        links: forRoute.map((l) => l.text),
        // The sentence and the link on one line: a link in a footer and the
        // sentence in a paragraph 400px away is not a map of the panes.
        linesWithHint: links.filter((l) => l.line.includes(route.hint) && l.href.includes(`#/${key}`)).length,
      }
    })
  }, routes)

  const noLink = map.filter((route) => !route.links.length)
  expect(
    noLink.length,
    `Help has no link to ${noLink.map((r) => r.hash).join(', ')} (of ${map.length} routes the shell offers); `
    + `measured ${map.map((r) => `${r.hash}:${r.links.length}`).join(' ')}`,
  ).toBe(0)

  const noSentence = map.filter((route) => !route.linesWithHint)
  expect(
    noSentence.length,
    `${noSentence.length} of ${map.length} routes have no line pairing the link with the shell's own sentence: `
    + noSentence.map((r) => `${r.hash} - missing "${r.hint}" near its link (link says "${(r.links[0] || '').slice(0, 60)}")`).join('; '),
  ).toBe(0)
})

/**
 * Clause 2. One click to any section, the current section indicated, and the
 * mechanism is Element Plus's `el-anchor` rather than a hand-rolled listener.
 *
 * The `.el-anchor` element is the assertion that the scroll-spy is the library's:
 * a hand-rolled table of contents would have to fake the class as well as the
 * behaviour, which is a different lie than the one this clause forbids.
 */
test('T-0186: one click reaches any section, and Element Plus says which one', async ({ page }) => {
  // Clause 2's defect was measured 2026-09-22 on bundle 870b282+dirty: the pane
  // rendered 0 `.el-anchor` containers and 0 `.el-anchor__link` items, so nothing
  // at the top of the 4308px page was clickable to a section. `HelpPane.vue` now
  // renders `<el-anchor :container="scroller">` with one `el-anchor-link` per
  // section, and on bundle 59b99a9+dirty (re-measured 11:42Z, three runs) this
  // test's body passes -- reported by the JSON reporter as "Expected to fail, but
  // passed", which is what licenses removing the marker. The assertions below are
  // untouched.
  await openHelp(page)

  const toc = await page.evaluate(() => {
    const anchor = document.querySelector('.aim-help .el-anchor, .el-anchor')
    const links = [...document.querySelectorAll('.el-anchor__link')]
    return {
      present: !!anchor,
      count: links.length,
      items: links.map((a) => ({ href: a.getAttribute('href') || '', text: a.textContent.trim() })),
    }
  })
  expect(
    toc.present,
    `no Element Plus anchor in Help: found ${toc.count} .el-anchor__link and no .el-anchor container, `
    + 'so there is nothing at the top of a 4308px page that says what is on it',
  ).toBe(true)
  expect(toc.count, 'the anchor exists but links nowhere').toBeGreaterThanOrEqual(5)

  const lastItem = toc.items[toc.items.length - 1]
  const lastId = lastItem.href.replace(/^#/, '')
  await page.click(`.el-anchor__link[href="${lastItem.href}"]`)
  await page.waitForTimeout(900)

  const reached = await page.evaluate((id) => {
    const scroller = document.querySelector('.aim-main')
    const target = document.getElementById(id)
    if (!target) return null
    return {
      top: Math.round(target.getBoundingClientRect().top - scroller.getBoundingClientRect().top),
      scrollTop: Math.round(scroller.scrollTop),
      active: [...document.querySelectorAll('.el-anchor__link.is-active, .el-anchor__link[class*="active"]')]
        .map((a) => a.getAttribute('href')),
    }
  }, lastId)
  expect(reached, `clicking "${lastItem.text}" left the section #${lastId} not on the page at all`).not.toBeNull()
  expect(
    Math.abs(reached.top),
    `one click on "${lastItem.text}" left #${lastId} ${reached.top}px from the top of the reading pane `
    + `(scrollTop ${reached.scrollTop}); "one click" means it lands there`,
  ).toBeLessThanOrEqual(80)
  expect(
    reached.active,
    `after clicking "${lastItem.text}" the indicated section is ${JSON.stringify(reached.active)}, not #${lastId}`,
  ).toContain(lastItem.href)
})

/**
 * Clause 3. A protocol enum may appear in Help's prose, but never without the
 * English word for that phase in the same row or block.
 *
 * The protocol-value column of the phases table is therefore fine (its row also
 * carries the `el-tag` that renders "Committed"), and a bare `COMMIT` in a
 * "usually next" cell is not (the English word in that row is the *current*
 * phase's, "Sealed", which is the wrong label for the enum beside it).
 */
test('T-0186: no protocol enum in Help without its English label beside it', async ({ page }) => {
  // Clause 3's defect was measured 2026-09-22 on bundle 870b282+dirty: 5 rows
  // rendered a bare COMMIT/SYNTHESIS/CROSS_EXAMINE/RESOLVE/CLOSED in the "usually
  // next" cell, with the English word for a different phase in the block and no
  // link. HelpPane's TRANSITIONS rows now carry the label beside the enum, and on
  // the bundle built 2026-09-22T10:51Z this test runs "Expected to fail, but
  // passed" -- so the marker is gone and the assertion below is untouched.
  await openHelp(page)

  const report = await page.evaluate((enums) => {
    const pane = document.querySelector('.aim-help')
    // The English word for each enum, read off the page's own phases table: the
    // `el-tag` in the row anchored `#phase-<enum lowercase>` renders the label.
    const english = {}
    for (const key of enums) {
      const row = pane.querySelector(`#phase-${key.toLowerCase()}`)
      english[key] = row?.querySelector('.el-tag__content')?.textContent.trim() || null
    }
    const missing = enums.filter((key) => !english[key])
    const bare = []
    const walker = document.createTreeWalker(pane, NodeFilter.SHOW_TEXT)
    let node
    while ((node = walker.nextNode())) {
      const found = node.textContent.match(new RegExp(`\\b(${enums.join('|')})\\b`))
      if (!found) continue
      const key = found[1]
      const block = node.parentElement.closest('tr, article, p, li, div')
      const text = (block?.innerText || '').replace(/\s+/g, ' ').trim()
      if (english[key] && !text.includes(english[key])) {
        bare.push({
          enum: key,
          english: english[key],
          where: `${node.parentElement.tagName.toLowerCase()}.${String(node.parentElement.className).split(' ')[0] || '-'}`,
          block: text.slice(0, 140),
        })
      }
    }
    return { english, missing, bare }
  }, PHASE_ENUMS)

  expect(
    report.missing,
    `the page has no English label to compare against for ${report.missing.join(', ')}: `
    + 'the phases table is where the mapping between the enum and the word is rendered, so it is what this test reads',
  ).toEqual([])

  expect(
    report.bare.length,
    `${report.bare.length} protocol enum(s) render without their English label in the same block: `
    + report.bare.map((b) => `${b.enum} (should sit beside "${b.english}") in ${b.where} -- "${b.block}"`).join(' | '),
  ).toBe(0)
})
