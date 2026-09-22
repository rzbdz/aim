import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * What the router is handed when a navigation happens.
 *
 * `main.js` assembles the whole shell at import time -- Element Plus, the panes,
 * the store -- and none of that is what this file is about. What is about is the
 * single value the router is given: `scrollBehavior`. Vue Router awaits a promise
 * returned from it *before* it commits the navigation, so if that promise is a
 * wait on animation frames then a slow renderer decides when the reader's click
 * becomes a page. So everything main.js reaches for is replaced, `createRouter`
 * keeps that one option, and the renderer is a queue this file fires by hand.
 */
let scrollBehavior = null
let frames = []
let frameRequests = 0
let virtualNow = 0
let scroller = null
let target = null
let writes = 0

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

/** One frame, costing `ms` of wall-clock. Slow on purpose: that is the renderer. */
const frame = async (ms = 16) => {
  virtualNow += ms
  const callbacks = frames.splice(0)
  for (const callback of callbacks) callback()
  await vi.advanceTimersByTimeAsync(ms)
}

/**
 * The clock moving with the renderer dead.
 *
 * A hidden tab is not a slow tab: `requestAnimationFrame` there is a callback
 * that is queued and not fired, so a wait made of frames is a wait that never
 * arrives. Timers still run, which is what makes a wall-clock ceiling a ceiling.
 */
const idle = async (ms) => {
  virtualNow += ms
  await vi.advanceTimersByTimeAsync(ms)
}

const navigate = (to, from = { path: '/items', hash: '' }) => scrollBehavior(to, from, null)

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  virtualNow = 1000
  vi.stubGlobal('performance', { now: () => virtualNow })
  frames = []
  frameRequests = 0
  vi.stubGlobal('requestAnimationFrame', (callback) => {
    frameRequests += 1
    frames.push(callback)
    return frameRequests
  })
  vi.stubGlobal('window', {
    location: { hash: '' },
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })
  writes = 0
  scroller = {
    top: 40,
    get scrollTop() { return this.top },
    set scrollTop(value) { writes += 1; this.top = value },
    getBoundingClientRect: () => ({ top: 10 }),
    scrollTo: vi.fn(),
  }
  target = null
  vi.stubGlobal('document', { querySelector: () => scroller, getElementById: () => target })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('a navigation to an anchor', () => {
  it('answers the router now instead of after frames', () => {
    const answer = navigate({ path: '/help', hash: '#row-1' })
    expect(answer).toBe(false)
    expect(frames).toHaveLength(1)
    expect(frameRequests).toBe(1)
  })

  it('still lands on the row as soon as the lazy pane has made it', async () => {
    navigate({ path: '/help', hash: '#row-1' })
    expect(scroller.scrollTo).not.toHaveBeenCalled()
    target = { getBoundingClientRect: () => ({ top: 100 }) }
    await frame()
    // 40 (already there) + (100 - 10) - 12: the row sits below the pane's top edge.
    expect(scroller.scrollTo).toHaveBeenCalledWith({ top: 118, behavior: 'auto' })
  })

  it('gives up at a wall-clock ceiling when the row never arrives', async () => {
    navigate({ path: '/help', hash: '#row-1' })
    for (let i = 0; i < 40; i += 1) await frame(300)
    const asked = frameRequests
    // 300ms frames: a 1500ms ceiling is ~five frames, not the thirty the old
    // retry would have spent nine seconds on.
    expect(asked).toBeLessThanOrEqual(7)
    expect(asked).toBeLessThan(30)
    await frame(300)
    await frame(300)
    expect(frameRequests).toBe(asked)
  })

  it('stops when a newer navigation takes over the reading position', async () => {
    navigate({ path: '/help', hash: '#row-1' })
    navigate({ path: '/items', hash: '' })
    target = { getBoundingClientRect: () => ({ top: 100 }) }
    await frame(16)
    await frame(16)
    expect(scroller.scrollTo).not.toHaveBeenCalled()
  })

  it('answers the router with the renderer dead, as it is in a hidden tab', async () => {
    // The frame this retry is waiting for may never be fired -- a background tab
    // queues it until the tab is shown again. The old `scrollBehavior` returned
    // the retry, so vue-router awaited a callback that had not been promised a
    // time. This answers now, and the retry tidies itself up at the ceiling.
    const answer = navigate({ path: '/help', hash: '#row-1' })
    expect(answer).toBe(false)
    expect(frameRequests).toBe(1)
    await idle(5000)
    expect(frameRequests).toBe(1)
  })
})

describe('a navigation to a different pane', () => {
  it('answers the router now and writes the top in the background', () => {
    const answer = navigate({ path: '/help' })
    expect(answer).toBe(false)
    expect(scroller.top).toBe(0)
    expect(frameRequests).toBe(1)
  })

  it('ends at the ceiling when no frame ever arrives, and lets the listener go', async () => {
    navigate({ path: '/help' })
    await idle(600)
    // Two writes: the one on the way in, and one more the moment the ceiling is
    // reached. Under the old loop this was a promise parked on an rAF, so the
    // reader's wheel listener was never removed and the loop never ended.
    expect(writes).toBeLessThanOrEqual(3)
    expect(window.removeEventListener).toHaveBeenCalled()
    const parked = writes
    await frame(16)
    expect(writes).toBe(parked)
  })

  it('ends at the ceiling on a renderer where a frame costs 300ms', async () => {
    navigate({ path: '/help' })
    for (let i = 0; i < 6; i += 1) await frame(300)
    // The old loop wrote ten times whatever the renderer was doing -- 3.2s at
    // this speed. The writes stop when the time is up, not when the frames are.
    expect(writes).toBeLessThanOrEqual(3)
    expect(window.removeEventListener).toHaveBeenCalled()
  })
})
