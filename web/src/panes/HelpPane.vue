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
import { STATUS_TYPE, statusLabel } from '../theme'
import { useBoard } from '../stores/board'

const board = useBoard()
const ctx = inject('ctx')

/**
 * The shell's groups, in the shell's order, over the panes it registered.
 *
 * The shell draws this grouping in its sidebar (`App.vue:53-67`) and this page
 * has to agree with it or the map is a second opinion about the same nav. Only
 * the membership is written here; the title and the purpose sentence are read off
 * the registration, so a pane that renames itself renames its row.
 */
const PANE_GROUPS = [
  { title: 'Work', keys: ['attention', 'kanban', 'gantt', 'items'] },
  { title: 'Conversation', keys: ['chat'] },
  { title: 'Insight', keys: ['reports'] },
  { title: 'Governance', keys: ['barrier', 'plan'] },
  { title: 'Reference', keys: ['help'] },
]

/**
 * Move the pane's own scroller to a row, and keep the address bar honest.
 *
 * A plain `<a href="#phase-commit">` cannot be used here: in hash mode the whole
 * route lives *in* the fragment, so the browser's own fragment jump rewrites the
 * route to `phase-commit` ("no such pane") and moves the window, which this shell
 * does not scroll. `main.js:141-158` resolves a fragment against `.aim-main` for
 * exactly that reason, and this is the same move made by the page that owns the
 * links -- same selector, same 12px offset, so a row lands identically whether the
 * reader followed a chip or a contents line. The fragment is replaced rather than
 * pushed, so Back still returns to the pane the reader came from.
 */
function goTo(id) {
  const scroller = document.querySelector('.aim-main')
  const target = document.getElementById(id)
  if (!scroller || !target) return
  const top = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top
  scroller.scrollTo({ top: Math.max(0, scroller.scrollTop + top - 12), behavior: 'smooth' })
  const parts = String(window.location.hash || '').split('#')
  parts[parts.length - 1] = id
  history.replaceState(null, '', parts.join('#'))
}

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
const panes = computed(() => {
  const index = new Map((ctx?.views || []).map((view) => [view.key, view]))
  return PANE_GROUPS.map((group) => ({ title: group.title, panes: group.keys.map((key) => index.get(key)).filter(Boolean) }))
    .filter((group) => group.panes.length)
})

/**
 * A deep link into this page is the shell's job, not this page's.
 *
 * `main.js:141-158` splits the fragment at the last `#` (the whole route lives in
 * it: `#/help#phase-resolve` is one string with two) and scrolls `.aim-main` to
 * the row, retrying until the lazy chunk has mounted. This page therefore has to
 * do exactly one thing for that to work: carry the ids. It used to keep a local
 * `currentAnchor` for an `ElAnchor` that was never rendered, which marked the
 * contents for nobody.
 */
const initial = ref('')
{
  const raw = String(window.location.hash || '').replace(/^#/, '')
  const cut = raw.lastIndexOf('#')
  const fragment = cut === -1 ? '' : decodeURIComponent(raw.slice(cut + 1))
  if (fragment && document.getElementById(fragment)) initial.value = fragment
}

/**
 * A pane's URL, by the shell's own rule.
 *
 * `main.js:292-295` registers `/${view.key}` for every view, so a link to a pane
 * is derived the same way the route is: the help map is written once and cannot
 * point at a path a pane stopped having.
 */
const pathOf = (view) => `/${view.key}`

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
  { id: 'tokens', title: 'The words on the screen — every token the board draws' },
  { id: 'inspecting', title: 'How a person acts on a work item — and on a decision' },
  { id: 'identifiers', title: 'Identifiers — what a bare M3 or R7 means' },
  { id: 'glossary', title: 'Glossary' },
]

/**
 * The phase enum, always drawn through its chip.
 *
 * `PHASES` carries a `next` that is a protocol value, and `TRANSITIONS` carries
 * `from`/`to` protocol values. Drawn raw those are enums in a label, which is the
 * defect this page exists to answer -- so both go through the one component that
 * knows the English word and keeps the raw value one hover away. The anchor is
 * built here rather than in a second lookup, so the row a chip links to and the
 * row the contents links to are the same expression.
 */
