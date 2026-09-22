<script setup>
/**
 * A work item's id, as a way into it.
 *
 * An id that is dead text is the failure this exists to stop: `T-0041` in a
 * report's blocker column looks exactly like something a person must deal with,
 * and gives them nothing to deal with it *with*. Every id the board draws should
 * be the same control, opening the same drawer, from wherever it appears.
 *
 * It asks on click rather than holding a task, so what opens is the board's
 * current state of that id. It falls back to a filtered list when the board does
 * not hold the id at all -- a blocker that is not in this view is still a fact
 * about the graph, and the reader should be able to go and look for it.
 */
import { computed, inject } from 'vue'
import { useBoard } from '../stores/board'
import { listQuery } from '../composables/useTaskDrawer'

const props = defineProps({
  id: { type: String, required: true },
  /** What to show. Defaults to the id itself. */
  label: { type: String, default: '' },
  /** The list to fall back to when the board does not hold this id. */
  fallback: { type: Object, default: () => ({ path: '/items', key: 'q' }) },
})

const board = useBoard()
const ctx = inject('ctx')
const drawer = ctx.service('taskDrawer')

/** A target that is on the board is a drawer; one that is not is a search. */
const known = computed(() => board.tasks.some((task) => task.id === props.id))
const destination = computed(() => ({
  path: props.fallback.path,
  query: listQuery(props.fallback.key || 'q', props.id),
}))

/**
 * Open this link's target, and say whether there was one.
 *
 * A row that is itself clickable cannot stop the click from reaching it -- the
 * table emits `row-click` for the whole row whatever the cell does -- so the row
 * handler has to know the click landed on a link and hand it back here instead of
 * opening the row. That is what this is for: one behaviour, one owner, and a
 * parent delegating to it rather than a second copy of "open the id".
 *
 * A missing id is deliberately *not* opened: its link navigates, which is the
 * sensible action it has, and a row that hijacked that navigation would be the
 * dead end the link exists to avoid.
 */
function open() {
  if (!known.value) return false
  return drawer.open(props.id, { tasks: board.tasks })
}

defineExpose({ open })
</script>

<template>
  <RouterLink v-if="!known" :to="destination" class="aim-task-link aim-task-link-missing"
              :title="`${id} is not in this view — search for it`">
    {{ label || id }}
  </RouterLink>
  <button v-else type="button" class="aim-task-link" :aria-label="`Open work item ${id}`"
          @click.stop="open()">
    {{ label || id }}
  </button>
</template>
