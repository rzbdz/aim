/**
 * Views register themselves.
 *
 * `import.meta.glob` is the whole extension point: dropping a file into
 * `views/` adds a pane, and nothing in the shell names a pane. That is the same
 * property the Python kernel gives `aimboard/views/` - deliberately the same,
 * because "a view is a plugin" should mean one thing in this project.
 */
const modules = import.meta.glob('./*.js', { eager: true })

export function viewsPlugin(ctx) {
  for (const mod of Object.values(modules)) {
    const view = mod.default || mod.view
    if (view) ctx.registerView(view)
  }
}
