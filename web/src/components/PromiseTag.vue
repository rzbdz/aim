<script setup>
/**
 * The one mark that says "this is a promise, not work".
 *
 * The landing page draws two kinds of row in the same list and with the same
 * shape: an item someone recorded, and a line a plan file asserts. Only the
 * first can be acted on, and the reader had no way to tell them apart -- measured
 * live, every overdue, blocked and review row on the page was a static string in
 * `plan/plan.json`. A per-pane flourish would not fix that: two marks for one
 * concept is two answers, and the second one is the one that will be wrong. So
 * the mark is this component and nothing else draws it.
 *
 * `planned` rather than `seed`: the tool's word for a record is "provenance",
 * and the reader has never seen that either. The tooltip is the sentence that
 * makes the difference falsifiable -- a promise has no record to move.
 */
defineProps({
  /** The title attribute, for a surface whose row means something more specific. */
  title: { type: String, default: '' },
})
</script>

<template>
  <span class="aim-chip seed aim-promise" :title="title || 'Planned, not recorded: there is no work item here to move, so it is not counted as work.'">
    planned
  </span>
</template>
