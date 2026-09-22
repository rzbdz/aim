<script setup>
/**
 * The page that explains the words.
 *
 * It exists because `SEALED_DIVERGENT` was drawn as a label and a reader had to
 * reverse-engineer the protocol from an identifier. The content is all in
 * `concepts.js` — this file draws it, and holds no copy of its own, so the
 * explanation a chip links to and the explanation a reader scrolls to cannot
 * drift apart.
 *
 * Anchors are stable and are what the phase chips link to (`#phase-resolve`).
 * An anchor that moves breaks a link from a page the reader cannot see is
 * broken, so add to this page rather than renaming what is here.
 *
 * It also opens with a contents and a map of the panes, both generated from what
 * the shell already declares. Measured before either existed (T-0186, 1440x1000
 * on the live board): 4184px of page inside a 951px `.aim-main`, the identifier
 * table 2372px below the pane top, the glossary 2892px, and not one in-page link
 * -- and the nine panes' purpose sentences, which the shell draws on arrival
 * (`App.vue:138`), appeared nowhere on the page whose own promise is "this page
 * explains what the dashboard is showing". Both summaries are *reads*, not
 * copies: the contents from the five cards below, the pane directory from
 * `ctx.views`.
 */
import { computed, inject, ref } from 'vue'
import PhaseChip from '../components/PhaseChip.vue'
import { GLOSSARY, CONCEPTS, ID_PREFIXES, PHASE_ACCESS, PHASES, TRANSITIONS, phaseAnchor } from '../concepts'
import { useBoard } from '../stores/board'

const board = useBoard()
const ctx = inject('ctx')

/**
 * The scroller is named, not looked up.
 *
 * `main.js:81-101` resolves a fragment against `.aim-main` because
 * `vue-router`'s scroll handling is about the window and this shell's window
 * never scrolls. The contents has to move the same element, so it is handed the
 * same selector: an `ElAnchor` left on its default container would write into
 * `document.documentElement` and move nothing, which is the exact failure
 * `main.js:66-79` was written to fix.
 */
const scroller = '.aim-main'

/**
 * The pane directory, straight off the shell's own registrations.
 *
 * `views/index.js` globs `web/src/views/*.js`, and every registration carries the
 * pane's `title` and its `hint` -- the one-line purpose the shell draws when the
 * reader arrives. The card that filed this measured that Help contained none of
 * "Kanban", "Gantt" or "Conversations"; those words were only in the sidebar,
 * which names tools rather than purposes. The purposes already existed. Writing
 * them here a second time is the drift this project keeps measuring
 * (`concepts.js:1-19` says the same thing about the phase vocabulary), so they
 * are read.
 *
 * Sidebar order and sidebar groups, not `order`: the shell's nav puts
 * Conversations between the panes it groups as "Work", and the grouping is part
 * of the answer to "what am I looking at". A key the shell no longer registers is
 * dropped rather than drawn as a dead row.
 */
const navGroups = computed(() => {
  const byKey = new Map((ctx?.views || []).map((view) => [view.key, view]))
  return [
    { title: 'Work', keys: ['attention', 'kanban', 'gantt', 'items'] },
    { title: 'Conversation', keys: ['chat'] },
    { title: 'Insight', keys: ['reports'] },
    { title: 'Governance', keys: ['barrier', 'plan'] },
    { title: 'Reference', keys: ['help'] },
  ].map((group) => ({ title: group.title, panes: group.keys.map((key) => byKey.get(key)).filter(Boolean) }))
    .filter((group) => group.panes.length)
})

/**
 * Which section the contents says the reader is in, for the first paint.
 *
 * `ElAnchor` works this out itself on mount, but only for an href that is a real
 * selector, and the shell's whole hash is `#/help#phase-resolve` -- one string
 * with two `#` in it. So the id is read the way `main.js:57-63` reads it, with
 * the last `#` as the separator, and handed over as `currentAnchor`. Without it a
 * deep link opens with nothing marked, which reads as "you are nowhere" on
 * exactly the arrival every phase chip in the product links to.
 */
