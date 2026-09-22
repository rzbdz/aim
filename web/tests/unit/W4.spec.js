import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * What the router is handed when a navigation happens, and what the actions it
 * leaves behind are allowed to do to the reader's scroll.
 *
 * `main.js` assembles the whole shell at import time -- Element Plus, the panes,
 * the store -- and none of that is what this file is about. What is about is the
 * single value the router is given: `scrollBehavior`. Vue Router awaits a promise
 * returned from it *before* it commits the navigation, so if that promise is a
 * wait on animation frames then a slow renderer decides when the reader's click
 * becomes a page. So everything main.js reaches for is replaced, `createRouter`
 * keeps that one option, and the renderer is a queue this file fires by hand --
 * and, since T-0225, a queue the code is not allowed to touch at all: a clause
 * that counts frames is now a clause that pins the *absence* of a frame request,
 * because a future tidy-up that reintroduces one is the regression the T-0225
 * rewrite exists to prevent.
 *
 * The retry that does the scrolling is an interval (main.js's `retryingUntil`,
 * RETRY_MS = 60), not a frame, and it is faked here along with `performance`,
 * which main.js reads through `performance.now()` for both deadlines. This is not
 * tidiness: while `setInterval` ran on the real clock and `performance` was
 * frozen, no tick could ever reach the write, so four clauses of this file could
 * not be satisfied by any version of main.js, and the two that went green went
 * green for the wrong reason -- a `frameRequests` that never leaves 0 satisfies
 * "gives up" as well as a real ceiling does, and "the listener was released" was
 * decided by how slowly the machine happened to run the file. The clock the code
 * reads is the clock the test must own.
 */
let scrollBehavior = null
let frames = []
let frameRequests = 0
let virtualNow = 0
let scroller = null
let target = null
let writes = 0
let retries = 0
let removals = []
let listeners = new Map()

vi.mock('vue', () => ({
  createApp: () => ({ use() {}, provide() {}, component() {}, mount() {} }),
  h: () => ({}),
}))
vi.mock('pinia', () => ({ createPinia: () => ({}) }))
vi.mock('vue-router', () => ({
  createRouter: (options) => { scrollBehavior = options.scrollBehavior; return {} },
  createWebHashHistory: () => ({}),
}))
vi.mock('element-plus', () => ({ default: {} }))
vi.mock('@element-plus/icons-vue', () => ({}))
vi.mock('element-plus/dist/index.css', () => ({}))
vi.mock('element-plus/theme-chalk/dark/css-vars.css', () => ({}))
vi.mock('github-markdown-css/github-markdown-light.css', () => ({}))
vi.mock('../../src/style.css', () => ({}))
vi.mock('../../src/App.vue', () => ({ default: {} }))
vi.mock('../../src/kernel', () => ({
  createContext: () => ({
    views: [],
    provide() {},
    use() {},
    service: () => ({}),
  }),
}))
vi.mock('../../src/composables/useTaskDrawer', () => ({ createTaskDrawer: () => ({}) }))
vi.mock('../../src/api', () => ({ createApi: () => ({}) }))
vi.mock('../../src/stores/board', () => ({
  useBoard: () => ({ viewer: 'human', init: () => Promise.resolve(), checkDigest() {} }),
}))
vi.mock('../../src/plugins/charts', () => ({ chartsPlugin: {} }))
vi.mock('../../src/plugins/markdown', () => ({ markdownPlugin: {} }))
vi.mock('../../src/views', () => ({ viewsPlugin: {} }))

await import('../../src/main.js')

/**
 * The clock moving in steps, with the timers it is moving past firing as it goes.
 *
 * The stepping is the whole point. A single `advanceTimersByTimeAsync(600)` runs
 * the clock to the end of the window and *then* lets the 60ms retry fire, so
 * every tick it fires reads a `performance.now()` already past the deadline and
 * the retry is reported as if it had never looked -- which is the same wrong
 * answer the unfaked clock gave, arrived at from a different direction. Ten
 * milliseconds at a time is what makes the deadline a deadline and the retry a
 * retry.
 */
const idle = async (ms) => {
  let left = ms
  while (left > 0) {
    const step = Math.min(10, left)
    virtualNow += step
    await vi.advanceTimersByTimeAsync(step)
    left -= step
  }
}

/** One frame, costing `ms` of wall-clock. Slow on purpose: that is the renderer. */
const frame = async (ms = 16) => {
  virtualNow += ms
  const callbacks = frames.splice(0)
  for (const callback of callbacks) callback()
  await vi.advanceTimersByTimeAsync(ms)
}

