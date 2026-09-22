<script setup>
/**
 * T-0231: the three org questions for one named agent, answered from the record.
 *
 * (1) the orgs it belongs to and the other members, (2) who it may dispatch work
 * to, (3) who it reports to. Each is answered from a key on the payload this
 * page is already reading, and each answer says which key it came from, because
 * the failure this pane exists to catch is a hierarchy or a roster that no one
 * recorded. Nothing here is derived from a second source:
 *
 *   - the roster is `channels[].participants` (`aimboard/api.py:501` ->
 *     `channel_payload`, `aimboard/api.py:358`), which the server reads out of
 *     `channels/<id>/manifest.json` (`aimboard/fabric.py:261`) -- the same
 *     manifest `aim status --channel` prints participants from
 *     (`bin/aim:3783-3784`). There is no second roster on this page to drift.
 *   - the dispatch edges are the *intersection* of those participant lists. The
 *     fabric has no authority graph and no delegation tree: a peer is someone
 *     you share a channel with.
 *   - reporting is not answered, and the pane says so with its reason. See
 *     `REPORTING` below.
 */
import { computed, watch } from 'vue'
import { useBoard } from '../stores/board'
import { useQueryFilters } from '../composables/useQueryFilters'
import OwnerAvatar from '../components/OwnerAvatar.vue'
import PhaseChip from '../components/PhaseChip.vue'

const board = useBoard()
const { filters, activeCount, clear } = useQueryFilters({
  agent: '', q: '', unplaced: false,
})

/**
 * Why question (3) is answered "not recorded" rather than guessed at.
 *
 * Evidence read, all of it a shape rather than a sentence:
 *   - `registry.json` is written by `cmd_register` (`bin/aim:977-983`) and holds
 *     `id, kind, model, session, registered_at` plus an optional
 *     `registration_events` list. No edge points at another agent.
 *   - `channels/<id>/manifest.json` is written by `cmd_new_channel`
 *     (`bin/aim:1015-1022`) and holds `id, topic, created_at, leader,
 *     synthesizer, participants, barrier`. `leader` and `synthesizer` are roles
 *     *in that channel*, not an agent-level reporting line, which is why the
 *     pane draws them as roles and labels them as roles.
 *   - the payload republishes the registry as `{kind, model}` only
 *     (`aimboard/api.py:529-530`), so even the session string is not on the wire.
 *   - `grep -rn 'reports_to\|reporting' bin/ aimboard/` finds no such key, and
 *     `aim --help` lists no org-shaped verb.
 *
 * The tempting inference -- "the channel's leader is who it reports to" -- is
 * refused on purpose. `leader` is a per-channel role and `require_leader`
 * (`bin/aim:818-819`) is a gate on *one* verb family (phase transitions and
 * membership), not a claim about who an agent answers to; an agent in three
 * channels would have three different "bosses" under that reading, and an agent
 * in no channel would have none. A surface that printed one of them as the
 * reporting line would be inventing the hierarchy the card's acceptance allows
 * it to call undefined.
 */
const REPORTING = {
  status: 'not recorded',
  because: 'no registry field, manifest field or ledger event names another agent as the one this one reports to',
  recorded: 'the roles the record does carry are per channel: `leader` and `synthesizer` (see the roster below) — they are roles in a channel, not a line between two agents',
}

/* ---------------------------------------------------------------------------
 * The payload, indexed once.
 * ------------------------------------------------------------------------- */

const channels = computed(() => board.channels || [])
const agents = computed(() => board.agents || {})

/** Registration order is the only order the fabric itself has. */
const ids = computed(() => Object.keys(agents.value).sort())

/**
 * The conversation gate's view of the same channels.
 *
 * `conversation.channels[]` is built by `gate.conversation_view` over
 * `state["channels"]` (`aimboard/gate.py:163-174`) -- the same list the roster
 * comes from -- and its `rule` sentence is the server's own statement of what
 * this seat may read. It is read here for one purpose: to compare it against the
 * roster and show a disagreement rather than pick a side. Today the two cannot
 * disagree on membership, because the gate ships `gated` and a rule sentence and
 * no participant names at all; that is a fact about the payload, and it is
 * reported as such below rather than assumed.
 */
const gate = computed(() => Object.fromEntries(
  (board.conversation.channels || []).map((ch) => [ch.id, ch])))

/**
 * Channels whose two views of the same object do not line up.
 *
 * Two comparisons, both inside the payload. The phase is published twice (roster
 * `phase`, gate `phase`) so a disagreement is checkable; membership is published
 * by the roster only, so a channel the gate does not mention is the one signal
 * available -- and a missing channel is exactly what "the gate does not see this
 * org" would look like.
 */