const phaseAt = (key) => ({ key, label: phaseLabel(key), anchor: phaseAnchor(key) })

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
 * The task state machine, read off the payload.
 *
 * `board.statuses` is the live list of statuses the tool can write, and
 * `task_flow.flow` is the move table the CLI itself checks -- the same
 * `TASK_FLOW` that `aim task move` consults before it refuses, which the server
 * publishes by parsing `bin/aim` for the constant rather than retyping it
 * (`aimboard/api.py`, `_cli_constant`). Reading it here is the difference
 * between a page that describes the tool and a page that *is* the tool's own
 * table: a move the CLI adds next month draws itself, and a move it removes
 * stops being offered.
 *
 * Before this key existed the table below was quoted by hand from
 * `bin/aim:95-102`, and the note that used to sit here said the moves were "the
 * one thing on this card that cannot be read off the record". That is no longer
 * true, and a citation that is no longer needed is a copy waiting to drift --
 * which is exactly what T-0214 named. The literal is kept only as the fallback
 * for a server that predates the key, because a blank table on the page that
 * explains the states is worse than a stale one, and `stale: true` in the shell
 * already says which of the two the reader has.
 */
const FLOW_FALLBACK = {
  backlog: ['ready', 'blocked', 'dropped'],
  ready: ['doing', 'blocked', 'dropped'],
  doing: ['review', 'blocked', 'dropped'],
  review: ['done', 'doing', 'blocked', 'dropped'],
  done: [],
  blocked: ['ready', 'doing', 'dropped'],
  dropped: [],
}
const TASK_FLOW = computed(() => board.doc?.task_flow?.flow || FLOW_FALLBACK)

/**
 * Which statuses `aim task move` will accept, and which it has no rule for.
 *
 * Two facts that look like one. `accepts` is the set the CLI's parser will
 * take -- a value outside it is a *form* refusal, refused before the phase is
 * consulted. `unconstrained` is a status in `statuses` with no `flow` entry at
 * all: today that is empty, and the page says "none" rather than drawing it as
 * "no legal moves", because those are different claims about the tool and only
 * one of them is what the record says.
 */
const MOVE_ACCEPTS = computed(() => board.doc?.task_flow?.accepts || [])
const MOVE_UNCONSTRAINED = computed(() => board.doc?.task_flow?.unconstrained || [])

/**
 * The refusal classes, read off the payload where the payload has them.
 *
 * `refusal_classes` carries `{class, from, where}`: the name, the site that
 * emits it, and the file it lives in. What it does *not* carry is the
 * explanation, and that is the part this card owns -- the three paragraphs
 * below are the page's own reading of what each class means for a person
 * looking at the barrier, and they are keyed by class name so a class the
 * server publishes and this page has no paragraph for still gets a row instead
 * of vanishing. The paragraphs are the reason a reader came to this card; the
 * vocabulary is the reason the rows are the tool's own.
 */
const REFUSAL_PROSE = {
  barrier: {
    label: 'the barrier',
    how: 'You asked for something the phase withholds — reading a sealed peer, speaking in Resolving, '
      + 'advancing without being the leader. Recorded with the phase it happened in, because the '
      + 'temptation is the evidence.' },
  form: {
    label: 'a malformed request',
    how: 'The call was rejected before the phase was consulted: a missing argument, an id that does not '
      + 'exist, a value the verb cannot take. A bug or a typo, not a protocol finding — so it is not '
      + 'evidence about the barrier.' },
  unrecorded: {
    label: 'a class the refusing site did not state',
    how: 'The refusal is real and the reason is missing. A weaker claim than either of the two above, '
      + 'and drawn as one rather than guessed at.' },
}
const REFUSAL_CLASSES = computed(() => {
  const published = board.doc?.refusal_classes
  const rows = Array.isArray(published) && published.length
    ? published
    : Object.keys(REFUSAL_PROSE).map((cls) => ({ class: cls, from: '', where: '' }))
  return rows.map((row) => ({
    ...row,
    ...(REFUSAL_PROSE[row.class] || {
      label: row.class,
      how: 'The record names this class and this card has no paragraph for it yet — the name is the '
        + 'tool\'s, the explanation is missing, and saying so is better than guessing one.',
    }),
  }))
})

