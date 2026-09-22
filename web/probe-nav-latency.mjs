/**
 * Is a route change bound by animation frames? (T-0225)
 *
 * `web/src/main.js` returns `resetReadingPane()` from the router's
 * `scrollBehavior`, and Vue Router awaits a promise returned there before it
 * settles the navigation. That much is a fact about Vue Router and is proved by
 * this probe's `never` arm, not by timing: with a `scrollBehavior` that returns a
 * promise which never resolves, the router's `afterEach` never fires and
 * `currentRoute` stays where it was.
 *
 * What that fact *costs the reader* is a separate question, and it is the one
 * this file exists to answer. Three arms separate the parts:
 *
 *   control   `() => false`  -- the pre-81dc58f answer for an ordinary path
 *              change. No promise at all.
 *   micro     `() => Promise.resolve(false)` -- a promise the router awaits,
 *              with no frame in it. A plain value and an already-resolved
 *              promise differ by one microtask hop and by nothing else, so if
 *              the card's mechanism is "the router awaits the reset", `micro`
 *              measures that mechanism at a cost of ~0ms.
 *   card      the shape HEAD 81dc58f ships: an `async` loop of ten
 *              `requestAnimationFrame` turns, returned and therefore awaited.
 *   writes    the same ten-frame loop started and left to run, a plain value
 *              returned now. Same writes, same frames, no promise.
 *   silent    the same loop, started and left to run, writing nothing. Isolates
 *              whether *ten `scrollTop = 0` writes* cost renderer time, which is
 *              a different mechanism from the promise and would starve the frame
 *              clock on its own.
 *
 * Two things about the measurement matter more than the numbers, because both
 * were got wrong by the probe this replaces:
 *
 *  1. The navigation is started with `router.push()`, the way a nav click starts
 *     one. The previous version wrote `window.location.hash` and then waited for
 *     `location.hash` to change -- but writing the hash *is* the address bar
 *     changing, so its own precondition was true before the router ran and its
 *     clock measured nothing.
 *  2. The address bar is polled on a **timer**, never `requestAnimationFrame`.
 *     Playwright's `waitForFunction`/`toHaveURL` poll in rAF by default
 *     (`node_modules/playwright-core/types/types.d.ts:26270`), so a probe that
 *     polls in rAF measures the renderer's frame clock -- the thing under
 *     suspicion -- rather than the router.
 *
 * Run:  cd web && node probe-nav-latency.mjs [--rate N] [--rounds N]
 * The board must already be up on http://127.0.0.1:8777. This starts nothing.
 */
import { chromium } from 'playwright'

