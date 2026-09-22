<script setup>
import { computed, inject, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import { PHASES, phaseConcept, phaseLabel } from '../concepts'
import PhaseChip from '../components/PhaseChip.vue'

const ctx = inject('ctx')
const board = useBoard()
const api = ctx.service('api')
const { filters, activeCount, clear } = useQueryFilters({
  channel: '', q: '', agent: '', refusalClass: '', phase: '',
})
const channels = computed(() => board.doc?.channels || [])
/**
 * The channel being drawn and the channel the URL names are the same channel.
 *
 * They were not, and the page said so out loud: with no `?channel=` the detail
 * panel fell back to the first channel, while every tab rendered unselected --
 * five channels, zero `is-active`, and `#barrier-v0`'s topic, phase and
 * participants on screen underneath. A tab strip that says "nothing is selected"
 * above a panel showing something is the reader being told two things at once,
 * and the one they will believe is the wrong one.
 *
 * So the fallback *is* the selection: the id that is drawn is written to the URL,
 * and the URL stays the source of truth for every other change.
 *
 * The strip is *bound*, not `v-model`ed. `v-model="shown"` was the second half of
 * this defect: `shown` is a computed, so the tab's `update:modelValue` assigned
 * to a readonly ref, the assignment was dropped, and in a production build Vue's
 * dev-time warning is stripped -- so `el-tabs` moved its own highlight and the
 * pane switched on screen while `filters.channel` and the URL did not move at
 * all. Measured: click `#hello` and `location.hash` still ended in
 * `channel=barrier-v0`, with the refusals table rendering nothing. The reader is
 * now the one who writes the selection, through the same `filters.channel` the
 * rest of the page reads.
 */
const shown = computed(() => {
  const ids = channels.value.map((c) => c.id)
  // A URL that names a channel this board does not hold is the zero-tab state
  // again: `el-tabs` has no pane to light, so every detail panel is hidden and
  // the reader sees the purpose line over nothing. The name has to be *in* the
  // list to be the selection; anything else falls back to the first channel, and
  // the watch below writes that back.
  return ids.includes(filters.channel) ? filters.channel : (ids[0] || '')
})
const current = computed(() => channels.value.find((c) => c.id === shown.value) || {})
watch(shown, (id) => {
  if (id && filters.channel !== id) filters.channel = id
}, { immediate: true })

/**
 * The move this channel is waiting on, named rather than inferred.
 *
 * `PHASES[].next` is the lifecycle's forward edge and not "the first edge in
 * `TRANSITIONS`" -- the two differ at CROSS_EXAMINE, where the machine also
 * offers a re-seal back to SYNTHESIS. The one the leader is *asked* for is the
 * forward one, so that is the one the page offers, and the argv below is built
 * from this function rather than typed twice: a control whose printed command is
 * not the command it posts is the defect, so both read `advanceArgv`.
 *
 * Null when the phase has no forward edge (CLOSED) or when the build cannot name
 * the phase at all (`phaseConcept` returns `next: null` for an unknown key).
 */
const nextPhase = (ch) => phaseConcept(ch?.phase).next || ''

/**
 * What crossing that edge changes, from the machine's own table.
 *
 * `unlocks` is the honest half of a phase move and it is why the barrier exists:
 * SYNTHESIS -> CROSS_EXAMINE is the edge that *ends independence*, and the three
 * before it change no permission at all. A leader deciding whether to press the
 * button should not have to read `concepts.js` to find that out.
 *
 * Only the *forward* edge is read. At CROSS_EXAMINE the machine also offers a
 * re-seal back to SYNTHESIS, and the map below holds both; the card draws the
 * one `nextPhase` names. Offering the re-seal here would mean deciding on the
 * leader's behalf that the round should be restarted, which is a different
 * decision from advancing it.
 */
function unlocks(ch) {
  const to = nextPhase(ch)
  const edge = PHASES.find((p) => p.key === ch?.phase)
  if (!to || !edge) return ''
  return TRANSITION_UNLOCKS[`${edge.key}->${to}`] || ''
}

/**
 * The argv the button runs, in the order `bin/aim advance --help` prints.
 *
 * `--as` is the channel's *leader*, because that is the identity the tool
 * requires (`require_leader`, `bin/aim:731`) and the one the page is showing the
 * control to. See `canAdvance`: the control is drawn only when that is also the
 * identity the server writes as, so the printed command and the posted command
 * are the same command and not two claims.
 */
function advanceArgv(ch) {
  const to = nextPhase(ch)
  if (!ch?.id || !to) return null
  return ['advance', '--as', ch.leader, '--channel', ch.id, '--to', to]
}
const advanceText = (ch) => {
  const argv = advanceArgv(ch)
  return argv ? `aim ${argv.join(' ')}` : ''
}

/**
 * Whose move this is, and whether this dashboard can make it.
 *
 * Three conditions, each of which alone has produced a control that lies:
 *
 *  * the *reading seat* is the channel's leader (`board.viewer`). Measured on
 *    the live board: it reads as `viewer: "claude-session1"` while it writes as
 *    `write.as: "human"`, so gating on the writer alone draws the leader's
 *    control for every participant who looks at the page;
 *  * the server was started with `--allow-write` (`board.canWrite`), because
 *    otherwise `POST /api/command` answers `rc 126` before a subprocess exists
 *    (`aimboard/cli.py:503`) and the button can only ever fail;
 *  * the server writes as the leader (`board.writer === ch.leader`), because the
 *    endpoint drops any `--as` in argv and appends its own (`aimboard/cli.py`
 *    `do_POST`), so a writer who is not the leader would run a *different*
 *    command from the one printed on the card.
 *
 * A leader who fails the second or third condition is not a non-leader and is
 * not shown nothing -- they are told the move is theirs and that this dashboard
 * cannot carry it. What is never drawn is a control.
 */
const isLeader = (ch) => Boolean(ch?.leader) && ch.leader === board.viewer
const canAdvance = (ch) => Boolean(advanceArgv(ch)) && isLeader(ch)
  && board.canWrite && board.writer === ch.leader

const busy = ref('')
const refusal = reactive({ channel: '', text: '' })

/**
 * The ask, for the seat the tool's own refusal names.
 *
 * `require_leader` refuses everyone but the leader and says the way round it --
 * "agents may ask with: aim request-advance ..." (`bin/aim:818-833`) -- so a page
 * that shows a participant whose move this is owes them that command rather than
 * a disabled button. It is the same act in the other direction, and it is
 * recorded in the channel's *public* log (`cmd_request_advance`, `bin/aim:1480`)
 * rather than in a private one, because a request is not a position.
 *
 * The two write conditions are `canAdvance`'s, for the same reason: the endpoint
 * drops any `--as` in argv and appends the server's own, so the argv has to be
 * postable *as this reader* or the printed command is not the command that runs.
 * When it is not -- a read-only server, or a writer who is somebody else -- this
 * renders nothing and the sentence below the branch says why, which is the
 * distinction the leader's own branch already keeps.
 */
const isParticipant = (ch) => (ch?.participants || []).includes(board.viewer)
const canRequest = (ch) => Boolean(advanceArgv(ch)) && !isLeader(ch)
  && isParticipant(ch) && board.canWrite && board.writer === board.viewer

/**
 * What the request says, defaulting to something the record can stand behind.
 *
 * `--reason` is `required=True` (`bin/aim:4419`) and its text is appended to the
 * channel log verbatim, so an empty box is not an option the command has. The
 * default names the phase rather than the enum: a reader of the log has the
 * english label beside every phase chip on the page, and the raw key in prose is
 * the thing `boards.spec.js:467` exists to keep off this pane.
 */
const requestNote = ref('')
const defaultReason = (ch) => `this channel is at ${phaseLabel(ch.phase)} and the next move is the leader's`
const requestReason = (ch) => requestNote.value.trim() || defaultReason(ch)

/**
 * The printed ask and the posted ask are one function, as on the leader's card.
 *
 * The reason is quoted with `JSON.stringify` rather than joined with spaces: an
 * unquoted sentence is a command that cannot be pasted into a shell, and a
 * printed command that differs from the posted one is the defect both of these
 * functions exist to prevent.
 */
function requestArgv(ch) {
  const to = nextPhase(ch)
  if (!ch?.id || !to || !board.viewer) return null
  return ['request-advance', '--as', board.viewer, '--channel', ch.id, '--to', to,
          '--reason', requestReason(ch)]
}
const requestText = (ch) => {
  const argv = requestArgv(ch)
  if (!argv) return ''
  return `aim request-advance --as ${board.viewer} --channel ${ch.id} --to ${nextPhase(ch)} `
    + `--reason ${JSON.stringify(requestReason(ch))}`
}

const requestBusy = ref('')
/** The same write path and the same verbatim-refusal rule as `advance`. */
async function requestAdvance(ch) {
  const argv = requestArgv(ch)
  if (!argv || !canRequest(ch)) return
  requestBusy.value = ch.id
  refusal.channel = ch.id
  refusal.text = ''
  const response = await api.command(argv)
  requestBusy.value = ''
  if (response.rc !== 0) {
    refusal.text = (response.stderr || response.stdout || `aim exited ${response.rc}`).trim()
    return
  }
  requestNote.value = ''
  await board.load()
}

/**
 * The page's purpose, in one sentence, above everything it shows.
 *
 * The measurement that put it here: `/#/barrier` held 5400px of content under
 * one heading, "Audit & barrier", and no sentence on it said what the page was
 * *for*. "Audit & barrier" is the pane's name, not its question; without this
 * line the reader is asked to infer the question from 10,235 characters of
 * answer. One sentence, one terminator, drawn above every card.
 */
const PURPOSE = 'This channel is at a phase, and only its leader may move it; '
  + 'everything below is the record of what happened under that phase.'

/**
 * The argv copied to the clipboard is the argv the button posts.
 *
 * `ItemsPane.copyCommand`'s idiom, and the same reason it exists there: this
 * dashboard does not write, it shows the command that does. The copy is a
 * convenience over `advanceText(ch)`, which is already on the card, so a refused
 * clipboard (`navigator.clipboard` is undefined off a secure origin) costs the
 * reader nothing and must not raise.
 */
async function copyAdvance(event, ch) {
  const command = advanceText(ch)
  const box = event?.currentTarget?.closest?.('.aim-leader-card')
  box?.querySelectorAll?.('input, textarea').forEach((field) => field.blur())
  await navigator.clipboard?.writeText(command).catch(() => {})
  ElMessage({ message: `copied: ${command}`, duration: 2000, customClass: 'aim-mono' })
}

/**
 * Run the move through the one write path (`api.command` -> `POST /api/command`).
 *
 * The dashboard does not advance a phase itself: it hands the argv to `bin/aim`
 * as the identity the server declares, so a refusal here is the tool's own text --
 * "cannot enter SYNTHESIS before every participant has sealed", say -- printed
 * verbatim rather than paraphrased, and recorded in the same ledger as a refusal
 * typed in a terminal.
 */
async function advance(ch) {
  const argv = advanceArgv(ch)
  if (!argv || !canAdvance(ch)) return
  busy.value = ch.id
  refusal.channel = ch.id
  refusal.text = ''
  const response = await api.command(argv)
  busy.value = ''
  if (response.rc !== 0) {
    refusal.text = (response.stderr || response.stdout || `aim exited ${response.rc}`).trim()
    return
  }
  refusal.text = ''
  await board.load()
}

/**
 * Which seal rows the reader has opened.
 *
 * Keyed by channel *and* agent: `el-tabs` keeps every pane in the DOM, and the
 * same agent seals in more than one channel (`claude-session1` seals in three
 * here), so an agent-keyed set would open a row in a pane the reader is not
 * looking at -- the same "three panes match the locator" shape the refusal
 * table's `:visible` scoping exists to correct.
 *
 * A `Set` of open keys rather than an `expanded` flag on the payload: the
 * payload is the server's, and mutating it would put reader state into the
 * record the page is auditing.
 */
const openSeals = reactive(new Set())
const sealKey = (ch, row) => `${ch.id}\u0000${row.agent}`
const sealOpen = (ch, row) => openSeals.has(sealKey(ch, row))
function toggleSeal(ch, row) {
  const key = sealKey(ch, row)
  if (openSeals.has(key)) openSeals.delete(key)
  else openSeals.add(key)
}

/**
 * The rows a refusal table draws, asked for a named channel rather than for "the
 * current one".
 *
 * The table is rendered inside `v-for="ch in channels"`, and it used to read the
 * filters against `current` -- the channel named by the URL. On load those are
 * the same channel, so the page looked right. After a tab click they are not, and
 * the sentence above the table printed a numerator from one channel over a
 * denominator from another: measured, "0 of 13 record(s)" over an empty table,
 * while 15 refusals sat one click away. A number and the list under it have to be
 * the same question asked once, so both are computed from the `ch` the table is
 * actually drawn in.
 */
function refusalsOf(channel) {
  return (channel?.refusals || []).filter((row) => {
    if (filters.q) {
      const needle = filters.q.toLowerCase()
      if (!`${row.agent} ${row.action} ${row.reason}`.toLowerCase().includes(needle)) return false
    }
    if (filters.agent && row.agent !== filters.agent) return false
    if (filters.refusalClass && row.class !== filters.refusalClass) return false
    if (filters.phase && row.phase !== filters.phase) return false
    return true
  })
}

function refusalAgentsOf(channel) {
  return [...new Set((channel?.refusals || []).map((row) => row.agent).filter(Boolean))].sort()
}
const chainRows = computed(() => Object.entries(current.value.chain || {})
  .map(([file, s]) => ({ file, ...s })))
</script>

<script>
/**
 * `unlocks` per lifecycle edge, read from `concepts.js` `TRANSITIONS` at module
 * load rather than re-typed here. A second copy of "what this move changes" is a
 * second answer to the question the leader is deciding with, and this project has
 * already measured what a second copy costs.
 */
import { TRANSITIONS } from '../concepts'
const TRANSITION_UNLOCKS = Object.fromEntries(
  TRANSITIONS.map((edge) => [`${edge.from}->${edge.to}`, edge.unlocks]),
)
export default { name: 'BarrierPane' }
</script>

<template>
  <el-tabs :model-value="shown" @update:model-value="(id) => { filters.channel = id }"
           v-if="channels.length">
    <el-tab-pane v-for="ch in channels" :key="ch.id" :name="ch.id"
                   :label="`#${ch.id} — ${phaseLabel(ch.phase)}`">
      <!-- The purpose line, above every card. It is drawn inside the pane and
           not above the tab strip because it is the *pane's* content: a reader
           measuring this page finds it under `.el-tab-pane:visible` with the
           cards, and putting it outside would leave the one sentence that says
           what the page is for outside the page the tests can see. -->
      <p class="aim-barrier-purpose aim-dim" style="margin:0 0 8px;font-size:11.5px;line-height:1.4">{{ PURPOSE }}</p>
      <!--
        The barrier card, first, because this page is about a phase and a phase is
        the one thing on it a person can move.

        It replaces the `el-descriptions` block that used to open the pane. Those
        twelve cells were a *report* -- topic, leader, round, participants, work
        items, refusals, concessions -- 166px of the reader's first screen spent
        on facts that are all one line each, and none of them an action. It also
        drops one line the old table had: "phase history — only the leader moves
        it", which was a statement of who *may* move the phase drawn *above*
        nothing that moves it. The claim did not go away, it changed tense: it is
        now either the argv below or the sentence that says whose move this is.
      -->
      <el-card shadow="never" class="aim-leader-card" body-style="padding:12px" style="margin-bottom:14px">
        <template #header>
          <div class="aim-leader-head">
            <span class="aim-leader-kind">the barrier</span>
            <span class="aim-leader-topic">{{ ch.topic || '(this channel records no topic)' }}</span>
          </div>
        </template>
        <div class="aim-leader-line"
             style="display:flex;align-items:center;gap:9px;flex-wrap:wrap">
          <PhaseChip :phase="ch.phase" effect="dark" link />
          <span class="aim-dim">{{ phaseConcept(ch.phase).summary }}</span>
          <span style="flex:1" />
          <span class="aim-dim aim-leader-facts" style="font-size:11.5px">
            leader {{ ch.leader }} · round {{ ch.round }} ·
            {{ (ch.participants || []).length }} participant(s) ·
            {{ ch.tasks_recorded }} work item(s) ·
            {{ (ch.refusals || []).length }} refusal(s) ·
            {{ ch.concessions }} concession(s)
          </span>
        </div>
        <div v-if="canAdvance(ch)" class="aim-leader-advance"
             style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:10px">
          <div class="aim-leader-next" style="font-size:12.5px">
            <span class="aim-dim">the move this phase opens: </span>
            <!--
              The label, not the enum. `boards.spec.js` asserts that no raw phase
              key is drawn as text inside `.aim-main` -- measured failing here the
              first time this was written, because `→ CROSS_EXAMINE` is a raw key
              with no tooltip behind it. The enum the tool needs is in the argv
              below, which is a command rather than a label, and the chip beside
              it carries the full value on hover.
            -->
            <b>→ {{ phaseLabel(nextPhase(ch)) }}</b>
            <span v-if="unlocks(ch)" class="aim-dim"> — {{ unlocks(ch) }}</span>
          </div>
          <span style="flex:1" />
          <!-- The command is on the card, not only in the click handler: a reader
               can read what the button will run, and a test can assert the whole
               argv rather than the presence of a button. -->
          <div class="aim-leader-argv aim-mono" style="word-break:break-word">{{ advanceText(ch) }}</div>
          <!-- The same string as a copy control, so a leader who would rather
               type the move into their own terminal can. It posts nothing. -->
          <el-button class="aim-advance-copy" size="small" text
                     @click="copyAdvance($event, ch)">copy</el-button>
          <el-button class="aim-advance" size="small" type="primary"
                     :loading="busy === ch.id" @click="advance(ch)">
            run it
          </el-button>
        </div>
        <!--
          A leader whose dashboard cannot carry the move is told so, in words and
          without an argv: printing a command the button cannot post would be the
          same lie in the other direction.
        -->
        <p v-else-if="isLeader(ch) && advanceArgv(ch)" class="aim-dim" style="font-size:12px;margin:0">
          this move is yours, and this dashboard cannot make it: it is read-only, or it writes as
          <span class="aim-mono">{{ board.writer || '(nobody)' }}</span> and the tool requires
          <span class="aim-mono">{{ ch.leader }}</span>.
        </p>
        <!--
          The other side of the same coin: a participant has no advance to run,
          but they do have an ask, and the tool's own refusal names it -- "agents
          may ask with: aim request-advance ..." (`bin/aim:818-833`). So this
          branch carries the ask and no argv that starts a phase move.

          It is deliberately NOT the leader's argv with a longer word: the printed
          command is `aim request-advance ...`, which reaches the same reader as
          a way round the gate without a button the tool would refuse. The
          `REQUEST-ADVANCE` chip is the visible half of that -- the same shape
          `barrier-leader.spec.js:302` measures on the leader's card, drawn for
          the seat that has no advance at all.
        -->
        <div v-else-if="canRequest(ch)" class="aim-leader-request"
             style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:10px">
          <el-tag class="aim-request-chip" size="small" type="warning" effect="plain">REQUEST-ADVANCE</el-tag>
          <el-input v-model="requestNote" class="aim-request-note" size="small"
                    :placeholder="defaultReason(ch)" clearable style="width:280px" />
          <span style="flex:1" />
          <div class="aim-leader-argv aim-mono" style="word-break:break-word">{{ requestText(ch) }}</div>
          <el-button class="aim-advance-copy" size="small" text
                     @click="copyAdvance($event, ch)">copy</el-button>
          <el-button class="aim-advance-request" size="small" type="primary"
                     :loading="requestBusy === ch.id" @click="requestAdvance(ch)">
            ask the leader
          </el-button>
        </div>
        <p v-else-if="isParticipant(ch) && advanceArgv(ch)" class="aim-dim" style="font-size:12px;margin:0">
          the next move is <span class="aim-mono">{{ ch.leader }}</span>'s, and this dashboard cannot
          even ask: it is read-only, or it writes as
          <span class="aim-mono">{{ board.writer || '(nobody)' }}</span> rather than as
          <span class="aim-mono">{{ board.viewer }}</span>.
        </p>
        <p v-else-if="!nextPhase(ch)" class="aim-dim" style="font-size:12px;margin:0">
          {{ phaseConcept(ch.phase).consequence }}
        </p>
        <el-alert v-if="refusal.channel === ch.id && refusal.text" type="error" :closable="false" show-icon
                  style="margin-top:8px" title="the tool refused this move">
          <pre class="aim-mono" style="white-space:pre-wrap;margin:0">{{ refusal.text }}</pre>
        </el-alert>
      </el-card>

      <!--
        Every section on this page answers "and if it is empty?" the same way:
        one line, and the line is the header's. Measured on the T-0192 fixtures
        (viewer `human`, 1440x1000), the empty sections stood at 84px (this one),
        111px (seals) and 84px (phase history) against the refusals card's 44px
        after the same treatment: an `el-card` renders a 20px-padded body around
        one sentence, and the sentence belongs beside the heading that names the
        thing it says is empty. The chain is the section a reader is most likely
        to meet empty, because a channel with no moves yet has no file to hash --
        and the caveat paragraph below goes with the body, because there is no
        chain to caveat when there is no chain.
      -->
      <el-card shadow="never" style="margin-bottom:14px"
               :body-style="chainRows.length ? '' : 'display:none'">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span>the chain — every file the record is made of</span>
            <span v-if="!chainRows.length" class="aim-dim" style="font-size:12px;font-weight:400">
              no file in this channel has a record yet — there is nothing to hash.
            </span>
          </div>
        </template>
        <el-table :data="chainRows" size="small">
          <el-table-column prop="file" label="file" width="200" />
          <el-table-column label="state" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="row.state === 'OK' ? 'success' : row.state === 'EMPTY' ? 'info' : 'danger'" effect="dark">{{ row.state }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="records" label="records" width="110" />
          <el-table-column prop="why" label="why" min-width="240" />
        </el-table>
        <p class="aim-dim" style="font-size:12px">
          A hash chain is not a signature: it proves the file was not edited without also editing every
          later line, and it says nothing about who wrote the first one.
        </p>
        <el-alert v-if="ch.tasks_unknown_events" type="warning" :closable="false" show-icon
                  style="margin-top:8px" title="the store holds events the fold could not place">
          {{ ch.tasks_unknown_events }} event(s) name a task whose creation is not in this store. They are not
          on the board: a `moved` for a card that was never created is either a foreign writer or a truncated
          file, and either way the board would be quietly wrong if this number were not here.
        </el-alert>
      </el-card>

      <!--
        One row per seal, and the claims behind an expansion.

        The claims used to be a table column printed in full. Measured on
        127.0.0.1:8777/#/barrier, viewer `human`, 1440x1000: this one card held
        3931px of the scroller's 5400px -- 73% of the page -- because
        `barrier-v0`'s two seals carry twelve claims between them, each rendered
        as a claim body plus a `confidence … would change my mind: …` line in a
        380px column. The table now carries one row per seal (agent, sealed,
        claims, at, digest) and the claims appear only when their row is opened,
        which is what a reader who wants the digest wants, in that order.
      -->
      <el-card shadow="never" style="margin-bottom:14px"
               :body-style="(ch.sealed || []).length ? '' : 'display:none'">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span>seals — a digest each participant committed to before reading the peer's</span>
            <!-- The reason, in place of the table: with nothing sealed there is no
                 digest to audit, and a header over an `el-table`'s "No Data" box
                 is chrome answering a question nobody asked. -->
            <span v-if="!(ch.sealed || []).length" class="aim-dim" style="font-size:12px;font-weight:400">
              nobody has sealed here yet — no position has been frozen, so there is no digest to audit.
            </span>
          </div>
        </template>
        <el-table :data="ch.sealed" size="small" class="aim-seal-table">
          <el-table-column prop="agent" label="agent" width="180" />
          <el-table-column label="sealed" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="row.sealed ? 'success' : 'warning'" effect="dark">{{ row.sealed ? 'yes' : 'not yet' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="claims" width="180">
            <template #default="{ row }">
              <el-button v-if="(row.claims || []).length" class="aim-seal-toggle" size="small" text type="primary"
                         :aria-expanded="String(sealOpen(ch, row))" @click="toggleSeal(ch, row)">
                {{ row.claims_count }} claim(s) {{ sealOpen(ch, row) ? '▾' : '▸' }}
              </el-button>
              <span v-else class="aim-dim">{{ row.claims_count }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="ts" label="at" width="200" />
          <el-table-column label="digest" min-width="200">
            <template #default="{ row }"><span class="aim-mono aim-dim">{{ (row.digest || '').slice(0, 24) }}…</span></template>
          </el-table-column>
          <!-- The claims stay a column, so the expansion opens the row it belongs
               to; a second table under the seal table would be a second thing to
               scroll and could not be `:visible`-scoped by row. -->
          <el-table-column label="" min-width="380">
            <template #default="{ row }">
              <template v-if="sealOpen(ch, row)">
                <el-tag v-if="row.withheld" type="info" size="small" effect="plain">withheld while the channel is sealed</el-tag>
                <div v-for="c in row.claims || []" :key="c.id" class="aim-claim" style="font-size:12px;margin-top:4px">
                  <b>{{ c.id }}</b> {{ c.claim }}
                  <div class="aim-dim">confidence {{ c.confidence }} · would change my mind: {{ c.kill_if }}</div>
                </div>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!--
        An empty section is one line, and that line is the header's.

        Measured on the T-0192 fixture (viewer `human`, 1440x1000), this card was
        123px with nothing in it: `.aim-filterbar` carries a 12px `margin-bottom`
        (`style.css:178`) that the header paid even with no filter drawn in it, and
        the body underneath spent its own 20px padding twice around one sentence.
        The 60px a reader should pay for a section with nothing in it is not
        reachable from inside a body -- an `el-card` renders `.el-card__body`
        whether or not there is anything to put in it -- so with nothing recorded
        the body is not drawn, and the reason moves up beside the count as the
        card's one line. That is also the honest shape: the controls are gone
        because there is nothing to filter, not hidden behind a click.
      -->
      <el-card shadow="never" style="margin-bottom:14px"
               :body-style="(ch.refusals || []).length ? '' : 'display:none'">
        <template #header>
          <div class="aim-filterbar" :style="(ch.refusals || []).length ? '' : 'margin-bottom:0'">
            <span>refusals — {{ refusalsOf(ch).length }} of {{ (ch.refusals || []).length }} record(s)</span>
            <!-- The reason, in place of the controls: with nothing recorded there
                 is nothing to filter, so the selects are not drawn at all. -->
            <span v-if="!(ch.refusals || []).length" class="aim-dim" style="font-weight:400">
              nothing has been refused in this channel — no one has yet wanted something the phase forbids.
            </span>
            <template v-if="(ch.refusals || []).length">
              <el-input v-model="filters.q" placeholder="search action or reason" clearable />
              <el-select v-model="filters.agent" placeholder="agent" clearable>
                <el-option v-for="agent in refusalAgentsOf(ch)" :key="agent" :value="agent" :label="agent" />
              </el-select>
              <el-select v-model="filters.refusalClass" placeholder="class" clearable>
                <el-option value="barrier" label="barrier" />
                <el-option value="form" label="form" />
              </el-select>
              <!-- The list is the dictionary's, not a copy: a filter that offers a
                   phase the tool cannot reach is a filter that can only return nothing. -->
              <el-select v-model="filters.phase" placeholder="phase" clearable>
                <el-option v-for="phase in PHASES" :key="phase.key" :value="phase.key"
                           :label="`${phase.label} (${phase.key})`" />
              </el-select>
              <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
            </template>
          </div>
        </template>
        <!--
          The empty branch moved into the header above, so the body holds only
          rows. What is left here is the other empty-ish case: a non-empty ledger
          that the reader's filters match none of.
        -->
        <p v-if="(ch.refusals || []).length && !refusalsOf(ch).length" class="aim-dim" style="font-size:12px;margin:0">
          no refusal matches these filters.
        </p>
        <el-table v-else :data="refusalsOf(ch)" size="small" class="aim-refusal-table">
          <el-table-column prop="ts" label="at" width="200" />
          <el-table-column prop="agent" label="agent" width="160" />
          <el-table-column prop="action" label="attempted" min-width="240" />
          <el-table-column prop="class" label="class" width="110">
            <template #default="{ row }"><el-tag size="small" type="danger" effect="plain">{{ row.class }}</el-tag></template>
          </el-table-column>
          <el-table-column label="phase" width="150">
            <template #default="{ row }">
              <el-tooltip :content="row.phase" placement="top" :show-after="200">
                <span>{{ phaseLabel(row.phase) }}</span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="reason" min-width="320" />
        </el-table>
      </el-card>

      <el-card shadow="never"
               :body-style="(ch.history || []).length ? '' : 'display:none'">
        <template #header>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span>phase history — every move, and who made it</span>
            <!-- The last section to keep this rule, and the one where the empty
                 case is not a fault: a channel that has never moved has no move
                 to record, which is why the phase it is sitting in is the whole
                 answer to "how did it get here". -->
            <span v-if="!(ch.history || []).length" class="aim-dim" style="font-size:12px;font-weight:400">
              this channel has not moved yet — the phase it is in now is the one it opened in.
            </span>
          </div>
        </template>
        <el-timeline>
          <el-timeline-item v-for="(h, i) in ch.history" :key="i" :timestamp="h.at" placement="top">
            <PhaseChip :phase="h.phase" effect="dark" link />
            <span class="aim-dim"> by {{ h.by }}{{ h.note ? ` — ${h.note}` : '' }}</span>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </el-tab-pane>
  </el-tabs>
  <el-empty v-else description="no channel to audit" />
</template>
