/**
 * Wiring, and nothing else.
 *
 * There is exactly one place that knows how the pieces are assembled: this file.
 * It provides services, loads plugins, builds the router from whatever views
 * registered themselves, and mounts. Adding a pane means adding a file under
 * `views/`; adding a service means one `provide`.
 */
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// Element Plus scopes its dark variables to `.dark`, so this import is inert
// until something puts that class on <html>. Keeping it here is what makes the
// palette a class flip rather than a second bundle.
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'github-markdown-css/github-markdown-light.css'
import * as Icons from '@element-plus/icons-vue'

import './style.css'
import App from './App.vue'
import { createContext } from './kernel'
import { createTaskDrawer } from './composables/useTaskDrawer'
import { createApi } from './api'
import { useBoard } from './stores/board'
import { chartsPlugin } from './plugins/charts'
import { markdownPlugin } from './plugins/markdown'
import { viewsPlugin } from './views'

const ctx = createContext('aimboard')
const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(ElementPlus)
for (const [name, component] of Object.entries(Icons)) app.component(name, component)

const board = useBoard(pinia)
ctx.provide('api', createApi({ getViewer: () => board.viewer }))
ctx.provide('board', board)
// One drawer for the whole shell. A pane opens a task; it does not own one.
ctx.provide('taskDrawer', createTaskDrawer())
ctx.use(chartsPlugin)
ctx.use(markdownPlugin)
ctx.use(viewsPlugin)

/**
 * The element a hash names, read from the address bar.
 *
 * The router is asked for the hash and the address bar is the authority, because
 * they can disagree: in hash mode the whole route lives in the fragment, so
 * `#/help#phase-resolve` has to be split by hand rather than trusted to be one
 * named anchor. Taking the last `#` as the separator is what makes the link a
 * reader copies out of the address bar identical to the one a chip generates.
 */
