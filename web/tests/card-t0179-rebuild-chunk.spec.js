/**
 * T-0179 -- "A rebuild under an open tab turns every nav click into a silent
 * no-op".
 *
 * Card text (channels/hello/tasks.jsonl, `created`
 * 2026-09-22T03:36:49.118Z, actor codex, owner claude-session1), verbatim
 * acceptance:
 *
 *   "With a lazy chunk deleted under an open tab, clicking that route either
 *    loads the new build or says so on screen; the URL and the rendered pane
 *    never disagree without a visible message"
 *
 * and, from the four numbered points under the comment:
 *
 *   1. "... It must not silently do nothing."
 *   2. "The URL and the rendered pane never disagree without a visible message."
 *   3. "Reload never discards text the reader typed, per the store's existing rule."
 *   4. "A test that deletes a chunk and asserts the on-screen outcome"
 *
 * Revision measured for this file. `GET http://127.0.0.1:8777/api/revision`
 * immediately before the run recorded below:
 *
 *   fabric 80620a8+dirty
 *   bundle f0c4d64+dirty, built 2026-09-22T08:33:19.792Z, source "vite build",
 *          source_sha256 b7985a7370ad528fdf4d218019252dd139f409c805ca234e1accbd49393971ef
 *   stale: true (front_end_sha256 8479acc0934e9f2645a973eaa93352fad8c1b4d936bdaddda2df431d3e9a701c)
 *
 * `stale` is true, so the bundle answering 8777 was not built from the `web/src`
 * checked out beside it: a peer is editing `web/src/main.js` and rebuilding
 * `web/dist` while this is measured, and `front_end_sha256` moved on every poll
 * of the session (the served asset name `index-CTWzdyli.js` did not). What that
 * means for the verdict is narrow. This file measures the bundle a reader
 * actually loads, and it names it: the served `index.html` asked for
 * `assets/index-CTWzdyli.js`, and that chunk holds exactly one occurrence of
 * the string `preloadError` -- Vite's own `new Event("vite:preloadError")`
 * dispatch -- and zero `addEventListener` listeners for it. `web/src/main.js`
 * holds zero of either. The handler the card asks for does not exist in the
 * bundle that answered, so the verdict below is a verdict about that bundle.
 *
 * How the fixture reproduces a rebuild without building anything, and which chunk
 * it deletes. A rebuild with `emptyOutDir: true` does not change what a tab already
 * holds: the tab keeps the pre-rebuild chunk map, asks for `GanttPane-<oldhash>.js`,
 * and that file is gone. So this file intercepts the first request for that
 * chunk's name-shaped URL -- the pattern `/assets/GanttPane-` followed by any hash
 * and `.js`, robust to renames -- and answers it the way a deleted file answers:
 * 404. The second such request is let through to the live board, which is what the
 * world after a reload looks like: the freshly fetched `index.html` names the new
 * chunk, and it loads. Nothing on disk is deleted and no build is run, so the peer
 * rebuilding `web/dist` cannot be disturbed.
 *
 * **The deleted chunk is a work pane and cannot be `ChatPane` any more.** Until
 * commit `b17063f` every pane chunk was reachable only through its own route's
 * dynamic import, so any of them could stand in for the deleted file. That commit
 * made `OverviewPane.vue:14` import `messageWaiting` from `ChatPane.vue` (the
 * receipts tile and the chat list share one predicate), which the build resolves
 * as a hard static edge: the served `assets/OverviewPane-BIVA3mBB.js` opens with
 * `import{messageWaiting as E}from"./ChatPane-USrcqsvr.js"`. So ChatPane's chunk is
 * now a static dependency of the *attention* route, and the attention route is
 * where three of these tests begin. Measured with the old fixture (ChatPane
 * deleted, `goto('/#/attention')`): one request for `ChatPane-USrcqsvr.js`, that
 * request is this fixture's first and is answered 404, `router.onError` sets
 * `stale` and `App.vue`'s alert takes the page -- `.aim-page h2` reads `""` before
 * any click, so the click the tests are about never happens. `GanttPane` carries
 * no such inbound edge (`grep -l 'GanttPane-' web/dist/assets/*.js` names only
 * `index-DK3vwFXp.js`, and only inside its `__vite__mapDeps` table, which no other
 * chunk preloads), so deleting it leaves a live pane to click from: measured
 * `goto('/#/attention')` -> heading `Attention`, and the click's own request is the
 * first and only request for the chunk, so the 404 lands on the navigation.
 *
 * What the served bundle does with a deleted chunk, measured 2026-09-22 against
 * `index-DK3vwFXp.js` (built 13:55Z) over `GanttPane-sjMSg06w.js` answered 404:
 *
 *   click on Gantt          -> URL stays `#/attention`, the pane heading stays
 *                              "Attention" (the router refuses the navigation), and
 *                              the shell mounts a visible `el-alert`: "this page was
 *                              built before the board was rebuilt, so the pane you
 *                              asked for is no longer on the server" with a `reload`
 *                              button. Console: 404 for `GanttPane-sjMSg06w.js`.
 *   `location.hash = '#/chat'` -> URL `#/chat`, heading "Conversations", no message:
 *                              the pane and the URL agree, so there is nothing to say.
 *   typed draft + click Gantt  -> the page is not reloaded, `inputValue()` still reads
 *                              the draft, and the alert above is on screen.
 *
 * The handler `web/src/App.vue:130-157` is what the card asked for, and it is in the
 * bundle that answered. So the four `test.fail(true, ...)` annotations this file
 * used to carry -- which recorded the silent no-op, and whose own comment said the
 * "expected to fail but passed" report is the tripwire that says the marker must be
 * lifted -- have fired, and they are removed here: one of them (the fixture control)
 * because it was measuring a fixture that had stopped being the thing the card
 * names, and the other three because the clause each encodes is now satisfied. A
 * `test.fail` left on a passing test is itself graded `unexpected`, so leaving them
 * would be the same red by another route.
 *
 * The visible-message predicate is a consequence, not a mechanism: any leaf text
 * newly visible in the reading pane (or an `el-message`/`el-notification`
 * mounted at body level) that mentions reload/refresh/rebuild/failure counts,
 * and the pre-click text is subtracted so a string that was already on the page
 * cannot masquerade as the affordance. `.aim-deferred` is excluded on purpose:
 * it is the store's "newer activity was held back" banner, a different message
 * about a different event, and counting it would let a busy record fake this
 * acceptance. The live board is used for everything except the deleted chunk
 * itself, because the card's subject is what the board actually serves.
 *
 * The board on 8777 runs without `--allow-write`, and that is not this file's to
 * change: `/api/state` publishes `write: {enabled: false, as: ""}`, `board.canWrite`
 * is false, and `ChatPane.vue:884` draws the "nothing here to type into" card
 * instead of the composer. The clause about typed text needs a composer, so that
 * one test serves the live payload with that one field flipped (`serveWritable`
 * below). `board.canWrite` is `Boolean(doc.write.enabled)` -- a field of the
 * payload, not of the server's argv -- so the missing control is one the fixture
 * can install without touching the server.
 */
