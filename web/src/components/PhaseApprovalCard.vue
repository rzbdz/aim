<script setup>
import { computed, ref } from 'vue'
import { useBoard } from '../stores/board'

const props = defineProps({
  request: { type: Object, required: true },
  busy: { type: String, default: '' },
  error: { type: String, default: '' },
})
const emit = defineEmits(['approve', 'reject'])
const board = useBoard()
const rejectionReason = ref('')

const match = computed(() => /^request:\s*([A-Z_]+)\s*->\s*([A-Z_]+)$/
  .exec(props.request.subject || ''))
const fromPhase = computed(() => match.value?.[1] || props.request.phase || props.request.currentPhase)
const targetPhase = computed(() => match.value?.[2] || props.request.targetPhase)
const channel = computed(() =>
  (board.doc?.channels || []).find((item) => item.id === props.request.channel))
const participants = computed(() => channel.value?.participants || [])
const leader = computed(() => channel.value?.leader || board.writer || board.viewer)

function reject() {
  if (!rejectionReason.value.trim()) return
  emit('reject', props.request, rejectionReason.value.trim())
  rejectionReason.value = ''
}
</script>

<template>
  <article class="aim-phase-request">
    <header>
      <div>
        <strong>Phase request</strong>
        <p>{{ request.from }} asks {{ fromPhase }} → {{ targetPhase }}</p>
      </div>
      <el-tag type="warning" effect="plain" size="small">{{ request.channel }}</el-tag>
    </header>
    <el-descriptions :column="1" border size="small">
      <el-descriptions-item label="reason">{{ request.body || '—' }}</el-descriptions-item>
      <el-descriptions-item label="participants">
        {{ participants.length ? participants.join(', ') : '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="decision owner">{{ leader }}</el-descriptions-item>
    </el-descriptions>
    <el-input v-model="rejectionReason" type="textarea" :rows="2"
              placeholder="Reason if you decline this phase request" />
    <div class="aim-decision-actions">
      <el-button type="primary" :disabled="!board.canWrite"
                 :loading="busy === `advance:${request.channel}:${request.ts}`"
                 @click="emit('approve', request)">
        Approve advance
      </el-button>
      <el-button type="warning" :disabled="!board.canWrite || !rejectionReason.trim()"
                 :loading="busy === `reject:${request.channel}:${request.ts}`"
                 @click="reject">
        Decline with reason
      </el-button>
    </div>
    <el-alert v-if="!board.canWrite" type="info" :closable="false" show-icon
              title="Read-only dashboard" description="Restart with --allow-write to decide phases here." />
    <el-alert v-if="error" type="error" :closable="false" show-icon title="The tool refused this action">
      <pre class="aim-mono">{{ error }}</pre>
    </el-alert>
  </article>
</template>