function anchorId(fromRouter) {
  const raw = window.location.hash.replace(/^#/, '')
  const cut = raw.lastIndexOf('#')
  const mine = cut === -1 ? '' : decodeURIComponent(raw.slice(cut + 1))
  const theirs = String(fromRouter || '').replace(/^#/, '')
  return mine || theirs
}

/**
 * How long a scroll action may keep asking the renderer for frames, in ms.
 *
 * A count of frames is not a bound. `requestAnimationFrame` is a promise the
 * renderer does not always keep: a busy one calls back late (at 20x CPU throttle
 * a frame here measured ~320ms, so ten frames of "reset the pane" is 3.2s), and
 * a hidden tab does not call back at all, which turns a wait for frames into a
 * wait forever. Wall-clock is the thing that runs out.
 */
const ANCHOR_WAIT_MS = 1500
const PANE_RESET_WAIT_MS = 200

/**
 * The next frame, or the deadline, whichever arrives first.
 *
 * The frame stays the fast path -- it is what keeps a write in the same paint as
 * the mount it is written for -- and the timer is the ceiling that makes the
 * wait bounded rather than frame-shaped.
 */
function frameOrDeadline(deadline) {
  return new Promise((next) => {
    const timer = setTimeout(next, Math.max(0, deadline - performance.now()))
    requestAnimationFrame(() => { clearTimeout(timer); next() })
  })
}

/**
 * Move the reading pane to an anchor, so a link to a row lands on that row.
 *
 * `vue-router`'s scroll handling is about the window, and the window does not
 * scroll here: the shell is a flex column and `.el-main` owns the overflow, so
 * the page stays 0px tall from the viewport's point of view and every anchor
 * scrolls nothing. Measured on `#/help#phase-cross_examine`: the pane's
 * `scrollTop` was 0 and the row was 1244px below the fold, and it was the same
 * whether the reader clicked a chip or typed the URL.
 *
 * So the anchor is resolved against the app's own scroller. The element is
 * retried across animation frames because a route's component is a lazy import:
 * on the first frame after navigation the row does not exist yet, and an anchor
 * that works only when the chunk is already cached is an anchor that works on
 * the second click.
 *
 * The retry is a *background* action and the router is answered now. Vue Router
 * awaits a promise returned from `scrollBehavior` before it commits the
 * navigation, so a retry that was returned here made every anchor navigation
 * wait on frames -- measured at 20x CPU throttle, a frame on this board took
 * ~320ms and thirty of them is ten seconds of a reader watching a URL not
 * change. Nothing about landing on a row needs the navigation held open for it.
 */
function scrollToAnchor(hash, epoch) {
  const id = anchorId(hash)
  if (!id) return false
  const put = () => {
    const scroller = document.querySelector('.aim-main')
    const target = document.getElementById(id)
    if (!scroller || !target) return false
    const top = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top
    // `scrollIntoView` would move the window too, and the window is not what the
    // reader is looking through. The offset leaves the whole row visible rather
    // than clipped against the pane's top edge.
    scroller.scrollTo({ top: Math.max(0, scroller.scrollTop + top - 12), behavior: 'auto' })
    return true
  }
  const deadline = performance.now() + ANCHOR_WAIT_MS
  const tick = async () => {
    for (let frame = 0; frame < 30; frame += 1) {
      // A newer navigation supersedes this one: an anchor that lands after the
      // reader has asked for something else is the reader being moved by a page
      // they left.
      if (epoch !== scrollEpoch) return
      if (put()) return
      if (performance.now() >= deadline) return
      await frameOrDeadline(deadline)
    }
  }
  tick()
  return false
}

/**
 * Put a freshly arrived pane at its top.
 *
 * The app's scroller is `.aim-main`, and nothing reset it on navigation, so the
 * reader kept the previous page's position. Measured live at 1280x800: `#/items`
 * scrolled to 4787/4787, then the nav's "Help & concepts" -> `#/help` at
 * 3937/3937, the bottom of a 4688px page. Clicking Help to escape a wall of
 * numbers and arriving in the glossary at the end of it is not a scroll bug, it
 * is the page ignoring which way the reader asked to go.
 *
 * Only a *pane* change resets. A filter, an anchor or a thread is a move inside
 * one list, and a reader who narrowed a list must not be thrown back to its top
 * for it -- the same distinction the drawer's lifecycle rule draws, for the same
 * reason.
 *
 * It is written across frames rather than once, because a route is a lazy import:
 * on the first frame the scroller still holds the pane that is leaving, and a
 * single write is undone by the incoming pane's own mount. But a loop that keeps
 * writing is a loop that can fight the reader, and it did: a test that wheeled
 * within 166ms of arriving watched the pane snap back to 0. So the loop stops the
 * instant the reader scrolls. This is the same rule `readingInterrupt` in the
 * store states, for the same reason -- nothing here scrolls under the reader's
 * hands.
 *
 * Ten frames is also not a length of time: on a renderer slow enough to matter,
 * ten frames outlives the navigation that started it. The wall-clock ceiling ends
 * the writes whatever the renderer is doing.
 */
function resetReadingPane(epoch) {
  // Deliberately not awaited by the caller. `vue-router` awaits a promise
  // returned from `scrollBehavior` before it considers the navigation finished,
  // and a navigation that completes ten frames late is a navigation a pane can
  // be reset out of -- the exact thing this function exists to prevent. The loop
  // is started and left to run; the router gets its answer now.
  const reader = watchingForReaderScroll()
  const deadline = performance.now() + PANE_RESET_WAIT_MS
  const tick = async () => {
    for (let frame = 0; frame < 10; frame += 1) {
      if (epoch !== scrollEpoch || reader.moved()) break
      const scroller = document.querySelector('.aim-main')
      if (scroller) scroller.scrollTop = 0
      if (performance.now() >= deadline) break
      await frameOrDeadline(deadline)
    }
    reader.done()
  }
  tick()
  return false
}

/**
 * Whether the reader has taken over the scroll since this was called.
 *
 * A wheel, a touch, a drag or a key is the reader moving the page themselves, and
 * it outranks anything the router was doing on its way in. `capture`, so it is
 * seen wherever it lands, and `passive`, because nothing here prevents anything.
 */
function watchingForReaderScroll() {
  const events = ['wheel', 'touchstart', 'touchmove', 'pointerdown', 'keydown']
  let moved = false
  const mark = () => { moved = true }
  for (const name of events) window.addEventListener(name, mark, { passive: true, capture: true })
  return {
    moved: () => moved,
    done() {
      for (const name of events) window.removeEventListener(name, mark, { capture: true })
    },
  }
}

/**
 * Which navigation owns the reading position right now.
 *
 * A scroll action outlives the tick that started it -- the reset above writes
 * across frames, and an anchor waits frames for a lazy chunk. Without this, the
 * tail of one navigation's reset lands *after* the next navigation's anchor and
 * wipes it: measured on the phase chip, `scrollToAnchor` moved the pane to 1195
 * and the pane ended at 0, one run in five, depending on whether the chip was
 * clicked inside the previous route's reset window. A scroll that is still
 * running when the reader has asked for something else is not a scroll the reader
 * asked for.
 */
let scrollEpoch = 0

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: () => `/${ctx.views[0]?.key || 'overview'}` },
    ...ctx.views.map((v) => ({
      path: `/${v.key}`, name: v.key, component: v.component,
      meta: { title: v.title, view: v.key },
    })),
    { path: '/:pathMatch(.*)*', component: { render: () => h('p', { class: 'aim-dim' }, 'no such pane') } },
  ],
  scrollBehavior(to, from, savedPosition) {
    const epoch = (scrollEpoch += 1)
    // A hash that names a row is a link to that row, so resolving it is the whole
    // point of the navigation.
    if (to.hash) return scrollToAnchor(to.hash, epoch)
    // Going *back* to a page the browser remembers is the one case where the
    // reader asked for the position they had, so it is restored and nothing else
    // is done to it.
    if (savedPosition) return savedPosition
    // Otherwise the reader asked for a different page: it opens at its top. A
    // move *inside* a page -- a filter, a thread, an anchor -- keeps its position,
    // so only a path change is a different page.
    if (to.path !== from.path) return resetReadingPane(epoch)
    return false
  },
})

app.use(router)
app.provide('ctx', ctx)
app.component('VChart', ctx.service('VChart'))

board.init(ctx.service('api')).then(() => {
  // The record is a live thing: a peer writes, the digest changes, and the board
  // catches up on its own. There is no refresh button to press and no "the record
  // has moved" banner, because a refresh is not an error and the reader did not
  // ask to be interrupted. The two things that *do* interrupt a reader -- unsent
  // text in a field, and a scroll position someone chose deliberately -- are
  // protected inside the store, which defers and says so quietly instead of
  // reloading the page under their hands.
  setInterval(() => board.checkDigest(), 2500)
})

app.mount('#app')