import { expect, test } from '@playwright/test'

const GANTT_CHUNK = '**/assets/GanttPane-*.js'
const DRAFT = 'half-written reply: do not reload under my hands'

/** The heading the shell draws for the pane a hash names, or "" while it has no route. */
const heading = (page) => page.locator('.aim-page h2').innerText().catch(() => '')

/**
 * Answer the first request for a pane's chunk the way a rebuild answers it: that
 * content-hashed file no longer exists. Later requests continue to the server,
 * so "the new build loads" is reachable and a reload cannot spin forever.
 *
 * `GANTT_CHUNK` only. The first request for a chunk is the one that decides, and
 * for a work pane reached by a nav click that request *is* the navigation: see the
 * header for why `ChatPane` no longer qualifies, and measure before pointing this
 * at another chunk.
 */
async function deletedChunk(page, pattern) {
  let deleted = 0
  await page.route(pattern, (request) => {
    if (deleted === 0) {
      deleted += 1
      return request.fulfill({ status: 404, contentType: 'text/plain', body: 'deleted by the T-0179 fixture' })
    }
    return request.continue()
  })
  return { pattern, deleted: () => deleted }
}

/**
 * The live board as it is, with one field flipped: `write.enabled`.
 *
 * The composer exists if and only if `board.canWrite`, which is
 * `Boolean((doc.write || {}).enabled)` (`stores/board.js:301-302`) -- so a payload
 * is what stands between this test and the draft it has to type. The read-only
 * board stays read-only: the payload is fetched from it and served back with that
 * one field set, and `/api/digest` is served the same board's digest so the store
 * does not read a poll as the record moving. Nothing is posted, and no write path
 * is exercised -- the test never presses send.
 */
async function serveWritable(page) {
  const state = await (await page.request.get('/api/state')).json()
  const served = { ...state, write: { enabled: true, as: state.viewer || 'human' } }
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(served),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: state.digest }),
  }))
  return served
}

/**
 * Text a reader could see that says the navigation did not happen silently.
 *
 * `baseline` is the same scan taken before the click, so only *new* text counts.
 * The words are deliberately broad (`failed`, `could not`) because the card asks
 * for a message, not for one spelling of it.
 */