const disagreements = computed(() => {
  const rows = []
  for (const ch of channels.value) {
    const g = gate.value[ch.id]
    if (!g) {
      rows.push({ id: ch.id, what: 'in the roster, absent from the conversation gate', roster: ch.phase, gate: '(absent)' })
      continue
    }
    if (g.phase !== ch.phase) {
      rows.push({ id: ch.id, what: 'the phase differs between the roster and the gate', roster: ch.phase, gate: g.phase })
    }
  }
  return rows
})

/** Participants of a channel that the registry does not hold, by channel. */
const unregistered = computed(() => {
  const rows = []
  for (const ch of channels.value) {
    for (const who of ch.participants || []) {
      if (!agents.value[who]) rows.push({ channel: ch.id, agent: who })
    }
  }
  return rows
})

/** The channels each agent is a participant of, in roster order. */
const member = computed(() => {
  const out = Object.fromEntries(ids.value.map((id) => [id, []]))
  for (const ch of channels.value) {
    for (const who of ch.participants || []) (out[who] ||= []).push(ch.id)
  }
  return out
})

const byRole = (field) => computed(() => {
  const out = Object.fromEntries(ids.value.map((id) => [id, []]))
  for (const ch of channels.value) {
    const who = ch[field]
    // `leader` is a required field of a channel and `synthesizer` is optional
    // and empty when unset (`bin/aim:1020`), so the empty string is the absence
    // of the role and not a seat called "".
    if (who) (out[who] ||= []).push(ch.id)
  }
  return out
})
const leads = byRole('leader')
const synthesises = byRole('synthesizer')

/**
 * The other participants of the channels this agent is in -- the dispatch set.
 *
 * This is the whole of the fabric's authority. `aim push` refuses a sender who
 * is not a participant of the channel it names (`bin/aim:3191`), and two agents
 * therefore have a channel to talk in exactly when they share one:
 * `hello` holds `claude-session1, codex, codex-orangement`, so all three may
 * push to each other and none of them to `claude-session2`, who shares no
 * channel with them. Membership is leader-only and recorded
 * (`channel_member_added`, `bin/aim:702-707`), which is why this is derived
 * rather than asked for.
 */
const peers = computed(() => {
  const out = {}
  for (const id of ids.value) {
    const set = new Set()
    for (const ch of channels.value) {
      const people = ch.participants || []
      if (people.includes(id)) for (const who of people) if (who !== id) set.add(who)
    }
    out[id] = [...set].sort()
  }
  return out
})

/**
 * Registered agents this one shares no channel with.
 *
 * Named rather than left implicit: "nobody told me who I cannot reach" is the
 * question a new seat actually has, and the count of unreachable agents is the
 * one figure that makes being unplaced legible.
 */
const strangers = computed(() => {
  const out = {}
  for (const id of ids.value) {
    const mine = new Set(peers.value[id] || [])
    out[id] = ids.value.filter((other) => other !== id && !mine.has(other))
  }
  return out
})

/**
 * In no channel, by any relation the record holds.
 *
 * A participant list is the only membership there is, so an agent named in no
 * `participants` array is in no org -- and that is a state a new seat lands in,
 * so it is drawn as a state and not as a blank cell. A leader or a synthesizer
 * is *not* thereby a member: the `hello` leader is in no participant list, and
 * collapsing the two is how a role gets read as a rank, so the roles are counted
 * beside this flag rather than folded into it.
 */
const unplaced = (row) => row.channels.length === 0

const rows = computed(() => {
  const needle = filters.q.trim().toLowerCase()
  return ids.value
    .map((id) => ({
      id,
      kind: agents.value[id]?.kind || '',
      model: agents.value[id]?.model || '',
      channels: member.value[id] || [],
      leads: leads.value[id] || [],
      synthesises: synthesises.value[id] || [],
      peers: peers.value[id] || [],
      strangers: strangers.value[id] || [],
    }))
    .filter((row) => {
      if (filters.unplaced && row.channels.length) return false
      if (!needle) return true
      return `${row.id} ${row.kind} ${row.model} ${row.channels.join(' ')} ${row.peers.join(' ')}`
        .toLowerCase().includes(needle)
    })
})

/* ---------------------------------------------------------------------------
 * The three answers, for the agent being asked about.
 * ------------------------------------------------------------------------- */