const initial = ref('')
{
  const raw = String(window.location.hash || '').replace(/^#/, '')
  const cut = raw.lastIndexOf('#')
  const fragment = cut === -1 ? '' : decodeURIComponent(raw.slice(cut + 1))
  if (fragment && document.getElementById(fragment)) initial.value = fragment
}

/**
 * The contents is built from this list, and the cards below carry these ids.
 *
 * Two lists in one page is how a contents comes to link to a section that was
 * renamed -- so the hrefs here are `phaseAnchor(entry.id)` against ids that the
 * `v-for`s below consume.
 */
const SECTIONS = [
  { id: 'panes', title: 'The panes — what each page is for' },
  { id: 'concepts', title: 'Why this is shaped the way it is' },
  { id: 'phases', title: 'Phases — where a channel is and what that lets you do' },
  { id: 'machine', title: 'The state machine — how a channel moves' },
  { id: 'identifiers', title: 'Identifiers — what a bare M3 or R7 means' },
  { id: 'glossary', title: 'Glossary' },
]

/**
 * The convention from `concepts.js`, joined to the counts in the live record.
 *
 * Derived, not written down: if a prefix has nothing behind it right now the row
 * says zero rather than describing something the reader cannot find.
 */
const countOf = {
  'T-': () => board.tasks.length,
  M: () => Object.keys(board.milestones || {}).length,
  D: () => (board.register?.decisions || []).length,
  R: () => (board.register?.risks || []).length,
}

/**
 * `T-` is the one prefix whose count covers more than one universe, and the row
 * used to describe only one of them.
 *
 * Measured live 2026-09-22: `board.tasks.length` was 161, of which 87 carried
 * `provenance: "seed only (not yet in the store)"`. The row's sentence --
 * "minted by aim task new; the store is the authority" -- was therefore false of
 * 87 of the ids it counted. Not a wording nit: `aim task move --id T-0042`
 * answers `no such task: T-0042` (`_load_task_or_die`, `bin/aim:1682`), because
 * `fold_tasks('hello')` folds the *events* and the store has no event for it;
 * the id exists only in `plan/plan.json`. A reader who believed the row goes
 * looking for T-0042 in the store and does not find it, which is what "the
 * store is the authority" promises he can do.
 *
 * The count moved 115 -> 151 -> 161 without the sentence becoming true, so the
 * sentence is not a claim that gets truer with time; it is a claim about *which*
 * ids are counted. The clauses below are counted from `provenance` -- the one
 * field that distinguishes the universes -- so they cannot drift from the
 * payload the way a written-down "87 of them" could.
 */
const PROVENANCE = {
  seedOnly: 'seed only (not yet in the store)',
  both: 'store + seed',
  storeOnly: 'store only',
}

const taskSplit = computed(() => {
  const total = board.tasks.length
  // Whole-value tests, not `includes('seed')`: the seed-only sentence contains
  // the word "store" ("not yet in the store"), so a substring test for one
  // universe answers yes for the other -- which is how a single field came to
  // be counted as two different things (`board.js:62` reads it the same way,
  // which is why `isPromise` counts a "store + seed" item as a promise).
  const count = (value) => board.tasks.filter((t) => (t.provenance || '') === value).length
  const seedOnly = count(PROVENANCE.seedOnly)
  const both = count(PROVENANCE.both)
  const storeOnly = count(PROVENANCE.storeOnly)
  const unknown = total - seedOnly - both - storeOnly
  const clauses = [`recorded in the store: ${storeOnly} of ${total}`,
                   `seeded and recorded both: ${both}`,
                   `plan seeds the store has no record of: ${seedOnly}`]
  // A zero is stated rather than dropped, because the row states counts at all:
  // `0` and "this row did not look here" are different facts, and the reader
  // cannot tell them apart from an omitted clause. The fourth clause is the
  // exception -- it names a category with no definition in the vocabulary, so a
  // sentence about it at zero would be noise rather than a measurement.
  if (unknown) clauses.push(`provenance this row does not know: ${unknown}`)
  return {
    total,
    seed: seedOnly,
    recorded: storeOnly,
    text: `${clauses.join('; ')}.`,
    // The consequence, not the taxonomy. A seed is not a work item the reader
    // can do anything with, and the row used to imply the opposite. The
    // condition ("the store has no record of") is kept in the sentence because
    // it is what makes it true: a "store + seed" id *can* be moved.
    limit: 'A seed the store has no record of cannot be moved, assigned or recorded: '
      + '`aim task move`, `aim task assign` and `aim task comment` answer `no such task` for its '
      + 'id, because there is no event of it for the store to change.',
  }
})

/**
 * Which plan file each milestone actually came from, read off the payload.
 *
 * Same audit as the `T-` row, one row down: the vocabulary says milestones are
 * "written by hand in plan/plan.json", and on 2026-09-22 one of the ten (M6,
 * Dogfooding) carried `source: "dogfood.json"`. The count was right and the
 * sentence was not, which is the defect this card is about -- so the filename is
 * derived here too rather than written down twice.
 */
const milestoneFiles = computed(() => [...new Set(Object.values(board.milestones || {})
  .map((m) => m.source).filter(Boolean))].sort())

const identifierRows = computed(() =>
  ID_PREFIXES.map((entry) => {
    const count = countOf[entry.prefix]?.() ?? 0
    if (entry.prefix === 'T-') {
      // The T- row's `where` in `concepts.js` is the convention for an id the
      // *store* minted, and it is true of `taskSplit.recorded` of them. The
      // split is what the row has to say instead, so the override lives here
      // rather than as a second, contradicting entry in the shared vocabulary.
      return { ...entry, count, split: taskSplit.value, where: 'the plan seeds it, or `aim task new` records it' }
    }
    if (entry.prefix === 'M' && milestoneFiles.value.length) {
      return { ...entry, count, where: `written by hand in ${milestoneFiles.value.map((f) => `plan/${f}`).join(', ')}` }
    }
    return { ...entry, count }
  }))

/**
 * The transition table's caption, read off `TRANSITIONS` rather than written out.
 *
 * Both sentences used to spell out two phase names in prose ("Synthesising →
 * Cross-examining", "Sealed, Committed and Synthesising"): a second copy of the
 * dictionary, in the one direction that cannot be caught, because prose does not
 * fail when the dictionary changes. They are now the chips' own labels, and the
 * anchored rows they point at are read from the list, so a renamed phase renames
 * its sentence.
 *
 * `el-tag` rather than `PhaseChip` for the enum beside it: a chip inside a `p`
 * wraps an `el-tooltip` around a `<span>`, and a tooltip's trigger keys swallow
 * the keys of whatever it wraps (components/PhaseChip.vue:30-40). Nothing here is
 * a control, so a tag is the honest element.
 */
const edgeTo = (key) => TRANSITIONS.find((edge) => edge.from === key && edge.to === 'CROSS_EXAMINE')
const rowAt = (key) => (key ? `#${phaseAnchor(key)}` : '')
const labelOf = (rows) => rows.map((row) => phaseLabel(row.key)).join(', ')
/**
 * The cells the raw enums sit in, keyed by the enum.
 *
 * `phase.next` is the protocol value of the phase a reader goes to next, and the
 * protocol-value column of the row above is the same string -- so this is the
 * one lookup that puts the English word beside the enum without writing the
 * mapping a third time.
 */
const phaseByKey = Object.fromEntries(PHASES.map((phase) => [phase.key, phase]))
</script>

<template>
  <section class="aim-help">
    <el-alert type="info" :closable="false" show-icon style="margin-bottom:14px">
      <template #title>
        This page explains what the dashboard is showing. Nothing here is required reading to use it —
        it is what to open when a chip, a column or a refusal does not mean anything yet.
      </template>
    </el-alert>

    <el-card shadow="never" style="margin-bottom:14px" class="aim-help-concepts">
      <template #header><span>Why this is shaped the way it is</span></template>
      <article v-for="concept in CONCEPTS" :key="concept.id" :id="concept.id" class="aim-help-concept">
        <h3>{{ concept.title }}</h3>
        <p v-for="(paragraph, index) in concept.body" :key="index">{{ paragraph }}</p>
        <div class="aim-help-links">
          <RouterLink v-for="link in concept.links" :key="link.to" :to="link.to">
            {{ link.label }}
          </RouterLink>
        </div>
      </article>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px">
      <template #header>
        <span>Phases — where a channel is in its lifecycle, and what that lets you do</span>
      </template>
      <p class="aim-dim" style="font-size:12.5px;margin-top:0">
        The phase is not a label on a conversation: the server decides who may read whom from it, and refuses
        the rest. Each row below says what the phase is for and what it means for you right now. The
        <code class="aim-mono">protocol value</code> is the exact string in the record — it is what you quote
        in a bug report and what <code class="aim-mono">aim advance --to</code> takes.
      </p>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:150px">phase</th>
            <th style="width:190px">protocol value</th>
            <th>what it means for you</th>
            <th style="width:150px">usually next</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="phase in PHASES" :key="phase.key" :id="phaseAnchor(phase.key)">
            <td>
              <el-tag size="small" effect="dark" type="warning">{{ phase.label }}</el-tag>
              <div class="aim-dim" style="font-size:11.5px;margin-top:3px">{{ phase.summary }}</div>
            </td>
            <td><code class="aim-mono aim-dim">{{ phase.key }}</code></td>
            <td>
              <p style="margin:0 0 5px">{{ phase.what }}</p>
              <p style="margin:0" class="aim-help-consequence">{{ phase.consequence }}</p>
            </td>
            <td>
              <span v-if="phase.next">{{ phase.next }}</span>
              <span v-else class="aim-dim">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px">
      <template #header><span>The state machine — how a channel moves, and who may move it</span></template>
      <p class="aim-dim" style="font-size:12.5px;margin-top:0">
        Phase transitions are <strong>leader-only</strong> — every one of them, not just the
        important ones. <code class="aim-mono">bin/aim</code> checks this before it looks at the
        target phase, so a participant cannot advance a channel at all. What a participant can do
        is ask: <code class="aim-mono">aim request-advance</code> records the request in the log
        and prints <em>awaiting &lt;leader&gt;</em>. Those requests are what the Leader decisions
        card on Attention is a queue of.
      </p>

      <h4 style="margin:16px 0 6px;font-size:12.5px">What each phase lets a participant do</h4>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:190px">phase</th>
            <th style="width:150px">may read each other</th>
            <th style="width:150px">may speak on the channel</th>
            <th>may write privately to the leader</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in PHASE_ACCESS" :key="row.key" :id="'access-' + phaseAnchor(row.key)">
            <td><PhaseChip :phase="row.key" link /></td>
            <td :class="row.read ? '' : 'aim-dim'">{{ row.read ? 'yes' : 'no' }}</td>
            <td :class="row.say ? '' : 'aim-dim'">{{ row.say ? 'yes' : 'no' }}</td>
            <td :class="row.private ? '' : 'aim-dim'">{{ row.private ? 'yes' : 'no' }}</td>
          </tr>
        </tbody>
      </table>
      <p class="aim-dim" style="font-size:12px;margin:6px 0 0">
        The first three rows are identical, and that is not a typo. Sealed, Committed and
        Synthesising grant exactly the same access — the phase changes, the permissions do not.
        That is why approving the first two edges is bookkeeping rather than a decision.
      </p>

      <h4 style="margin:18px 0 6px;font-size:12.5px">Every edge, and what crossing it unlocks</h4>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:120px">from</th>
            <th style="width:190px">to</th>
            <th style="width:250px">what it unlocks</th>
            <th>why it is that way</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="edge in TRANSITIONS" :key="edge.from + '->' + edge.to">
            <td><PhaseChip :phase="edge.from" link /></td>
            <td><PhaseChip :phase="edge.to" link /></td>
            <td :class="edge.unlocks.startsWith('nothing') ? 'aim-dim' : ''">{{ edge.unlocks }}</td>
            <td class="aim-dim">{{ edge.why }}</td>
          </tr>
        </tbody>
      </table>
      <p class="aim-dim" style="font-size:12px;margin:6px 0 0">
        Only one edge in this table ends independence: Synthesising → Cross-examining. If you are
        ever asked to approve a transition and you cannot say what it unlocks, this table is the
        answer — and where it says <em>nothing</em>, the honest decision is that there is none to
        make.
      </p>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px">
      <template #header><span>Identifiers — what a bare M3 or R7 means</span></template>
      <p class="aim-dim" style="font-size:12.5px;margin-top:0">
        Single letters are drawn on the board, the plan and the dependency lists. They are a naming
        convention held in the plan files rather than a vocabulary the tool defines, so each row says who
        is the authority for it and how many exist in the record right now.
      </p>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:74px">prefix</th>
            <th style="width:130px">names</th>
            <th style="width:92px">right now</th>
            <th>where it comes from, and what it is for</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in identifierRows" :key="row.prefix">
            <td><code class="aim-mono"><strong>{{ row.prefix }}</strong></code></td>
            <td>{{ row.kind }}</td>
            <td class="aim-dim">{{ row.count }}</td>
            <td>
              <p style="margin:0 0 5px">
                <code class="aim-mono aim-dim" style="font-size:11.5px">{{ row.where }}</code>
              </p>
              <!-- The split, and nothing else, for a prefix that has one: 87 of
                   the 161 ids this row counts are not on the record, and the
                   number above them cannot be read without it. Styled with the
                   page's existing consequence mark rather than a new class, so
                   this edit adds no rule to style.css. -->
              <p v-if="row.split" style="margin:0 0 5px" class="aim-help-consequence">
                {{ row.split.text }}
              </p>
              <p v-if="row.split?.limit" style="margin:0 0 5px" class="aim-help-consequence">
                {{ row.split.limit }}
              </p>
              <p style="margin:0" class="aim-dim">{{ row.detail }}</p>
            </td>
          </tr>
        </tbody>
      </table>
    </el-card>

    <el-card shadow="never">
      <template #header><span>Glossary</span></template>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:170px">term</th>
            <th style="width:340px">what it is</th>
            <th>why it is that way</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in GLOSSARY" :key="entry.term" :id="entry.anchor">
            <td><strong>{{ entry.term }}</strong></td>
            <td>{{ entry.plain }}</td>
            <td class="aim-dim">{{ entry.why }}</td>
          </tr>
        </tbody>
      </table>
      <p class="aim-dim" style="font-size:12px;margin-bottom:0">
        Where a term has a home of its own, the page that owns it is the one to read:
        <RouterLink to="/barrier">Audit &amp; barrier</RouterLink> for the gate and the ledger,
        <RouterLink to="/plan">Plan &amp; risks</RouterLink> for what a plan seed and a drift are, and
        <RouterLink to="/attention">Attention</RouterLink> for what is waiting on you.
      </p>
    </el-card>
  </section>
</template>