async function newVisibleMessages(page, baseline) {
  const hits = await page.evaluate(() => {
    const saysSo = /(reload|refresh|new version|new build|rebuilt|rebuild|failed|could not)/i
    const out = []
    for (const el of document.querySelectorAll('.aim-main *, .el-message, .el-notification')) {
      if (el.closest('.aim-deferred') || el.children.length) continue
      const text = (el.textContent || '').trim()
      if (!text || !saysSo.test(text)) continue
      const box = el.getBoundingClientRect()
      if (box.width === 0 || box.height === 0) continue
      out.push(text)
    }
    return [...new Set(out)]
  })
  return hits.filter((text) => !baseline.includes(text))
}

/**
 * What the reader can see after a navigation whose chunk was deleted.
 *
 * `paneLoaded` is the heading the route's own meta carries: the shell draws it
 * from the committed route, and `vue-router` commits only after the lazy
 * component resolves, so a heading naming the target pane is the pane being
 * there. It is deliberately not "some pane is mounted" -- in the typed-text test
 * the pane the reader is leaving stays mounted when the navigation fails, and
 * that must not be read as a successful load.
 */
async function outcome(page, baseline, title) {
  const shown = await heading(page)
  return {
    url: new URL(page.url()).hash,
    heading: shown,
    paneLoaded: shown === title,
    messages: await newVisibleMessages(page, baseline),
  }
}

/** Watch for one of the two permitted outcomes, for a bounded time only. */
async function observeOutcome(page, baseline, title, ms = 4000) {
  const deadline = Date.now() + ms
  let seen = await outcome(page, baseline, title)
  while (!seen.paneLoaded && !seen.messages.length && Date.now() < deadline) {
    await page.waitForTimeout(200)
    seen = await outcome(page, baseline, title)
  }
  return seen
}