/**
 * The agent the page is about, and the URL is where that lives.
 *
 * The same shape BarrierPane's channel tab uses: a name the board does not hold
 * is not a selection (`?agent=nobody` would otherwise draw an answer about a
 * seat that does not exist), so it falls back and the fallback is written back.
 * The default is the reading seat itself -- whose view this is, is on the
 * header -- because the question "what is my org" is the one a new session asks.
 */
const selected = computed(() => {
  if (ids.value.includes(filters.agent)) return filters.agent
  if (ids.value.includes(board.viewer)) return board.viewer
  return ids.value[0] || ''
})

/**
 * The fallback is the selection, so it is written to the URL.
 *
 * Without this the page drew an answer while `?agent=` named nothing, which is
 * the BarrierPane defect at one remove: the panel shows one agent, the URL
 * names none, and a reader who copies the address bar gets the default again
 * rather than what they were reading. Guarded on `ids` being loaded -- at first
 * paint every agent list is empty, and writing `agent=` then would put an empty
 * name in the URL for the one render before the state arrives.
 */
watch(selected, (id) => {
  if (id && filters.agent !== id) filters.agent = id
}, { immediate: true })

const answer = computed(() => {
  const id = selected.value
  if (!id) return null
  const orgs = channels.value.filter((ch) => (ch.participants || []).includes(id))
  return {
    id,
    orgs: orgs.map((ch) => ({
      id: ch.id,
      phase: ch.phase,
      others: (ch.participants || []).filter((who) => who !== id),
    })),
    roles: [
      ...(leads.value[id] || []).map((ch) => ({ role: 'leader', channel: ch })),
      ...(synthesises.value[id] || []).map((ch) => ({ role: 'synthesizer', channel: ch })),
    ],
    peers: peers.value[id] || [],
    strangers: strangers.value[id] || [],
  }
})

/**
 * Why the dispatch answer is drawn beside a measured counter-example.
 *
 * Sharing a channel is necessary to *push* and to *speak* (`bin/aim:3191`,
 * `bin/aim:1100`), and it is not what bounds who work can be handed to: measured
 * in a scratch root, `alpha` (a participant of `team`) ran
 * `aim task assign --owner gamma` for a `gamma` who was registered and in no
 * channel, rc 0, and `gamma` then read the card and moved it
 * (`bin/aim:2135-2136` checks that the owner is *registered*, not that it is a
 * participant). Drawing only the channel intersection and calling it "who you
 * may dispatch to" would therefore understate the fabric by exactly the edge
 * that a new seat arrives on -- and the card this pane answers was filed for a
 * newly registered agent.
 */
const DISPATCH_CAVEAT = 'a card can also be handed to any *registered* agent, participant or not: `aim task assign --owner <id>` refuses only an unregistered owner (measured: a registered agent in no channel was assigned a card by a participant, rc 0, and could then move it)'
</script>

