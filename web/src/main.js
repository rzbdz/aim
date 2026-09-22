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
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'github-markdown-css/github-markdown-dark.css'
import * as Icons from '@element-plus/icons-vue'

import './style.css'
import App from './App.vue'
import { createContext } from './kernel'
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
ctx.use(chartsPlugin)
ctx.use(markdownPlugin)
ctx.use(viewsPlugin)

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
