// T-0190 verification: render the REAL PlanPane.vue twice -- the committed
// version and the working-tree version -- through the real Vue runtime and the
// real live payload, and print the sentence and the rows each one produces.
//
// Why it is built this way: the board on 8777 serves web/dist, and web/dist is
// the coordinator's build (BRIEF2 rule 2: nobody else runs `npm run build`). So
// the served bundle can only ever show this pane's *before* state. To measure
// the *after* without a build, this compiles `web/src/panes/PlanPane.vue` with
// @vue/compiler-sfc, rewrites its module specifiers to absolute paths, mounts it
// in a pinia store holding the payload fetched from 127.0.0.1:8777, and
// server-renders the resulting HTML. Both variants run through the same harness,
// so the difference in the output is the edit and nothing else.
//
// It is a render of the real component and the real data; it is NOT a browser,
// and the parts it stubs are named in the report (el-*, RouterLink, TaskLink,
// useQueryFilters) because they are other cards' code, not this one's.
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

/**
 * `before` is the committed pane, read out of git and written to the scratch
 * directory. It is written *inside* the scratch directory on purpose: nothing in
 * this prompt's rules is being edited outside the two files this task owns, and a
 * copy of HEAD in `tmp-t0190/` is a measurement input rather than a change to the
 * repository. `git show` is a read.
 */
const WEB = resolve(import.meta.dirname)
const ROOT = resolve(WEB, '..')
const TMP = join(WEB, 'tmp-t0190')
const BOARD = process.env.AIM_URL || 'http://127.0.0.1:8777'
const require = createRequire(join(WEB, 'package.json'))
const { parse, compileScript } = require('@vue/compiler-sfc')
const { register } = await import('node:module')

rmSync(TMP, { recursive: true, force: true })
mkdirSync(TMP, { recursive: true })
writeFileSync(join(TMP, 'before.vue'),
  execFileSync('git', ['show', 'HEAD:web/src/panes/PlanPane.vue'], { cwd: ROOT, maxBuffer: 1 << 24 }))

/**
 * `src/stores/board.js` imports `../theme` with no extension, because vite
 * resolves that and node does not. The hook only retries a failed relative
 * resolve with the extensions the bundler would have tried; it changes nothing
 * about which module is loaded.
 */
writeFileSync(join(TMP, 'loader.mjs'), `
export async function resolve(specifier, context, next) {
  try {
    return await next(specifier, context)
  } catch (err) {
    for (const ext of ['.js', '.mjs', '/index.js']) {
      try { return await next(specifier + ext, context) } catch { /* try the next */ }
    }
    throw err
  }
}
`)
register(pathToFileURL(join(TMP, 'loader.mjs')).href)

const { createSSRApp, h } = await import('vue')
const { renderToString } = await import('@vue/server-renderer')
const { createPinia, setActivePinia } = await import('pinia')
const { useBoard } = await import(pathToFileURL(join(WEB, 'src/stores/board.js')).href)

/**
 * Compile a .vue file to a plain ES module node can import.
 *
 * `compileScript(..., { inlineTemplate: true })` emits the render function into
 * `setup`, exactly as the vite build does, so the module this harness imports is
 * the same program the bundle runs. Only the module specifiers are rewritten:
 * relative paths become absolute file URLs (the generated file does not live
 * next to the source), and the four stubs below replace the modules that need
 * the browser, the drawer or the router.
 */
