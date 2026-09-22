/**
 * T-0175 -- "The palette must be switchable from the UI, and the choice must
 * survive a reload".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T03:24:15.953Z,
 * actor codex, owner claude-session1, tags web/theme), verbatim acceptance:
 *
 *   "A control in the shell flips light and dark, the choice is remembered
 *    across reloads, and it is reflected in the URL or a stored preference
 *    rather than only in memory. The hook is already in place: every colour is a
 *    token in style.css with light values on :root and the original dark values
 *    verbatim under html.dark, and Element Plus scopes its own dark variables to
 *    that same class."
 *
 * Revision measured for this file -- `GET http://127.0.0.1:8777/api/revision`
 * on 2026-09-22:
 *
 *   fabric 7a327bf+dirty
 *   bundle e3824c5+dirty, built 2026-09-22T08:15:50.150Z, source "vite build"
 *   stale: true
 *
 * Re-checked after this file was committed: the board's *revision string* moved
 * (fabric 536433e+dirty, bundle 59c319b+dirty, built 08:20:23Z) while
 * `front_end_sha256` stayed `69f09a81927c4ee6d165fa313f6f0c9811b18ed4fc283becabe894524355442c`
 * -- the same bytes, so the verdict below is a verdict about the same front-end
 * that was measured first; only the label changed.
 *
 * `stale` is true: `web/src` has been edited since the served bundle was built,
 * so this file measures the bundle a reader actually loads on 8777, and the
 * verdict below is a verdict about that bundle. A control that exists in
 * `web/src` and not in the bundle is still, from the reader's chair, missing.
 *
 * What the shell actually renders is the measurement. Every assertion is taken
 * from the live page, not from the stylesheet text: the light palette is the
 * baseline of whatever board is on 8777 when this runs, so a board that had
 * switched its default to dark would fail here rather than be described as
 * "light" by a hard-coded expectation. The one number that is *not* read off
 * the page is the luminance threshold: light means the surfaces are light
 * (`--el-bg-color` #fff -> 1.00, Element Plus dark #141414 -> 0.07), and a
 * threshold in the middle is the smallest claim that separates the two palettes
 * without pinning an exact hex.
 *
 * The three clause tests were annotated with `test.fail()` and carried the
 * measured values in their messages. `test.fail()` was not a weakening of the
 * assertion: adding a control makes the flip test pass, which Playwright reports
 * as an *unexpected pass*, so the annotation had to be removed deliberately and
 * the flip could not happen silently. It was removed on 2026-09-22 with the fix,
 * and the assertions below are unchanged from the red revision.
 *
 * Fixed and re-measured 2026-09-22 on the rebuilt bundle, at 1280x720:
 *
 *   one theme candidate in the shell: `button.el-button("switch the board to the
 *   dark palette | dark palette")`, class `aim-theme-toggle`
 *   --el-bg-color #fff -> #141414, --aim-accent #0369a1 -> #38bdf8, then back
 *   localStorage aim-palette "light" -> "dark", and a reload with "dark" stored
 *   opens dark (the default with nothing stored stays light)
 */
import { expect, test } from '@playwright/test'

/** Text that names the palette, in a control's name, class or title. */
const THEME_WORDS = /theme|dark|light|palette|appearance|night|day|contrast|moon|sun/i

/**
 * The shell as a reader meets it: the nav and the header are rendered by
 * `App.vue` before `/api/state` resolves, which is what lets these tests run on
 * the live board without depending on live data.
 */
async function openShell(page) {
  await page.goto('/')
  await page.waitForSelector('.aim-header', { state: 'visible' })
  await page.waitForSelector('.aim-aside .el-menu-item', { state: 'visible' })
}

/**
 * The theme as the page actually resolves it. Reading `--el-bg-color` through
 * `getComputedStyle` matters: the tokens are declared on `:root` and overridden
 * by `html.dark`, and only the resolved value says which declaration won.
 */
async function readTheme(page) {
  return page.evaluate(() => {
    const root = getComputedStyle(document.documentElement)
    const token = (name) => root.getPropertyValue(name).trim()
    return {
      htmlClass: document.documentElement.className,
      darkClass: document.documentElement.classList.contains('dark'),
      accent: token('--aim-accent'),
      pageBg: token('--el-bg-color-page'),
      cardBg: token('--el-bg-color'),
      textColor: token('--el-text-color-primary'),
      href: location.href,
    }
  })
}

