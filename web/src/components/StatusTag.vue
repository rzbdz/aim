<script setup>
import { color } from '../theme'
defineProps({ status: String, count: Number })
</script>

<template>
  <span class="aim-status">
    <span class="aim-dot" :style="{ background: color(status) }" />
    <span>{{ status }}</span>
    <span v-if="count !== undefined" class="aim-count">{{ count }}</span>
  </span>
</template>

<style scoped>
.aim-status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; letter-spacing: .01em; }
.aim-dot { width: 7px; height: 7px; border-radius: 50%; flex: 0 0 auto; box-shadow: 0 0 0 3px rgb(var(--aim-muted-rgb) / .09); }
.aim-count { color: var(--aim-dim); font-variant-numeric: tabular-nums; }
</style>