<template>
  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>
      <div class="aim-filterbar">
        <span>one agent, the three questions</span>
        <el-select v-model="filters.agent" placeholder="agent" data-filter="agent">
          <el-option v-for="id in ids" :key="id" :value="id" :label="id" />
        </el-select>
        <el-input v-model="filters.q" placeholder="search id, kind, channel" clearable />
        <el-checkbox v-model="filters.unplaced" data-filter="unplaced">only agents in no channel</el-checkbox>
        <el-button v-if="activeCount()" size="small" text @click="clear()">clear</el-button>
        <span class="aim-filter-count">{{ rows.length }} of {{ ids.length }} agent(s)</span>
      </div>
    </template>

    <el-empty v-if="!answer" description="no registered agent to ask about" />
    <template v-else>
      <div class="aim-org-answers">
        <div class="aim-org-q">
          <p class="aim-dim">(1) the org it belongs to, and the other members</p>
          <template v-if="answer.orgs.length">
            <p v-for="org in answer.orgs" :key="org.id">
              <RouterLink :to="{ path: '/barrier', query: { channel: org.id } }" class="aim-task-link">#{{ org.id }}</RouterLink>
              <PhaseChip :phase="org.phase" link size="small" />
              <span>with
                <template v-if="org.others.length">
                  <RouterLink v-for="who in org.others" :key="who"
                              :to="{ path: '/org', query: { agent: who } }" class="aim-task-link">{{ who }}</RouterLink>
                </template>
                <span v-else class="aim-dim">nobody else — the only participant</span>
              </span>
            </p>
          </template>
          <p v-else class="aim-dim">
            in no channel. It is a participant of none, which is a state and not an omission:
            a channel's `participants` is the only membership the fabric records, and this id is
            in no list.
          </p>
          <p v-if="answer.roles.length" class="aim-dim" style="font-size:11.5px">
            roles held, which are not memberships:
            <span v-for="r in answer.roles" :key="r.role + r.channel" class="aim-role">{{ r.role }} of #{{ r.channel }}</span>
          </p>
        </div>

        <div class="aim-org-q">
          <p class="aim-dim">(2) who it may dispatch to</p>
          <p v-if="answer.peers.length">
            <RouterLink v-for="who in answer.peers" :key="who"
                        :to="{ path: '/org', query: { agent: who } }" class="aim-task-link">{{ who }}</RouterLink>
            <span class="aim-dim"> — the other participants of the channel(s) above</span>
          </p>
          <p v-else class="aim-dim">
            nobody, by channel membership: it shares no channel with another agent, and a push or a
            message into a channel is refused for a non-participant.
          </p>
          <p v-if="answer.strangers.length" class="aim-dim" style="font-size:11.5px">
            shares no channel with: {{ answer.strangers.join(', ') }}
          </p>
          <p class="aim-dim" style="font-size:11.5px">{{ DISPATCH_CAVEAT }}</p>
        </div>

        <div class="aim-org-q">
          <p class="aim-dim">(3) who it reports to</p>
          <p data-not-recorded="reporting">
            <el-tag size="small" type="info" effect="plain">{{ REPORTING.status }}</el-tag>
            <span class="aim-dim">because {{ REPORTING.because }}</span>
          </p>
          <p class="aim-dim" style="font-size:11.5px">
            what the record does carry: {{ REPORTING.recorded }}
          </p>
        </div>
      </div>
    </template>
  </el-card>

  <el-alert v-if="disagreements.length" type="warning" :closable="false" show-icon style="margin-bottom:14px"
            title="the roster and the conversation gate disagree about the same channels">
    <p v-for="row in disagreements" :key="row.id" style="margin:2px 0">
      #{{ row.id }} — {{ row.what }} (roster {{ row.roster }}, gate {{ row.gate }})
    </p>
  </el-alert>

  <el-alert v-if="unregistered.length" type="error" :closable="false" show-icon style="margin-bottom:14px"
            title="a channel names a participant the registry does not hold">
    <p v-for="row in unregistered" :key="row.channel + row.agent" style="margin:2px 0">
      #{{ row.channel }} lists '{{ row.agent }}', which is not a registered agent
    </p>
  </el-alert>

  <el-card shadow="never" style="margin-bottom:14px">
    <template #header>
      <div class="aim-filterbar">
        <span>the roster — every registered agent, and where it sits</span>
      </div>
    </template>

    <!-- The card's anti-drift clause, stated once, with the key it came from. -->
    <p class="aim-dim" style="font-size:12px; margin:0 0 10px">
      Read from <code>channels[].participants</code> in <code>/api/state</code> — the same object
      <code>aim status --channel</code> prints participants from (<code>bin/aim:3783</code>), which the
      server builds from <code>channels/&lt;id&gt;/manifest.json</code> (<code>aimboard/fabric.py:261</code>).
      This is not a second roster: a member this table does not show is a member the tool does not have.
      Cross-checked against the conversation gate's own view (<code>channels[].gated</code> and its rule
      sentence, <code>aimboard/gate.py:174</code>): <strong>{{ channels.length }}</strong> channel(s)
      compared, <strong>{{ disagreements.length }}</strong> disagreement(s)
      <template v-if="!disagreements.length">
        — the gate publishes no participant names at all, so membership can currently only disagree by a
        channel the gate omits, and it omits none.
      </template>
    </p>

    <el-table :data="rows" size="small" max-height="60vh">
      <el-table-column label="agent" width="180">
        <template #default="{ row }">
          <RouterLink :to="{ path: '/org', query: { agent: row.id } }" class="aim-task-link">
            <OwnerAvatar :id="row.id" />
          </RouterLink>
        </template>
      </el-table-column>
      <el-table-column label="kind" width="110">
        <template #default="{ row }"><span class="aim-dim">{{ row.kind || '—' }}</span></template>
      </el-table-column>
      <el-table-column label="model" width="120">
        <template #default="{ row }"><span class="aim-dim">{{ row.model || '—' }}</span></template>
      </el-table-column>
      <el-table-column label="channels" min-width="220">
        <template #default="{ row }">
          <template v-if="row.channels.length">
            <RouterLink v-for="ch in row.channels" :key="ch" :to="{ path: '/barrier', query: { channel: ch } }"
                        class="aim-task-link" style="margin-right:8px">#{{ ch }}</RouterLink>
          </template>
          <span v-else-if="unplaced(row)" class="aim-dim" data-unplaced="1">in no channel</span>
        </template>
      </el-table-column>
      <el-table-column label="role in channel" min-width="200">
        <template #default="{ row }">
          <span v-if="!row.leads.length && !row.synthesises.length" class="aim-dim">—</span>
          <span v-for="ch in row.leads" :key="'l' + ch" class="aim-dim" style="margin-right:8px">
            leader of #{{ ch }}
          </span>
          <span v-for="ch in row.synthesises" :key="'s' + ch" class="aim-dim" style="margin-right:8px">
            synthesizer of #{{ ch }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="may dispatch to" min-width="200">
        <template #default="{ row }">
          <span v-if="row.peers.length">{{ row.peers.join(', ') }}</span>
          <span v-else class="aim-dim" data-zero="1">nobody — shares no channel</span>
        </template>
      </el-table-column>
      <!-- The same answer in every row, and that is the finding rather than a
           rendering shortcut: the fabric records no such edge for anybody. -->
      <el-table-column label="reports to" width="140">
        <template #default>
          <span class="aim-dim" data-not-recorded="1">{{ REPORTING.status }}</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card shadow="never">
    <template #header>
      <div class="aim-filterbar">
        <span>per channel — the members, the roles, and what the gate serves this seat</span>
      </div>
    </template>
    <el-table :data="channels" size="small" max-height="60vh" row-key="id">
      <el-table-column label="channel" width="170">
        <template #default="{ row }">
          <RouterLink :to="{ path: '/barrier', query: { channel: row.id } }" class="aim-task-link">#{{ row.id }}</RouterLink>
        </template>
      </el-table-column>
      <el-table-column label="phase" width="130">
        <template #default="{ row }"><PhaseChip :phase="row.phase" link size="small" /></template>
      </el-table-column>
      <el-table-column label="leader (role, not a reporting line)" width="220">
        <template #default="{ row }">
          <OwnerAvatar v-if="row.leader" :id="row.leader" />
          <span v-else class="aim-dim">—</span>
        </template>
      </el-table-column>
      <el-table-column label="synthesizer (role)" width="180">
        <template #default="{ row }">
          <OwnerAvatar v-if="row.synthesizer" :id="row.synthesizer" />
          <span v-else class="aim-dim" data-zero="1">unset</span>
        </template>
      </el-table-column>
      <el-table-column label="participants (members)" min-width="260">
        <template #default="{ row }">
          <span v-for="who in row.participants" :key="who" style="margin-right:10px">
            <RouterLink :to="{ path: '/org', query: { agent: who } }" class="aim-task-link">{{ who }}</RouterLink>
          </span>
          <span v-if="!(row.participants || []).length" class="aim-dim" data-zero="1">no participants</span>
        </template>
      </el-table-column>
      <el-table-column label="gate" min-width="260">
        <template #default="{ row }">
          <el-tag size="small" :type="gate[row.id]?.gated ? 'warning' : 'success'" effect="plain">
            {{ gate[row.id]?.gated ? 'sealed to this seat' : 'open to this seat' }}
          </el-tag>
          <span class="aim-dim" style="font-size:11.5px">{{ gate[row.id]?.rule || '' }}</span>
        </template>
      </el-table-column>
    </el-table>
    <p class="aim-dim" style="font-size:12px; margin:8px 0 0">
      The gate column is the server's own sentence about this reading seat, taken verbatim from
      <code>conversation.channels[].rule</code>; it says what this seat may read, not who is a member.
      A phase says nothing about who may dispatch: the first three phases carry identical rules.
    </p>
  </el-card>
</template>

<style scoped>
/* Three answers side by side where there is room, stacked where there is not:
   the pane is read at 390px as well as on a desktop, and a row of three
   fixed-width columns is a horizontal scroller at phone width. */
.aim-org-answers { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
.aim-org-q { display: flex; flex-direction: column; gap: 6px; }
.aim-org-q p { margin: 0; font-size: 12.5px; line-height: 1.6; }
.aim-org-q > p:first-child { text-transform: uppercase; letter-spacing: .06em; font-size: 11px; }
.aim-org-q .aim-task-link + .aim-task-link { margin-left: 8px; }
/* Roles sit on one line each: two roles held in two channels run together into
   one sentence about a rank, which is the reading this pane is built to avoid. */
.aim-role { display: inline-block; margin-right: 10px; white-space: nowrap; }
</style>