/**
 * The verbs a person actually reaches for, with their flags.
 *
 * Every flag here except `--force` is quoted from `bin/aim:4118-4170`; `--force`
 * is on `task link` and is named because it is the one flag that writes a
 * deadlock into the record on purpose. The channel is the live one, so the
 * sentence is runnable rather than illustrative, and `--as` carries the identity
 * the server declares rather than a placeholder.
 */
const ACTIONS = computed(() => {
  const as = board.writer || board.viewer || '<you>'
  const ch = board.doc?.channel || '<channel>'
  const at = `--as ${as} --channel ${ch}`
  return [
    { want: 'Take a work item nobody has taken', where: 'Items, Kanban and Attention mark it unassigned',
      argv: `aim task claim ${at} --id <T-…>` },
    { want: 'Move one along the board', where: 'drag a card, or the drawer on any row',
      argv: `aim task move ${at} --id <T-…> --to <status> [--reason "…"]` },
    { want: 'Hand one to somebody else', where: 'the owner control in the item drawer',
      argv: `aim task assign ${at} --id <T-…> --owner <who> [--reason "…"]` },
    { want: 'Answer a decision that is waiting on you', where: 'the decisions card on Attention',
      argv: `aim task move ${at} --id <T-…> --to <status> --reason "…"` },
    { want: 'Ask the leader to open cross-examination', where: 'a participant cannot advance a channel',
      argv: `aim request-advance ${at} --to CROSS_EXAMINE --reason "…"` },
    { want: 'Advance the channel yourself (leader only)', where: 'the phase control on Audit & barrier',
      argv: `aim advance ${at} --to <PHASE>` },
    { want: 'Record a blocker between two items', where: 'the dependency editor on Gantt and Plan',
      argv: `aim task link ${at} --id <T-…> --blocked-by <T-…>` },
    { want: 'Write down what you found', where: 'the drawer, on any item',
      argv: `aim task comment ${at} --id <T-…> --body "…"` },
  ]
})
</script>

