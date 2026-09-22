/**
 * One drawer, one place that opens it.
 *
 * Five panes each mounted their own `TaskDecisionDrawer` and each kept their own
 * `selected` ref. That is five answers to "which work item is open", and it shows
 * the moment a reader follows a link from one surface to another: the row they
 * clicked is not the thing that opens, because the pane they arrived in has never
 * heard of it.
 *
 * This is the same rule the server applies to writes, applied to the reader's
 * attention: one owner, declared once, everyone else asks it. The shell mounts
 * the drawer; a pane says what to open.
 *
 * `open()` resolves an id against the board *at the moment of opening*, so a
 * surface holding a stale copy of a task -- an older summary row, a blocker id
 * scraped out of a report -- opens the current state of that task rather than the
 * copy it happened to be holding.
 */
import { reactive } from 'vue'

export function createTaskDrawer() {
  const state = reactive({ open: false, id: '', task: null, history: [] })

  /**
   * Open a task by id, or by the task object a surface already has.
   *
   * Returns whether anything was found: a caller that offered a link for an id
   * the board does not hold needs to know, because a dead link is the thing this
   * whole task is about.
   */
  function open(taskOrId, { tasks = [], push = true } = {}) {
    const id = typeof taskOrId === 'string' ? taskOrId : taskOrId?.id
    if (!id) return false
    const task = tasks.find((item) => item.id === id)
      || (typeof taskOrId === 'object' ? taskOrId : null)
    if (!task) return false
    state.id = id
    state.task = task
    state.open = true
    // The history is a path, not a set: walking to the same item twice is two
    // steps, and a stack of *distinct* ids loses the step you would want to take
    // back to. Only a repeat of where you already are is not a step.
    if (push && state.history[state.history.length - 1] !== id) state.history.push(id)
    return true
  }

  /** Closing ends the path: reopening starts from wherever you reopen it. */
  function close() {
    state.open = false
    state.history.length = 0
  }

  /**
   * Where the reader was, so closing goes back one step rather than nowhere.
   *
   * A drawer opened from a report row, then from that task's blocker, then
   * closed, should put you back on the first task -- not on an empty page.
   */
  function back({ tasks = [] } = {}) {
    state.history.pop()
    const previous = state.history[state.history.length - 1]
    if (!previous) {
      state.open = false
      return false
    }
    return open(previous, { tasks, push: false })
  }

  return { state, open, close, back }
}

/** The URL a surface links to when it wants a list narrowed to one field. */
export const listQuery = (key, value) => (value ? { [key]: value } : {})
