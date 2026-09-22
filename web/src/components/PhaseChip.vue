<script setup>
/**
 * A phase, said in English, with the protocol value one hover away.
 *
 * The chip is the primary label everywhere a person reads a phase: the header,
 * the barrier tabs, the phase history and the refusal filter. The enum is not
 * hidden — it is in the tooltip, because it is the thing you quote in a bug
 * report and the thing `bin/aim` takes as an argument — but it is never the
 * first thing a reader has to understand.
 *
 * A chip that links is a chip with a destination: some surfaces want the reader
 * to be able to go and read what the phase *means*, and some (a table cell in a
 * history list) do not.
 */
import { computed } from 'vue'
import { phaseConcept, phaseAnchor } from '../concepts'

const props = defineProps({
  phase: { type: String, default: '' },
  link: { type: Boolean, default: false },
  size: { type: String, default: 'small' },
  effect: { type: String, default: 'plain' },
  type: { type: String, default: 'warning' },
  round: { type: Boolean, default: false },
})

const concept = computed(() => phaseConcept(props.phase))
const tooltip = computed(() => `${concept.value.key} — ${concept.value.summary}. ${concept.value.consequence}`)

/**
 * A tooltip around a link eats the link's keyboard activation.
 *
 * `el-tooltip`'s trigger listens for Enter, NumpadEnter and Space by default and
 * calls `preventDefault` on them, so a `<a>` inside one is focusable, announces
 * itself as a link, and then does nothing when you press the key a link is
 * supposed to answer to. A tooltip is not worth an inaccessible control, so when
 * the chip is a link the trigger keys are emptied and the tooltip opens on hover
 * and on focus only.
 */
const triggerKeys = computed(() => (props.link ? [] : undefined))

/** A phase this build cannot describe has no section to link to, and must not
 *  be given an anchor that does not exist: a link to nowhere is worse than no
 *  link, because the reader concludes the explanation is missing rather than
 *  that the *phase* is. */
const destination = computed(() => (concept.value.known
  ? { path: '/help', hash: `#${phaseAnchor(concept.value.key)}` }
  : { path: '/help' }))
</script>

<template>
  <el-tooltip :content="tooltip" placement="top" :show-after="200" :trigger-keys="triggerKeys">
    <RouterLink v-if="link" :to="destination" class="aim-phase-chip aim-phase-chip-link">
      <el-tag :size="size" :effect="effect" :type="type" :round="round">{{ concept.label }}</el-tag>
    </RouterLink>
    <el-tag v-else :size="size" :effect="effect" :type="type" :round="round">{{ concept.label }}</el-tag>
  </el-tooltip>
</template>