<template>
  <section class="aim-help">
    <el-alert type="info" :closable="false" show-icon style="margin-bottom:14px">
      <template #title>
        This page explains what the dashboard is showing. Nothing here is required reading to use it —
        it is what to open when a chip, a column or a refusal does not mean anything yet.
      </template>
    </el-alert>

    <!-- The contents and the pane map, first, because the two complaints this
         page earned were "no way in" and "never says what any pane is for", and
         both are about the reader who has not started reading yet. -->
    <el-card shadow="never" style="margin-bottom:14px">
      <template #header><span>On this page</span></template>
      <ol class="aim-help-contents">
        <!-- A button, not an `<a href="#id">`: see `goTo` above -- in hash mode
             the route is the fragment, so the browser's own jump is a navigation
             to a pane that does not exist. -->
        <li v-for="entry in SECTIONS" :key="entry.id">
          <button type="button" class="aim-help-toc" @click="goTo(entry.id)">{{ entry.title }}</button>
        </li>
      </ol>
      <p class="aim-dim" style="font-size:12px;margin:10px 0 0">
        Every section also has a stable anchor — <code class="aim-mono">{{ SECTIONS[0].id }}</code>,
        <code class="aim-mono">phase-commit</code>, <code class="aim-mono">concept-barrier</code> — which is
        what a chip or an identifier on another page links to. The page never renames one of those quietly:
        a link from a page the reader cannot see is broken without anyone noticing.
      </p>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px" id="panes">
      <template #header><span>The panes — what each page is for</span></template>
      <p class="aim-dim" style="font-size:12.5px;margin-top:0">
        The sidebar names tools; this says what each one is for. The title and the purpose sentence are the
        pane's own registration, not a second copy of it, and the grouping is the shell's.
      </p>
      <div v-for="group in panes" :key="group.title" class="aim-help-pane-group">
        <h4>{{ group.title }}</h4>
        <table class="aim-help-table">
          <tbody>
            <tr v-for="pane in group.panes" :key="pane.key">
              <td style="width:180px">
                <RouterLink :to="pathOf(pane)">{{ pane.title }}</RouterLink>
              </td>
              <td class="aim-dim">{{ pane.hint }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px" id="concepts" class="aim-help-concepts">
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

    <el-card shadow="never" style="margin-bottom:14px" id="phases">
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
              <!-- The chip, not a bare tag: the header, the barrier tabs and the
                   refusal filter all say a phase through this component, and a
                   page about the words cannot be the one place that says it
                   differently. -->
              <PhaseChip :phase="phase.key" effect="dark" />
              <div class="aim-dim" style="font-size:11.5px;margin-top:3px">{{ phase.summary }}</div>
            </td>
            <td><code class="aim-mono aim-dim">{{ phase.key }}</code></td>
            <td>
              <p style="margin:0 0 5px">{{ phase.what }}</p>
              <p style="margin:0" class="aim-help-consequence">{{ phase.consequence }}</p>
            </td>
            <td>
              <!-- The `next` field is a protocol value. Drawn raw it is the
                   exact defect this page exists after, so it is drawn as the
                   phase it names, with the enum one hover away. -->
              <PhaseChip v-if="phase.next" :phase="phase.next" link />
              <span v-else class="aim-dim">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px" id="machine">
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

    <!-- The tokens card is the page's half of T-0156's rule: every raw value the
         board prints in a chip, a column or a row is explained here. It is
         *derived* wherever the record can answer (the status vocabulary and its
         provenance values come off the payload) and written down only where the
         board would otherwise print a string with no explanation at all. -->
    <el-card shadow="never" style="margin-bottom:14px" id="tokens">
      <template #header><span>The words on the screen — every token the board draws</span></template>
      <p class="aim-dim" style="font-size:12.5px;margin-top:0">
        Nothing on this dashboard prints a bare enum. Where a raw value is the right thing to say — a
        column heading, a bug report, an argument to <code class="aim-mono">aim</code> — it is drawn
        beside the English, never instead of it. These are the values the rest of the board shows.
      </p>

      <h4 style="margin:14px 0 6px;font-size:12.5px">Work item status — what a card in a column means</h4>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:150px">status</th>
            <th style="width:170px">what it means</th>
            <th>what can follow it</th>
          </tr>
        </thead>
        <tbody>
          <!-- The statuses are the ones this board holds (`statuses` in the
               payload, which is `TASK_STATUSES` in `bin/aim`); the moves beside
               them are `task_flow.flow` -- the table `aim task move` checks
               before it refuses, parsed out of the CLI by the server rather
               than retyped here. A status the tool cannot move has to be
               visible as one, which is why the two empty rows say so instead of
               being dropped. -->
          <tr v-for="st in board.statuses" :key="st">
            <td><el-tag size="small" effect="dark" :type="STATUS_TYPE[st] || 'info'">{{ statusLabel(st) }}</el-tag></td>
            <td class="aim-mono aim-dim" style="font-size:11px">{{ st }}</td>
            <td>
              <template v-if="(TASK_FLOW[st] || []).length">
                <el-tag v-for="next in TASK_FLOW[st]" :key="next" size="small" effect="plain"
                        style="margin:0 4px 2px 0">{{ statusLabel(next) }}</el-tag>
              </template>
              <span v-else-if="MOVE_UNCONSTRAINED.includes(st)" class="aim-dim">
                no rule at all — the tool has no move table entry for this status
              </span>
              <span v-else class="aim-dim">nothing — this is where a work item stops</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="aim-dim" style="font-size:12px;margin:6px 0 0">
        <em>in review</em> going back to <em>in progress</em> is the "changes requested" move, not a
        mistake: the record shows the item moved twice, which is the point of moving it rather than
        editing it.
        <template v-if="MOVE_ACCEPTS.length">
          The moves above are drawn from the same table the CLI enforces; a status outside
          <code class="aim-mono">{{ MOVE_ACCEPTS.join(' ') }}</code> cannot even be named, and is
          refused as a <em>form</em> error before the phase is consulted.
        </template>
      </p>

      <h4 style="margin:18px 0 6px;font-size:12.5px">Provenance — where a work item actually lives</h4>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:300px">value in the record</th>
            <th>what it means for you</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="aim-mono" style="font-size:11.5px">{{ PROVENANCE.storeOnly }}</td>
            <td>A recorded work item. This is the one the verbs work on: it can be claimed, moved,
                assigned and commented on, and the store is the authority for it.</td>
          </tr>
          <tr>
            <td class="aim-mono" style="font-size:11.5px">{{ PROVENANCE.seedOnly }}</td>
            <td>A promise: a line in <code class="aim-mono">plan/plan.json</code> that the store has no
                record of. It is drawn because the plan says it exists, not because anyone is doing it,
                and an id in this state cannot be moved — the tool answers <em>no such task</em>.</td>
          </tr>
          <tr>
            <td class="aim-mono" style="font-size:11.5px">{{ PROVENANCE.both }}</td>
            <td>Both: the plan seeds it and the store holds it, so it behaves like a recorded item and the
                plan still lists it.</td>
          </tr>
        </tbody>
      </table>
      <p class="aim-dim" style="font-size:12px;margin:6px 0 0">
        Right now: {{ taskSplit.text }} The counts are read from the payload, so this sentence cannot
        drift from the board it describes.
      </p>

      <h4 style="margin:18px 0 6px;font-size:12.5px">A refusal, by class</h4>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:150px">class</th>
            <th style="width:190px">what was refused</th>
            <th>how to read it</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in REFUSAL_CLASSES" :key="row.class">
            <td>
              <code class="aim-mono">{{ row.class }}</code>
              <!-- Where the class comes from is the tool's own answer, published
                   on `refusal_classes`, and it is the difference between a class
                   a site deliberately stated and one it inherited from a
                   default. A reader filtering the ledger by class is relying on
                   that distinction, so it is shown rather than buried. -->
              <div v-if="row.from" class="aim-dim" style="font-size:10.5px;margin-top:2px">{{ row.from }}</div>
            </td>
            <td>{{ row.label }}</td>
            <td class="aim-dim">
              {{ row.how }}
              <div v-if="row.where" class="aim-mono" style="font-size:10.5px;margin-top:3px">{{ row.where }}</div>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="aim-dim" style="font-size:12px;margin:6px 0 0">
        A refusal is recorded before anything is written, so the class is the field an audit groups by.
        The three names are the tool's; the reading beside each is this page's.
      </p>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px" id="inspecting">
      <template #header><span>How a person acts on a work item — and on a decision</span></template>
      <p style="font-size:12.5px;margin-top:0">
        Every control on this dashboard resolves to a command, and the command is quoted in full before you
        press anything: a button whose action you cannot read is a button you are taking on trust. Where the
        board already knows who you are it fills the identity in for you
        (<code class="aim-mono">--as {{ board.writer || board.viewer }}</code>) — so the same sentence works
        whether you are reading it here or typing it yourself.
      </p>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:210px">what you want</th>
            <th>the exact command</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in ACTIONS" :key="row.want">
            <td>{{ row.want }}<div class="aim-dim" style="font-size:11.5px;margin-top:3px">{{ row.where }}</div></td>
            <td><code class="aim-mono">{{ row.argv }}</code></td>
          </tr>
        </tbody>
      </table>
      <p class="aim-dim" style="font-size:12px;margin:8px 0 0">
        Two of these are the leader's and not a participant's: the edges of the phase machine are
        leader-only (see <em>The state machine</em> above), so a participant asks with
        <code class="aim-mono">request-advance</code> and the leader's queue is what the Attention pane
        draws. And if a command is refused, the refusal is not an error page — it is written into the
        ledger with the phase it happened in, because someone wanting something the barrier withholds is
        evidence about the barrier.
        <RouterLink to="/barrier">Audit &amp; barrier</RouterLink> has the ledger and the refusals.
      </p>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px" id="identifiers">
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

    <el-card shadow="never" id="glossary">
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

<style scoped>
/* The contents is long enough to need two columns at a desktop width and one on
   a phone, so it wraps rather than pushing the pane's own scroller sideways. */
.aim-help-contents {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 4px 24px;
  margin: 0;
  padding-left: 20px;
}
/* A button, reset to look like the link it is: it moves the scroller itself
   (see `goTo`), which an `<a href="#…">` cannot do in hash mode. */
.aim-help-toc {
  border: 0;
  background: none;
  padding: 2px 0;
  font: inherit;
  font-size: 13px;
  color: var(--el-color-primary);
  text-align: left;
  cursor: pointer;
}
.aim-help-toc:hover { text-decoration: underline; }
.aim-help-toc:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 2px; border-radius: 4px; }
.aim-help-pane-group + .aim-help-pane-group { margin-top: 10px; }
.aim-help-pane-group h4 {
  margin: 0 0 2px;
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--aim-dim);
}
</style>