const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`)
  return i === -1 ? fallback : Number(process.argv[i + 1])
}
const RATE = arg('rate', 1)
const ROUNDS = arg('rounds', 4)
const CAP = arg('cap', 20000)

const BEHAVIOURS = {
  control: '() => false',
  micro: '() => Promise.resolve(false)',
  card: `async () => {
    for (let i = 0; i < 10; i += 1) { const s = document.querySelector('.aim-main'); if (s) s.scrollTop = 0; await new Promise((n) => requestAnimationFrame(n)) }
    return false
  }`,
  writes: `() => {
    const t = async () => { for (let i = 0; i < 10; i += 1) { const s = document.querySelector('.aim-main'); if (s) s.scrollTop = 0; await new Promise((n) => requestAnimationFrame(n)) } }
    t(); return false
  }`,
  silent: `() => {
    const t = async () => { for (let i = 0; i < 10; i += 1) { await new Promise((n) => requestAnimationFrame(n)) } }
    t(); return false
  }`,
}

const ROUTES = ['/help', '/items', '/kanban', '/attention', '/reports', '/plan', '/gantt', '/barrier']

/** Install the arms and the in-page instrument. Runs once per page. */
function install(behaviours) {
  window.__behaviours = behaviours
  window.__router = document.getElementById('app').__vue_app__.config.globalProperties.$router
  // The board's own behaviour, kept so one arm can hand the slot back: the
  // reader's question is about what is shipped, not only about arms we wrote.
  window.__shipped = window.__router.options.scrollBehavior
  window.__setBehaviour = (name) => {
    window.__router.options.scrollBehavior = name === 'shipped'
      ? window.__shipped
      : new Function(`return (${window.__behaviours[name]})`)()
  }
  window.__arm = (path, capMs) => new Promise((resolve) => {
    const router = window.__router
    const t0 = performance.now()
    const out = { path, urlAt: null, routeAt: null, domAt: null, settleAt: null, frames: 0, maxGap: 0, timedOut: false, top: null }
    const scroller = () => document.querySelector('.aim-main')
    out.topBefore = scroller() ? Math.round(scroller().scrollTop) : -1
    let done = false
    let last = t0
    let off = null
    const raf = () => {
      const now = performance.now()
      const gap = now - last
      last = now
      out.frames += 1
      if (gap > out.maxGap) out.maxGap = Math.round(gap)
      if (done) {
        out.settleAt = Math.round(now - t0)
        out.top = scroller() ? Math.round(scroller().scrollTop) : -1
        resolve(out)
        return
      }
      requestAnimationFrame(raf)
    }
    requestAnimationFrame(raf)
    off = router.afterEach(() => { if (out.routeAt === null) out.routeAt = Math.round(performance.now() - t0) })
    const main = scroller()
    const mo = new MutationObserver(() => { if (out.domAt === null) out.domAt = Math.round(performance.now() - t0) })
    if (main) mo.observe(main, { childList: true, subtree: true })

    // The address bar, polled by timer with a 4ms floor -- never rAF.
    const want = `#${path}`
    const pollUrl = () => {
      if (window.location.hash === want || window.location.hash.startsWith(`${want}#`)) {
        if (out.urlAt === null) out.urlAt = Math.round(performance.now() - t0)
        return
      }
      if (!done) setTimeout(pollUrl, 4)
    }
    setTimeout(pollUrl, 0)

    router.push(path).catch(() => {})
    const check = () => {
      if (done) return
      if (performance.now() - t0 > capMs) { done = true; out.timedOut = true; return }
      if (out.routeAt !== null && out.domAt !== null) { done = true; return }
      setTimeout(check, 4)
    }
    setTimeout(check, 0)
    const finish = setInterval(() => { if (done) { clearInterval(finish); mo.disconnect(); off() } }, 8)
  })
  /** The router's own promise, which is what a caller of `push()` waits on. */
  window.__push = (path, capMs) => new Promise((resolve) => {
    const t0 = performance.now()
    const timer = setTimeout(() => resolve({ settled: null, rejected: null, timedOut: true }), capMs)
    window.__router.push(path).then(
      () => { clearTimeout(timer); resolve({ settled: Math.round(performance.now() - t0), rejected: null, timedOut: false }) },
      () => { clearTimeout(timer); resolve({ settled: null, rejected: Math.round(performance.now() - t0), timedOut: false }) },
    )
  })
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
const cdp = await page.context().newCDPSession(page)
await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE })

await page.goto('http://127.0.0.1:8777/#/help', { waitUntil: 'load' })
await page.waitForTimeout(2500)
await page.evaluate(install, BEHAVIOURS)

const names = ['shipped', ...Object.keys(BEHAVIOURS)]
const rows = Object.fromEntries(names.map((n) => [n, []]))
const pushes = Object.fromEntries(names.map((n) => [n, []]))

// Interleaved, so a board that drifts under us drifts under every arm equally.
// Consecutive arms get different routes, so each navigation is a real path change.
const plan = []
for (let i = 0; i < ROUNDS * names.length; i += 1) plan.push([names[i % names.length], ROUTES[i % ROUTES.length]])

for (const [name, path] of plan) {
  await page.evaluate((n) => window.__setBehaviour(n), name)
  const r = await page.evaluate(([p, cap]) => window.__arm(p, cap), [path, CAP])
  rows[name].push(r)
}
for (const name of names) {
  await page.evaluate((n) => window.__setBehaviour(n), name)
  pushes[name].push(await page.evaluate(([p, cap]) => window.__push(p, cap), [ROUTES[ROUTES.length - 1], CAP]))
}

