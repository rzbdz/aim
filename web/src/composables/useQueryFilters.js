import { reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * Filters that live in the URL.
 *
 * The URL is the source of truth, and the filters follow it -- but the filters
 * also write back to it, so the two are in a loop and the loop has to know which
 * of them moved. The rule is one comparison: if the URL already says what the
 * filters say, the change was our own write coming back and there is nothing to
 * do; otherwise the URL is the source and the filters adopt it *whole*.
 *
 * Adopting it whole is the part that is easy to get wrong. A reader who goes from
 * `?owner=codex` to `?milestone=M2` means a different filter, not one more of
 * them; a reader that only ever sets the keys the URL happens to mention keeps
 * every filter the last route left behind, and the board silently narrows to a
 * query nobody asked for.
 */
const same = (a, b) => (Array.isArray(a) || Array.isArray(b)
  ? JSON.stringify([a].flat().filter(Boolean)) === JSON.stringify([b].flat().filter(Boolean))
  : a === b)

export function useQueryFilters(defaults) {
  const route = useRoute()
  const router = useRouter()
  const routeName = route.name
  const filters = reactive({ ...defaults })
  const isMulti = (key) => Array.isArray(defaults[key])

  /** What the URL says, as a complete set of filters. Absent keys are defaults. */
  const fromQuery = () => {
    const next = {}
    for (const key of Object.keys(defaults)) {
      const value = route.query[key]
      next[key] = value === undefined
        ? defaults[key]
        : isMulti(key)
          ? [value].flat().filter(Boolean)
          : typeof defaults[key] === 'boolean'
            ? value === '1'
            : String(value)
    }
    return next
  }

  watch(filters, () => {
    const query = { ...route.query }
    for (const [key, value] of Object.entries(filters)) {
      const empty = value === '' || value === 'all' || value === false
        || (Array.isArray(value) && !value.length)
      if (empty) delete query[key]
      else query[key] = typeof value === 'boolean' ? '1' : value
    }
    router.replace({ query })
  }, { deep: true })

  watch(() => route.query, () => {
    if (route.name !== routeName) return
    const next = fromQuery()
    if (Object.keys(next).every((key) => same(filters[key], next[key]))) return
    Object.assign(filters, next)
  }, { immediate: true })

  const active = (value) => value !== '' && value !== false && value !== 'all'
    && !(Array.isArray(value) && !value.length)
  const activeCount = () => Object.entries(filters)
    .filter(([key, value]) => key !== 'thread' && active(value))
    .length
  const clear = () => {
    for (const key of Object.keys(defaults)) {
      filters[key] = defaults[key]
    }
  }

  return { filters, activeCount, clear }
}
