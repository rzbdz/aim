<script setup>
import { computed } from 'vue'
import { useBoard } from '../stores/board'

const props = defineProps({ id: String, size: { type: Number, default: 20 }, showName: { type: Boolean, default: true } })
const board = useBoard()
const kind = computed(() => board.agents[props.id]?.kind || 'agent')
const model = computed(() => board.agents[props.id]?.model || '')
const initials = computed(() => (props.id || '?').replace(/[^a-z0-9]/gi, '').slice(0, 2).toUpperCase())
/** Colour by kind, so a glance tells a human from an agent from a stranger. */
const tint = computed(() => ({ human: '#38bdf8', codex: '#34d399', claude: '#a78bfa', claude_code: '#a78bfa' }[kind.value] || '#94a3b8'))
</script>

<template>
  <el-tooltip :content="model ? `${id} — ${kind} (${model})` : `${id} — ${kind}`" placement="top">
    <span class="aim-owner">
      <span class="aim-avatar" :style="{ width: size + 'px', height: size + 'px', fontSize: (size * 0.46) + 'px',
                                        background: `color-mix(in srgb, ${tint} 22%, transparent)`,
                                        border: `1px solid color-mix(in srgb, ${tint} 45%, transparent)`,
                                        color: tint }">{{ initials }}</span>
      <span v-if="showName">{{ id || 'unassigned' }}</span>
    </span>
  </el-tooltip>
</template>

<style scoped>
.aim-owner { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--aim-dim); }
.aim-avatar { display: inline-flex; align-items: center; justify-content: center; border-radius: 6px; font-weight: 600; letter-spacing: .02em; }
</style>