test.describe('T-0179: a deleted lazy chunk must not be a silent no-op', () => {
  test('the fixture is the thing the card names: the tab asks for a chunk that is gone', async ({ page }) => {
    // A control, and it stays green: it asserts the premise the three acceptance
    // tests below rest on. Until this run it ran red *on purpose*, deleting the
    // chat chunk and failing at its first assertion because the shell's stale
    // handler had already taken the page at load -- and that red was the fixture,
    // not the board: `OverviewPane.vue:14` imports ChatPane, so the first request
    // for `ChatPane-*.js` is the attention route's own static dependency, and this
    // fixture answered it 404 (see the header). Deleting a work pane's chunk
    // instead leaves a live pane to click from, which is exactly the premise:
    // `#/attention` draws, the click asks for the deleted file, and the route is
    // not broken -- unblock the chunk and the same click loads the same pane. A
    // control that is red because its own fixture is wrong asserts nothing.
    const gone = await deletedChunk(page, GANTT_CHUNK)
    await page.goto('/#/attention')
    await expect(page.locator('.aim-page h2')).toHaveText('Attention')

    await page.locator('.el-menu-item').filter({ hasText: 'Gantt' }).click()
    // The pane the tab was holding asked for the content-hashed file the rebuild
    // removed, and this test answered it 404. The cause is the deleted chunk, not
    // a broken route, a bad fixture, or a server that was down.
    await expect.poll(gone.deleted).toBeGreaterThanOrEqual(1)

    // And the route is not broken: unblock the chunk and the same click, on the
    // same board, loads the same pane. If this ever fails, the verdict in the
    // tests below says something about a broken route rather than a deleted chunk.
    await page.unroute(gone.pattern)
    await page.reload()
    await page.locator('.el-menu-item').filter({ hasText: 'Gantt' }).click()
    // The heading is the consequence, not the mechanism: the shell draws it from
    // the committed route, and `vue-router` commits only after the lazy chunk has
    // resolved. Nothing here asserts the Gantt pane's own markup, which belongs to
    // other cards and is being rewritten while this is measured.
    await expect(page.locator('.aim-page h2')).toHaveText('Gantt')
  })

  test('a nav click whose chunk is gone either loads the pane or says so on screen', async ({ page }) => {
    // Was `test.fail(true)`: "measured on bundle f0c4d64+dirty: the click does
    // nothing and says nothing; the pane stays 'Attention'". That was measured, and
    // on bundle `index-DK3vwFXp.js` it is no longer true: the click's own request
    // for `GanttPane-sjMSg06w.js` is this fixture's first and is 404'd, the router
    // refuses the navigation, and `App.vue`'s stale alert is on screen in words.
    // The annotation is lifted rather than kept because a `test.fail` on a passing
    // test is itself reported `unexpected`; the assertion below is unchanged.
    await deletedChunk(page, GANTT_CHUNK)
    await page.goto('/#/attention')
    await expect(page.locator('.aim-page h2')).toHaveText('Attention')
    const baseline = await newVisibleMessages(page, [])

    await page.locator('.el-menu-item').filter({ hasText: 'Gantt' }).click()
    const seen = await observeOutcome(page, baseline, 'Gantt')
    expect(
      seen.paneLoaded || seen.messages.length,
      `after clicking Gantt the URL is ${seen.url}, the pane heading is ` +
        `"${seen.heading}", and the new visible messages are ${JSON.stringify(seen.messages)}`,
    ).toBeTruthy()
  })

  test('the URL and the rendered pane never disagree without a visible message', async ({ page }) => {
    // Was `test.fail(true)`: "measured on bundle f0c4d64+dirty: URL #/chat over a
    // pane still showing Attention, with no message". The card's own repro is kept
    // unchanged -- the hash is moved directly, so nothing in the router can undo it
    // -- and on the served bundle the clause holds: the navigation fails with the
    // alert on screen, and moving the hash back to `#/chat` (the fixture's second
    // request for the chunk, which is let through) commits the route, so URL and
    // pane agree. Both halves are permitted by the same assertion the card names.
    await deletedChunk(page, GANTT_CHUNK)
    await page.goto('/#/attention')
    await expect(page.locator('.aim-page h2')).toHaveText('Attention')
    const baseline = await newVisibleMessages(page, [])

    // The card's own repro: the hash is moved directly, so nothing in the router
    // can undo it and the disagreement the reader would see is maximal.
    await page.evaluate(() => { location.hash = '#/chat' })
    let seen = await observeOutcome(page, baseline, 'Conversations')
    let agree = (seen.url === '#/chat') === seen.paneLoaded
    // First the hash the click could not commit, then the one it can: a navigation
    // that lands clears the message (`App.vue`, `router.afterEach`), so a stale
    // alert left over the pane the reader actually asked for is the failure this
    // second half catches.
    if (!agree && !seen.messages.length) {
      await page.evaluate(() => { location.hash = '#/chat' })
      seen = await observeOutcome(page, baseline, 'Conversations')
      agree = (seen.url === '#/chat') === seen.paneLoaded
    }
    expect(
      agree || seen.messages.length,
      `the URL claims ${seen.url || '(none)'} while the pane heading is ` +
        `"${seen.heading}" (chat pane loaded: ${seen.paneLoaded}), and the new ` +
        `visible messages are ${JSON.stringify(seen.messages)}`,
    ).toBeTruthy()
  })

  test('a reload that would discard typed text is withheld, and that is said on screen', async ({ page }) => {
    // Was `test.fail(true)`: "the server runs without --allow-write, so ChatPane
    // draws the 'nothing here to type into' card and `.aim-composer textarea` does
    // not exist ... its 30s timeout is a missing control rather than a withheld
    // reload". The annotation was honest but the test was graded `unexpected`
    // anyway, because it failed by *timeout* and Playwright does not match `fail`
    // against a timeout. The missing control is one this fixture can install:
    // `board.canWrite` is `Boolean(doc.write.enabled)`, a field of the payload, so
    // the live board is served back with that one field set and the board itself
    // is left read-only. The clause itself is unchanged.
    const served = await serveWritable(page)
    expect(served.write.enabled, 'the fixture failed to install a writable payload').toBe(true)
    await page.goto('/#/chat')
    await expect(page.locator('.aim-page h2')).toHaveText('Conversations')
    const composer = page.locator('.aim-composer textarea')
    await composer.fill(DRAFT)
    await page.evaluate(() => { window.__t0179_alive = 'the page was not reloaded' })
    await deletedChunk(page, GANTT_CHUNK)
    const baseline = await newVisibleMessages(page, [])

    await page.locator('.el-menu-item').filter({ hasText: 'Gantt' }).click()
    const seen = await observeOutcome(page, baseline, 'Gantt')
    const alive = (await page.evaluate(() => window.__t0179_alive)) === 'the page was not reloaded'
    const textStillThere = alive && (await composer.inputValue()) === DRAFT

    // The narrow part of acceptance 3: whatever else the handler does, a reload
    // under a half-written reply is the failure the store's rule exists to stop.
    expect(textStillThere, 'the page was reloaded and the typed text was discarded').toBe(true)
    // The part that makes "withheld" a decision rather than a dead click: the
    // reader must be told, or the pane must load. On the served bundle the reader
    // is told -- `App.vue`'s stale alert names the route that did not load -- and
    // the draft the reader had typed is still in the box underneath it.
    expect(
      seen.paneLoaded || seen.messages.length,
      `the typed text survived, but after clicking Gantt the URL is ${seen.url}, ` +
        `the pane heading is "${seen.heading}", and the new visible messages are ` +
        `${JSON.stringify(seen.messages)}`,
    ).toBeTruthy()
  })
})