const col = (xs, key) => {
  const v = xs.map((x) => x[key]).filter((x) => x !== null && x !== undefined)
  if (!v.length) return '   none'
  v.sort((a, b) => a - b)
  const mid = Math.floor(v.length / 2)
  return `${String(v[0]).padStart(6)} / ${String(v[mid]).padStart(6)} / ${String(v[v.length - 1]).padStart(6)}`
}
console.log(`board http://127.0.0.1:8777   cpu x${RATE}   ${ROUNDS} navigations per arm   cap ${CAP}ms`)
console.log('columns are min / median / max in ms, from the `router.push()` call\n')
console.log('arm       url(addr bar)     route(afterEach)  dom(.aim-main)    settle            frames   maxGap')
for (const n of names) {
  const r = rows[n]
  const frames = r.map((x) => x.frames).sort((a, b) => a - b)
  const gaps = r.map((x) => x.maxGap).sort((a, b) => a - b)
  console.log(`${n.padEnd(9)} ${col(r, 'urlAt')}   ${col(r, 'routeAt')}   ${col(r, 'domAt')}   ${col(r, 'settleAt')}   ${String(frames[Math.floor(frames.length / 2)]).padStart(6)}  ${String(gaps[Math.floor(gaps.length / 2)]).padStart(6)}`)
}
console.log('\nrouter.push() promise (what a caller of push() waits for):')
for (const n of names) {
  const p = pushes[n]
  console.log(`  ${n.padEnd(9)} ${p.map((x) => x.timedOut ? `>${CAP}` : (x.settled ?? `rej ${x.rejected}`)).join(', ')}`)
}
console.log('\nper-navigation:')
for (const [name, path] of plan) {
  const r = rows[name].shift()
  console.log(`  ${name.padEnd(9)} -> ${path.padEnd(10)} url ${String(r.urlAt).padStart(6)}  route ${String(r.routeAt).padStart(6)}  dom ${String(r.domAt).padStart(6)}  set ${String(r.settleAt).padStart(6)}  frames ${String(r.frames).padStart(4)}  maxGap ${String(r.maxGap).padStart(6)}  top ${String(r.topBefore).padStart(6)} -> ${String(r.top)}${r.timedOut ? '  TIMEOUT' : ''}`)
}

/*
 * The decisive check, and it is a decision rather than a duration: with a
 * `scrollBehavior` that returns a promise which never resolves, has the
 * navigation happened? If the router does not await the return value,
 * `currentRoute` moves and `afterEach` fires anyway. If it does, neither does --
 * and no amount of CPU explains that. Last, because it leaves a navigation
 * pending on purpose.
 */
const waited = RATE === 1 ? 2000 : 10000
const awaited = await page.evaluate(async ([waitMs]) => {
  const router = window.__router
  let askedFor = null
  router.options.scrollBehavior = (to) => { askedFor = to.fullPath; return new Promise(() => {}) }
  const before = router.currentRoute.value.fullPath
  let afterEachFired = false
  const off = router.afterEach(() => { afterEachFired = true })
  router.push('/plan')
  await new Promise((n) => setTimeout(n, waitMs))
  const out = {
    before,
    askedFor,
    currentRouteAfter: router.currentRoute.value.fullPath,
    afterEachFired,
    addressBar: location.hash,
  }
  off()
  return out
}, [waited])
console.log(`\nscrollBehavior returning a promise that never resolves, ${waited}ms later:`)
console.log(`  before            ${awaited.before}`)
console.log(`  push('/plan')     scrollBehavior saw ${awaited.askedFor}`)
console.log(`  currentRoute      ${awaited.currentRouteAfter}  <- did the navigation commit?`)
console.log(`  afterEach fired   ${awaited.afterEachFired}`)
console.log(`  address bar       ${awaited.addressBar}`)
console.log(awaited.currentRouteAfter === '/plan' && awaited.afterEachFired
  ? '  => the router does NOT await scrollBehavior; the card\'s mechanism is wrong.'
  : '  => the router DOES await scrollBehavior; the mechanism is a fact.')

await browser.close()
