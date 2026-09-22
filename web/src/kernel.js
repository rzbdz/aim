/**
 * A kernel, in the shape cordis uses - and the same shape as `aimboard/kernel.py`
 * on the Python side, deliberately, so that "a view is a plugin" means one thing
 * in this project rather than two.
 *
 * The idea worth taking from cordis (the meta-framework behind Koishi) is small
 * and specific: **the context owns what exists.** A plugin is a function that
 * receives the context and registers what it provides; a service is looked up by
 * name; nothing reaches across to a concrete sibling module. Two properties fall
 * out of that, and both are testable:
 *
 *   1. `no view imports another view` - a pane can be deleted, reordered or
 *      replaced without touching the shell or its neighbours.
 *   2. adding a view is adding one file - `views/index.js` globs the directory,
 *      so the shell never names a pane.
 *
 * Deliberately about fifty lines. A framework large enough to need its own
 * documentation would be a second thing to maintain, and this project has
 * already measured what a second implementation of a rule costs.
 */

export class Context {
  constructor(name = 'aimboard') {
    this.name = name
    this.services = new Map()
    this.views = []
    this.plugins = []
    this.hooks = new Map()
    this.app = null
  }

  // -- services ------------------------------------------------------------
  provide(name, value) {
    if (this.services.has(name)) {
      throw new Error(`service '${name}' is already provided by the context`)
    }
    this.services.set(name, value)
    return value
  }

  service(name) {
    if (!this.services.has(name)) {
      throw new Error(
        `no service '${name}'; provided: ${[...this.services.keys()].sort().join(', ')}`,
      )
    }
    return this.services.get(name)
  }

  // -- plugins -------------------------------------------------------------
  use(plugin, options = {}) {
    if (typeof plugin !== 'function') {
      throw new Error('a plugin is a function taking (ctx, options)')
    }
    plugin(this, options)
    this.plugins.push(plugin.name || 'anonymous')
    return this
  }

  // -- views ---------------------------------------------------------------
  registerView(def) {
    for (const field of ['key', 'title', 'component']) {
      if (!def?.[field]) throw new Error(`a view needs a '${field}'`)
    }
    if (this.views.some((v) => v.key === def.key)) {
      throw new Error(`view '${def.key}' is already registered`)
    }
    this.views.push({ order: 50, icon: 'Grid', ...def })
    this.views.sort((a, b) => a.order - b.order || (a.key < b.key ? -1 : 1))
    return def
  }

  routeRecords(parent = '/', name = 'view') {
    return this.views.map((v) => ({
      path: v.path || v.key,
      name: `${name}-${v.key}`,
      component: v.component,
      meta: { viewKey: v.key, title: v.title },
    })).concat(parent ? [] : [])
  }

  // -- lifecycle -----------------------------------------------------------
  on(event, fn) {
    if (!this.hooks.has(event)) this.hooks.set(event, [])
    this.hooks.get(event).push(fn)
    return this
  }

  async emit(event, ...args) {
    for (const fn of this.hooks.get(event) || []) await fn(...args)
  }
}

export function createContext(name) {
  return new Context(name)
}