/** WCAG relative luminance of `#rrggbb`; null if the token is not a hex colour. */
function luminance(color) {
  const raw = String(color || '').trim().replace(/^#/, '')
  // Element Plus ships `--el-bg-color: #fff`, so short hex is the common case,
  // not an edge case; a token this function cannot read is a `null` the callers
  // assert against rather than a silently wrong number.
  const full = /^[0-9a-f]{3}$/i.test(raw)
    ? raw.split('').map((c) => c + c).join('')
    : raw
  const match = /^([0-9a-f]{6})$/i.exec(full)
  if (!match) return null
  const value = parseInt(match[1], 16)
  const [r, g, b] = [(value >> 16) & 255, (value >> 8) & 255, value & 255].map((v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function isDark(theme) {
  return theme.darkClass || (luminance(theme.cardBg) ?? 1) < 0.5
}

/**
 * Clickable things in the shell chrome that name the palette.
 *
 * The search is deliberately wider than "a button that says dark": an icon
 * button labelled only `aria-label="dark mode"` or carrying `.theme-toggle`
 * counts. It is deliberately *not* "click every control until the theme
 * changes": the shell's other buttons write to the record (`send to review`,
 * `confirm receipt`), and a test that discovers the theme toggle by pressing
 * those is a test that mutates the leader's board. A control that flips the
 * palette with no name, class, title or aria-label anywhere is therefore out of
 * reach of this file -- that is a limit of a read-only search, and it is stated
 * rather than papered over.
 *
 * Matches are tagged with a test-only attribute so the click can be aimed at the
 * exact node rather than at a text match that an icon-only control cannot give.
 */
const CLICKABLE = [
  'button', 'a', '[role="switch"]', '[role="button"]', '[role="radio"]',
  '.el-switch', '.el-radio-button', '.el-checkbox', '.el-radio',
  'input[type="checkbox"]', 'input[type="radio"]', 'label:has(input)',
].join(', ')

async function themeCandidates(page) {
  return page.evaluate(({ pattern, clickable }) => {
    const words = new RegExp(pattern, 'i')
    const chrome = [...document.querySelectorAll('.aim-header, .aim-aside')]
    const inShell = [...document.querySelectorAll(clickable)].filter(
      (el) => chrome.some((root) => root.contains(el)) && !el.closest('.el-menu'),
    )
    const describe = (el) => ({
      tag: el.tagName.toLowerCase(),
      cls: String(el.className || '').split(' ')[0] || '-',
      name: [el.getAttribute('aria-label'), el.getAttribute('title'), el.textContent.trim()]
        .filter(Boolean).join(' | ').slice(0, 80) || '(no accessible name)',
    })
    document.querySelectorAll('[data-t0175-candidate]').forEach(
      (el) => el.removeAttribute('data-t0175-candidate'),
    )
    const candidates = inShell.filter((el) => words.test([
      el.getAttribute('aria-label'), el.getAttribute('title'), el.className,
      el.id, el.name, el.textContent,
    ].filter(Boolean).join(' ')))
    candidates.forEach((el, index) => el.setAttribute('data-t0175-candidate', String(index)))
    return {
      searched: inShell.length,
      searchedPage: document.querySelectorAll(clickable).length,
      candidates: candidates.map(describe),
      // Enough of the neighbourhood to make a "nothing found" message useful.
      neighbours: inShell.slice(0, 24).map(describe),
    }
  }, { pattern: THEME_WORDS.source, clickable: CLICKABLE })
}

/** Press the control tagged as candidate `index`, or say the tag went stale. */
async function pressCandidate(page, index) {
  const clicked = await page.evaluate((i) => {
    const root = document.querySelector(`[data-t0175-candidate="${i}"]`)
    if (!root) return false
    const target = root.matches('input, button, a')
      ? root
      : root.querySelector('input, button, a, [role="switch"]') || root
    target.click()
    return true
  }, index)
  if (!clicked) throw new Error(`T-0175: the palette control at index ${index} vanished before it could be pressed`)
}

/** Wait up to a second for the page to settle into the dark palette. */
async function waitForDark(page) {
  for (let frame = 0; frame < 20; frame += 1) {
    if (isDark(await readTheme(page))) return true
    await page.waitForTimeout(50)
  }
  return false
}

/**
 * Flip the palette with whatever control names it, and say which one did it.
 * Returns `{ index, candidate, before }` on a light -> dark flip, and throws
 * with the measured state when no control in the shell does it.
 */
async function clickToDark(page) {
  const before = await readTheme(page)
  const found = await themeCandidates(page)
  if (!found.candidates.length) {
    throw new Error(
      `T-0175 FAIL: no control in the shell names the palette. Searched the ${found.searched} clickable `
      + `controls in .aim-header/.aim-aside (of ${found.searchedPage} on the page) for ${THEME_WORDS}; `
      + `the ones in the shell are: ${found.neighbours.map((c) => `${c.tag}.${c.cls}("${c.name}")`).join(', ')}. `
      + `Measured on load: html class "${before.htmlClass}", --el-bg-color ${before.cardBg} (light), `
      + `--aim-accent ${before.accent}, url ${before.href}, `
      + `localStorage ${JSON.stringify((await storedPreference(page)).localStorage)}.`,
    )
  }
  for (const index of found.candidates.keys()) {
    await pressCandidate(page, index)
    if (await waitForDark(page)) return { index, candidate: found.candidates[index], before }
  }
  const after = await readTheme(page)
  throw new Error(
    `T-0175 FAIL: ${found.candidates.length} shell control(s) name the palette `
    + `(${found.candidates.map((c) => `${c.tag}.${c.cls}("${c.name}")`).join(', ')}) but none of them flips it: `
    + `--el-bg-color stayed ${after.cardBg} (was ${before.cardBg}), html class "${after.htmlClass}" `
    + `(dark would be html.dark with Element Plus --el-bg-color #141414).`,
  )
}

/** Everywhere a choice could be remembered, as the page sees it. */
async function storedPreference(page) {
  return page.evaluate(() => ({
    localStorage: Object.fromEntries(Object.keys(localStorage).map((k) => [k, localStorage.getItem(k)])),
    sessionStorage: Object.fromEntries(Object.keys(sessionStorage).map((k) => [k, sessionStorage.getItem(k)])),
    cookie: document.cookie,
  }))
}

/**
 * The baseline. The card names light as the default (`:root` in style.css, with
 * the old dark values kept verbatim under `html.dark`), so this asserts the live
 * default rather than assuming it: a board that ships dark by default fails
 * here, and the failure message says which values were on screen.
 *
 * This one is not annotated: it passes on the measured revision.
 */
test('T-0175 baseline: the live default palette is light', async ({ page }) => {
  await openShell(page)
  const theme = await readTheme(page)
  const lum = luminance(theme.cardBg)

  expect(theme.darkClass, `html.dark is on the default page: class="${theme.htmlClass}"`).toBe(false)
  expect(lum, `--el-bg-color is ${theme.cardBg}, which is not a light surface`).not.toBeNull()
  expect(lum, `--el-bg-color is ${theme.cardBg} on the default page`).toBeGreaterThan(0.5)
  expect(theme.accent, `--aim-accent is ${theme.accent} on the default page`)
    .toBe('#0369a1')
  expect(theme.href).toContain('/#/')
})

/**
 * Clause 1 of the acceptance: a control in the shell flips light and dark.
 *
 * Measured on the red revision: the shell rendered 37 clickable controls and
 * none of them named the palette, so there was nothing to flip. The shell now
 * renders one -- `button.el-button("switch the board to the dark palette")` in
 * `.aim-header`, the only candidate the search finds -- and it is what this test
 * presses, in both directions.
 */
test('T-0175: a control in the shell flips light and dark', async ({ page }) => {
  await openShell(page)
  const { index, candidate, before } = await clickToDark(page)
  const dark = await readTheme(page)

  expect(luminance(dark.cardBg), `after clicking ${candidate.name}: --el-bg-color is ${dark.cardBg}`)
    .toBeLessThan(0.5)
  expect(dark.accent, `the accent did not move from the light value ${before.accent}`).not.toBe(before.accent)

  // "flips light and dark" is both directions: the same control has to come back.
  await pressCandidate(page, index)
  await expect
    .poll(async () => luminance((await readTheme(page)).cardBg), { timeout: 3000 })
    .toBeGreaterThan(0.5)
})

/**
 * Clause 2: the choice is remembered across reloads.
 *
 * A fresh navigation to the same origin reuses the browser context, so a
 * remembered choice must still be dark after the reload; a choice held only in
 * a Vue ref comes back light.
 */
test('T-0175: the choice survives a reload', async ({ page }) => {
  await openShell(page)
  await clickToDark(page)
  await page.reload()
  await page.waitForSelector('.aim-header', { state: 'visible' })
  const after = await readTheme(page)
  expect(isDark(after), `after a reload: html class "${after.htmlClass}", --el-bg-color ${after.cardBg}`).toBe(true)
})

/**
 * Clause 3: the choice is reflected in the URL or a stored preference rather
 * than only in memory.
 *
 * The flip is attempted first, but the preference surfaces are read either way,
 * so the failure message reports what exists rather than only what is missing.
 */
test('T-0175: the choice is reflected in the URL or a stored preference', async ({ page }) => {
  await openShell(page)
  const baseline = await readTheme(page)
  const storageBefore = await storedPreference(page)
  let flipped = false
  try {
    await clickToDark(page)
    flipped = true
  } catch {
    flipped = false
  }
  const theme = await readTheme(page)
  const storage = await storedPreference(page)

  const urlSays = /(theme|palette|dark|light)=/i.test(theme.href) || /theme=(dark|light)/i.test(decodeURIComponent(theme.href))
  const storedSays = [...Object.entries(storage.localStorage), ...Object.entries(storage.sessionStorage)]
    .some(([k, v]) => THEME_WORDS.test(k) || THEME_WORDS.test(String(v)))
  const cookieSays = THEME_WORDS.test(storage.cookie)

  expect(
    urlSays || storedSays || cookieSays,
    `no palette preference anywhere after ${flipped ? 'a successful flip' : 'a fresh load'}: `
    + `url ${theme.href} (unchanged from ${baseline.href}), `
    + `localStorage ${JSON.stringify(storage.localStorage)} (was ${JSON.stringify(storageBefore.localStorage)}), `
    + `sessionStorage ${JSON.stringify(storage.sessionStorage)}, cookie "${storage.cookie}". `
    + 'A choice that lives only in a Vue ref is the reset this clause forbids.',
  ).toBe(true)
})
