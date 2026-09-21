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
      meta: { title: v.title, titleZh: v.titleZh, view: v.key },
    })),
    { path: '/:pathMatch(.*)*', component: { render: () => h('p', { class: 'aim-dim' }, 'no such pane') } },
  ],
})

app.use(router)
app.provide('ctx', ctx)
app.component('VChart', ctx.service('VChart'))

board.init(ctx.service('api')).then(() => {
  // Ask the server whether the *record* moved, rather than reloading the page.
  // A dashboard that reloads itself throws away your scroll position and your
  // place in a long message; a banner lets you finish the sentence first.
  setInterval(() => board.checkDigest(), 15000)
})

app.mount('#app')
