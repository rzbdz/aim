import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * Record, at build time, what this bundle was built from.
 *
 * `design/12` §1.6: a measurement that cannot state which revision it measured
 * is not a measurement. This writes `dist/revision.json`; the server reads it and
 * compares it against the current source, so a page drawing code that no longer
 * exists says so instead of being probed as if it were current.
 *
 * The comparison is a *content* hash, not a revision string. `sha+dirty` was the
 * first attempt and it is useless in the only situation that matters: a tree
 * under development is dirty at build time and still dirty when the server
 * answers, so the two labels compare equal while the bytes differ.
 *
 * `sourceHash` is a byte-for-byte reimplementation of `aimboard/revision.py`'s
 * `source_hash` -- same inputs, same order, same separator. Two implementations
 * of one hash is a real cost and it is paid deliberately: the alternative is
 * asking the Python side to hash the tree at serve time and calling that "what
 * the build used", which is a claim about the tree, not about the bytes.
 */
const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..')

const git = (...args) => execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8' }).trim()
const dirt = () => {
  try { return git('status', '--porcelain', '--', 'bin', 'aimboard', 'web').length > 0 } catch { return true }
}
const revision = (() => {
  try { return git('rev-parse', '--short', 'HEAD') } catch { return 'unknown' }
})()
const revisionLabel = revision + (dirt() ? '+dirty' : '')

function walk(path) {
  const out = []
  const walkDir = (dir) => {
    for (const name of readdirSync(dir).sort()) {
      const full = join(dir, name)
      if (statSync(full).isDirectory()) walkDir(full)
      else out.push(full)
    }
  }
  if (statSync(path).isDirectory()) walkDir(path)
  else out.push(path)
  return out
}

/** Must equal aimboard/revision.py::source_hash over the same paths. */
function sourceHash(paths) {
  const h = createHash('sha256')
  for (const base of paths) {
    let files
    try { files = walk(base) } catch { continue }
    const root = statSync(base).isDirectory() ? base : dirname(base)
    // Python sorts the full paths; all of these share the base prefix, so sorting
    // by the relative name gives the same order.
    files.sort((a, b) => (relative(root, a) < relative(root, b) ? -1 : 1))
    for (const file of files) {
      h.update(relative(root, file).split(sep).join('/') + '\0')
      h.update(readFileSync(file))
      h.update('\0')
    }
  }
  return h.digest('hex')
}

const frontEndInputs = [join(here, 'src'), join(here, 'index.html'), join(here, 'vite.config.js')]

function revisionPlugin() {
  return {
    name: 'aim-revision',
    apply: 'build',
    closeBundle() {
      const files = frontEndInputs.filter((p) => { try { statSync(p); return true } catch { return false } })
      writeFileSync(join(here, 'dist', 'revision.json'), JSON.stringify({
        revision: revisionLabel, built_at: new Date().toISOString(), dirty: dirt(),
        source: 'vite build', source_paths: files.map((f) => relative(repo, f)),
        source_sha256: sourceHash(files),
      }, null, 1) + '\n')
    },
  }
}

// The dashboard is served by `aimboard serve` from `web/dist`, next to the JSON
// API that feeds it. `base: './'` keeps the built assets path-relative so the
// same bundle works from `/` and from a sub-path.
export default defineConfig({
  plugins: [vue(), revisionPlugin()],
  define: { __AIM_REVISION__: JSON.stringify(revisionLabel) },
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // a function, not a map: the bundler in use here wants to see the id
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('echarts') || id.includes('zrender')) return 'charts'
          if (id.includes('element-plus')) return 'element'
          if (id.includes('/vue') || id.includes('pinia') || id.includes('vue-router')) return 'vendor'
          return undefined
        },
      },
    },
  },
  server: {
    proxy: {
      // `npm run dev` against a running `aimboard serve`, so the front-end can be
      // edited with hot reload without teaching it a second way to read the fabric.
      '/api': { target: 'http://127.0.0.1:8777', changeOrigin: true },
    },
  },
})
