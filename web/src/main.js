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
 */
async function scrollToAnchor(hash) {
  const id = anchorId(hash)
  if (!id) return false
  let scroller = null
  let target = null
  for (let frame = 0; frame < 30 && (!scroller || !target); frame += 1) {
    scroller = document.querySelector('.aim-main')
    target = document.getElementById(id)
    if (!scroller || !target) await new Promise((next) => requestAnimationFrame(next))
  }
  if (!scroller || !target) return false
  const top = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top
  // `scrollIntoView` would move the window too, and the window is not what the
  // reader is looking through. The offset leaves the whole row visible rather
  // than clipped against the pane's top edge.
  scroller.scrollTo({ top: Math.max(0, scroller.scrollTop + top - 12), behavior: 'auto' })
  return false
}

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
    // A hash that names a row is a link to that row, so resolving it is the whole
    // point of the navigation. Everything else -- every ordinary route change, and
    // every return to a page the browser remembers -- leaves the reading position
    // alone. Moving a reader who did not ask to be moved is the same defect as
    // failing to move one who did.
    if (to.hash) return scrollToAnchor(to.hash)
    return savedPosition || false
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