function compile(componentPath, outPath, baseDir) {
  const source = readFileSync(componentPath, 'utf8')
  const { descriptor } = parse(source, { filename: componentPath })
  const stubs = {
    [join(WEB, 'src/composables/useQueryFilters.js')]: join(TMP, 'stub-filters.mjs'),
    [join(WEB, 'src/composables/useTaskDrawer.js')]: join(TMP, 'stub-drawer.mjs'),
    // TaskLink reaches for `inject('ctx')`, which only exists in the shell; its
    // own behaviour (a dead-end id opens the drawer) is T-0159's card.
    [join(WEB, 'src/components/TaskLink.vue')]: join(TMP, 'stub-tasklink.mjs'),
    // PromiseTag is compiled for real (the card asks that it mark the seed rows),
    // so its target is the compiled scratch module, not a lookalike.
    [join(WEB, 'src/components/PromiseTag.vue')]: join(TMP, 'PromiseTag.mjs'),
  }
  const rewrite = (code) => code.replace(/(from\s+)(["'])([^"']+)\2/g, (all, pre, q, spec) => {
    if (spec === 'vue' || spec.startsWith('@vue/') || spec.startsWith('pinia')) return all
    // Relative specifiers resolve against the *source* file's directory, not the
    // scratch directory the generated module is written to -- and an extensionless
    // one (`../composables/useQueryFilters`) has to be found with the extension the
    // bundler would have found, or the real module loads and the stub the harness
    // meant to substitute is silently ignored.
    const abs = spec.startsWith('.') ? resolve(baseDir, spec) : spec
    const target = [abs, `${abs}.js`, `${abs}.vue`].map((key) => stubs[key]).find(Boolean) || abs
    return `${pre}${q}${pathToFileURL(target).href}${q}`
  })
  // PromiseTag is compiled for real: the card asks that it mark the seed rows,
  // so the mark has to be the component, not a lookalike.
  writeFileSync(join(TMP, 'PromiseTag.mjs'),
    rewrite(compileScript(parse(readFileSync(join(WEB, 'src/components/PromiseTag.vue'), 'utf8'),
      { filename: join(WEB, 'src/components/PromiseTag.vue') }).descriptor,
    { id: 'promisetag', inlineTemplate: true }).content))
  const compiled = compileScript(descriptor, { id: outPath, inlineTemplate: true })
  writeFileSync(outPath, rewrite(compiled.content))
  return outPath
}
writeFileSync(join(TMP, 'stub-filters.mjs'), `
import { reactive } from 'vue'
export const useQueryFilters = (defaults) => ({
  filters: reactive({ ...defaults }),
  activeCount: () => 0,
  clear: () => {},
})
`)
writeFileSync(join(TMP, 'stub-drawer.mjs'), `
export const listQuery = (key, value) => (value ? { [key]: value } : {})
`)
writeFileSync(join(TMP, 'stub-tasklink.mjs'), `
import { h } from 'vue'
export default { props: ['id'], setup: (p) => () => h('span', { class: 'aim-task-link' }, p.id) }
`)

/** The element-plus components the pane names, as pass-through stubs.
 *
 * `el-table-column` deliberately draws nothing: its scoped slot wants a `row`
 * element-plus would supply, and the columns are not what this task measures --
 * the sentence and the drift rows are. Stubbing a cell renderer would be a second
 * copy of the table, which is worse than not drawing one.
 */
const slotStub = (tag, slot) => ({
  setup: (props, { slots }) => () => h(tag, null, slots[slot] ? slots[slot]() : []),
})
const STUBS = {
  RouterLink: { props: ['to'], setup: (p, { slots }) => () => h('a', {}, slots.default ? slots.default() : []) },
  PromiseTag: null, // filled in per variant, from the real component
  'el-alert': slotStub('section', 'title'),
  'el-card': slotStub('div', 'default'),
  'el-table': slotStub('div', 'default'),
  'el-table-column': { setup: () => () => null },
  'el-progress': slotStub('div', 'default'),
  'el-collapse': slotStub('div', 'default'),
  'el-collapse-item': slotStub('div', 'default'),
  'el-select': slotStub('div', 'default'),
  'el-option': slotStub('div', 'default'),
  'el-input': slotStub('div', 'default'),
  'el-button': slotStub('div', 'default'),
}

async function render(variant, componentPath, sourceDir, state) {
  const modulePath = compile(componentPath, join(TMP, `${variant}.mjs`), sourceDir)
  const Pane = (await import(`${pathToFileURL(modulePath).href}?v=${variant}`)).default
  const PromiseTag = (await import(pathToFileURL(join(TMP, 'PromiseTag.mjs')).href)).default
  const pinia = createPinia()
  setActivePinia(pinia)
  const board = useBoard()
  board.doc = state
  board.viewer = state.viewer || 'human'
  const app = createSSRApp({ render: () => h(Pane) })
  app.use(pinia)
  for (const [name, stub] of Object.entries(STUBS)) app.component(name, name === 'PromiseTag' ? PromiseTag : stub)
  const html = await renderToString(app)
  if (process.stdout.isTTY === false) writeFileSync(join(TMP, `${variant}.html`), html)
  // The alert is the first `<section>` in the tree (the el-alert stub). Cutting
  // at `id="plan-drift"` instead would return an empty string for the committed
  // pane, which is exactly the version that has no such card -- the bug measured
  // as "(no alert rendered)" once already.
  const alert = (html.match(/<section[^>]*>([\s\S]*?)<\/section>/) || ['', '(no alert rendered)'])[1]
  const rows = html.match(/class="aim-attention-row"/g) || []
  return {
    // Tags out, entities back to text: this is the sentence the reader sees.
    sentence: alert.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim(),
    noteRows: (html.match(/not recorded<\/code>/g) || []).length,
    promiseRows: (html.match(/aim-chip seed aim-promise/g) || []).length,
    claimWords: {
      disagreements: (html.match(/disagreement\(s\)/g) || []).length,
      notInStoreYet: (html.match(/not in the store yet/g) || []).length,
      storeWins: (html.match(/the store wins/g) || []).length,
    },
    rows: rows.length,
    tail: (html.match(/show all \d+ \(\d+ more\)/) || ['(no expansion control)'])[0],
    detailRows: rows.length,
  }
}

const state = await (await fetch(`${BOARD}/api/state`)).json()
const drift = state.drift || []
const nullStore = drift.filter((row) => !row.store)
const tasks = Object.values(state.tasks || {})
const undated = tasks.filter((task) => !task.due)
const undatedSeeds = undated.filter((task) => String(task.provenance || '').includes('seed')).length

console.log('payload, live from', BOARD, '(generated_at', state.generated_at, ')')
console.log('  drift rows:', drift.length, '| store absent:', nullStore.length,
            '| store holds a differing value:', drift.length - nullStore.length)
console.log('  tasks without a due date:', undated.length, '| of which plan seeds:', undatedSeeds)
console.log('  provenance of the drift ids:',
  [...new Set(nullStore.map((row) => (state.tasks?.[row.id]?.provenance || 'not on the board')))].join(' | '))

/**
 * The live board cannot tell a correct split from a convenient one: every one of
 * its 87 store values is absent, so a pane that drew "not recorded" for *every*
 * row would pass here. This fixture is the discriminating one and it is the exact
 * fixture `web/tests/drift-claim.spec.js` asserts against -- 24 rows the store has
 * never seen, 2 where both sides hold a value and differ, and 11 undated items
 * split 7 seeds / 4 recorded. Every pair differs (24 vs 26, 24 vs 2, 7 vs 4) so a
 * count that reads the wrong list cannot pass by coincidence.
 */
// The coordinator's own T-0190 fixture (web/tests/card-t0190-plan-drift.spec.js,
// commit 1277f7e): 24 never-recorded rows, 3 where both sides hold a value. Copied
// here so the string half of their spec can be evaluated against this render before
// anyone runs Playwright -- their file cannot be imported (importing it calls
// `test.describe` outside a runner).
const mixed = {
  ...state,
  drift: [
    ...Array.from({ length: 24 }, (_, i) => ({
      id: `T-11${String(i).padStart(2, '0')}`, field: 'status',
      plan: ['backlog', 'ready', 'doing'][i % 3], store: null,
    })),
    { id: 'T-1201', field: 'status', plan: 'ready', store: 'doing' },
    { id: 'T-1202', field: 'owner', plan: 'codex', store: 'human' },
    { id: 'T-1203', field: 'due', plan: '2026-09-21', store: '2026-09-20' },
  ],
}
const NEVER = 24
const DIFFER = 3

for (const [name, data] of [['live payload', state], ['mixed fixture', mixed]]) {
  const recorded = (data.drift || []).filter((row) => !row.store).length
  const differing = (data.drift || []).filter((row) => row.store).length
  console.log(`\n--- ${name}: ${recorded} never recorded, ${differing} where both values exist ---`)
  for (const [label, path, dir] of [
    ['BEFORE (git HEAD)', join(TMP, 'before.vue'), join(WEB, 'src/panes')],
    ['AFTER (working tree)', join(WEB, 'src/panes/PlanPane.vue'), join(WEB, 'src/panes')],
  ]) {
    const out = await render(name.replace(/\W+/g, '-') + (label.startsWith('BEFORE') ? '-before' : '-after'),
                             path, dir, data)
    console.log(`  ${label}`)
    console.log('    sentence:', out.sentence)
    console.log('    rows drawn:', out.rows, '| "not recorded" cells:', out.noteRows,
                '| planned chips:', out.promiseRows)
    console.log('    words:', JSON.stringify(out.claimWords), '| expansion control:', out.tail)
  }
}

/**
 * The string assertions of the coordinator's spec, evaluated against this render.
 *
 * This is NOT a Playwright run and it is NOT their spec executed: it checks the
 * four assertions of theirs that are pure text (`toContain` / regex over the page
 * body and over the "differ" card) against the text this harness produced. The
 * DOM-shaped assertions of theirs -- row counts, the `drawn < 24` bound, the
 * `PromiseTag` class compared with the landing page's -- are not covered here.
 */
function preflight(label, { sentence, body, differText }) {
  const checks = [
    ['body contains "not recorded"', body.includes('not recorded')],
    [`body contains "${NEVER} plan item(s)"`, body.includes(`${NEVER} plan item(s)`)],
    ['body has no "disagreement(s)"', !/disagreement\(s\)/.test(body)],
    ['body has no "where the two disagree the store wins"', !/where the two disagree the store wins/.test(body)],
    [`body has no "${NEVER} ... store wins" (either order)`,
      !new RegExp(`\\b${NEVER}\\b[^.]{0,120}store wins`, 'i').test(body)
      && !new RegExp(`store wins[^.]{0,120}\\b${NEVER}\\b`, 'i').test(body)],
    [`body does not print the drift total (${NEVER + DIFFER}) as the absent count`,
      !body.includes(`${NEVER + DIFFER} plan item(s)`)],
    [`differ card states ${DIFFER}`, new RegExp(`\\b${DIFFER}\\b`).test(differText)],
    [`differ card does not state ${NEVER}`, !new RegExp(`\\b${NEVER}\\b`).test(differText)],
    ['differ card says "store wins"', /store wins/i.test(differText)],
    [`the remainder reads "${NEVER - 20} more"`, new RegExp(`\\b${NEVER - 20}\\b\\s*more`).test(body)],
  ]
  return checks.map(([what, ok]) => `    ${ok ? 'PASS' : 'FAIL'}  ${what}`)
}

const shrink = (html) => html.replace(/<[^>]+>/g, ' ').replace(/&#39;/g, "'").replace(/&quot;/g, '"')
  .replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim()
const afterMixed = await render('after-mixed', join(WEB, 'src/panes/PlanPane.vue'), join(WEB, 'src/panes'), mixed)
const html = readFileSync(join(TMP, 'after-mixed.html'), 'utf8')
const differHtml = html.slice(html.indexOf('id="plan-drift-differs"'))
console.log('\ncoordinator spec (card-t0190-plan-drift.spec.js) string checks, against the AFTER render:')
for (const line of preflight('mixed', {
  sentence: afterMixed.sentence, body: shrink(html), differText: shrink(differHtml),
})) console.log(line)