/** What a wheel does to the reset: the reader's own move outranks it. */
const readerWheels = () => {
  const wheel = listeners.get('wheel')
  if (wheel) wheel()
}

const navigate = (to, from = { path: '/items', hash: '' }) => scrollBehavior(to, from, null)

beforeEach(() => {
  // `setInterval` is in this list because the retry the code runs is an interval
  // (main.js:109). See the file comment: without it the harness owns a clock the
  // code does not read.
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
  virtualNow = 1000
  vi.stubGlobal('performance', { now: () => virtualNow })
  frames = []
  frameRequests = 0
  retries = 0
  removals = []
  listeners = new Map()
  vi.stubGlobal('requestAnimationFrame', (callback) => {
    frameRequests += 1
    frames.push(callback)
    return frameRequests
  })
  vi.stubGlobal('window', {
    location: { hash: '' },
    addEventListener: vi.fn((name, fn) => { listeners.set(name, fn) }),
    removeEventListener: vi.fn((name) => { removals.push(name); listeners.delete(name) }),
  })
  writes = 0
  // `40` is where the reader was sitting when the navigation starts. It is not 0
  // on purpose: a scroller already at its top makes every assertion about where
  // the reader ends up true for the wrong reason, so the stub starts them
  // somewhere else and the clauses below have to move it.
  scroller = {
    top: 40,
    get scrollTop() { return this.top },
    set scrollTop(value) { writes += 1; this.top = value },
    getBoundingClientRect: () => ({ top: 10 }),
    scrollTo: vi.fn(),
  }
  target = null
  vi.stubGlobal('document', { querySelector: () => scroller, getElementById: () => target })
  // The retry is counted rather than asserted on blindly: it is the 60ms interval
  // (main.js's RETRY_MS) and the store's digest poll is a 2500ms one, so only the
  // first is the action under test.
  const realSetInterval = globalThis.setInterval
  vi.stubGlobal('setInterval', (fn, ms) => {
    if (ms !== 60) return realSetInterval(fn, ms)
    retries += 1
    return realSetInterval(fn, ms)
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('a navigation to an anchor', () => {
  it('answers the router now, and the retry it arms is a timer rather than a frame', () => {
    const answer = navigate({ path: '/help', hash: '#row-1' })
    // What the reader is promised is unchanged in shape -- `scrollBehavior`
    // returns a plain value, so nothing about the navigation waits on the row --
    // but the action it leaves behind is a 60ms interval, so the frame queue is
    // *empty* here and `frameRequests` stays 0. This is the clause that used to
    // say `frames` had one entry and `frameRequests` was 1: no version of main.js
    // after the T-0225 rewrite can produce that, and a version that could would be
    // the regression T-0225 was filed for.
    expect(answer).toBe(false)
    expect(frames).toHaveLength(0)
    expect(frameRequests).toBe(0)
    expect(retries).toBe(1)
  })

  it('still lands on the row as soon as the retry has looked again', async () => {
    navigate({ path: '/help', hash: '#row-1' })
    expect(scroller.scrollTo).not.toHaveBeenCalled()
    target = { getBoundingClientRect: () => ({ top: 100 }) }
    // One RETRY_MS of clock rather than one frame, because what is being waited
    // for is a lazy chunk arriving over the network. The arithmetic is the same
    // arithmetic it always was -- 40 (already there) + (100 - 10), minus the 12px
    // that keeps the row off the pane's top edge -- because the offset is not the
    // part that moved. The assertion is exactly as strict as it was.
    await idle(60)
    expect(scroller.scrollTo).toHaveBeenCalledWith({ top: 118, behavior: 'auto' })
  })

  it('gives up at the wall-clock ceiling, and never asks the renderer for anything', async () => {
    navigate({ path: '/help', hash: '#row-1' })
    // ANCHOR_WAIT_MS is 1500 and the row never arrives, so the retry runs to its
    // ceiling and stops: one interval, no frames, and the pane untouched.
    await idle(1600)
    expect(retries).toBe(1)
    expect(frameRequests).toBe(0)
    expect(scroller.scrollTo).not.toHaveBeenCalled()
    const asked = writes
    await idle(600)
    expect(writes).toBe(asked)
  })

  it('stops when a newer navigation takes over the reading position', async () => {
    navigate({ path: '/help', hash: '#row-1' })
    // Same path, so this is a move *inside* one page rather than a pane change:
    // the reader keeps the position they had (main.js:316-318), which is why the
    // assertion below is that the position is untouched rather than that it is 0.
    navigate({ path: '/items', hash: '' })
    target = { getBoundingClientRect: () => ({ top: 100 }) }
    // The row exists now, so the anchor's retry would land on it if it were still
    // running; it was cancelled by the navigation that superseded it.
    await idle(600)
    expect(scroller.scrollTo).not.toHaveBeenCalled()
    expect(scroller.top).toBe(40)
    expect(retries).toBe(1)
  })

  it('answers the router with the renderer dead, as it is in a hidden tab', async () => {
    // What a dead renderer costs is nothing at all now: the retry is a timer, so
    // it makes progress in a tab that is not painting and still tidies itself up
    // at the ceiling. "There is no frame request anywhere in here on purpose"
    // (main.js:97) is the invariant this pins -- a stale frame request is the one
    // way a hidden tab can turn this action into a hang again.
    const answer = navigate({ path: '/help', hash: '#row-1' })
    expect(answer).toBe(false)
    expect(frameRequests).toBe(0)
    expect(retries).toBe(1)
    await idle(5000)
    const settled = retries
    await idle(5000)
    expect(retries).toBe(settled)
    expect(frameRequests).toBe(0)
  })
})

describe('a navigation to a different pane', () => {
  it('answers the router now and has the top written before it has', () => {
    const answer = navigate({ path: '/help' })
    // The reset writes `scrollTop` on the app's scroller (main.js:217) and does it
    // synchronously, before the router is answered -- the same shape of promise as
    // the anchor clause above, with the write asserted through the scroller the
    // code actually writes rather than a `scrollTo` this path never calls.
    expect(answer).toBe(false)
    expect(scroller.top).toBe(0)
    expect(retries).toBe(1)
    expect(frameRequests).toBe(0)
  })

  it('keeps writing while the incoming pane settles, because its mount can undo the first write', async () => {
    navigate({ path: '/help' })
    expect(scroller.top).toBe(0)
    // The incoming pane's mount putting the shared scroller back where the
    // leaving pane left it, with the reader having moved nothing: the retry is the
    // only thing that covers this, and a reset that wrote exactly once would leave
    // the reader at the previous page's position.
    scroller.top = 400
    await idle(120)
    expect(scroller.top).toBe(0)
  })

  it('stops the moment the reader takes the scroll, and does not write again', async () => {
    navigate({ path: '/help' })
    const parked = writes
    readerWheels()
    scroller.top = 900
    await idle(600)
    // A wheel inside the reset window is the reader choosing a position, and the
    // page is not allowed to take it back -- the same rule the store states for
    // its own reloads.
    expect(scroller.top).toBe(900)
    expect(writes).toBe(parked)
  })

  it('ends at the ceiling and lets the listeners go, whatever the renderer was doing', async () => {
    navigate({ path: '/help' })
    // Three times PANE_RESET_WAIT_MS of clock: the retry has had its window and is
    // over. `reader.done()` is the clause with teeth -- the reset takes five window
    // listeners on the way in (main.js:246) and a ceiling that stops the interval
    // without releasing them leaves a wheel handler behind per navigation, which
    // shows up only as a board that gets slower over a long read. It is also the
    // reason this file fakes `setInterval`: with the real one this assertion was
    // decided by the file's own load time, and it passed in a full run and failed
    // when the test ran alone.
    await idle(600)
    expect(removals).toContain('wheel')
    expect(removals).toContain('keydown')
    expect(removals).toHaveLength(5)
    // And the writes stopped with the window: a renderer that wakes up later gets
    // no say in where the reader is sitting.
    const parked = writes
    scroller.top = 500
    await idle(600)
    expect(scroller.top).toBe(500)
    expect(writes).toBe(parked)
  })

  it('keeps its hands off the pane on a renderer where a frame costs 300ms', async () => {
    navigate({ path: '/help' })
    for (let i = 0; i < 6; i += 1) await frame(300)
    // The old loop wrote ten times whatever the renderer was doing -- 3.2s at this
    // speed. The writes stop when the time is up, not when the frames are, and the
    // frames here are fired into a code path that does not hold them.
    const parked = writes
    scroller.top = 500
    await frame(300)
    expect(scroller.top).toBe(500)
    expect(writes).toBe(parked)
    expect(removals).toContain('wheel')
  })
})
