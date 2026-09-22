<script setup>
import { computed, inject, onBeforeUnmount, onErrorCaptured, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElAside, ElDrawer } from 'element-plus'
import { useColorMode, useMediaQuery } from '@vueuse/core'
import { useBoard } from './stores/board'
import { phaseConcept } from './concepts'
import OwnerAvatar from './components/OwnerAvatar.vue'
import PhaseChip from './components/PhaseChip.vue'
import TaskDecisionDrawer from './components/TaskDecisionDrawer.vue'

const ctx = inject('ctx')
const board = useBoard()
const route = useRoute()

/**
 * The sidebar is a column when there is room and a drawer when there is not.
 *
 * Measured 2026-09-22 at 390x844, bundle 59c319b+dirty: `<el-aside width="216px">`
 * was a permanent column, `.el-main` was left 174px of 390 (45%), and the header
 * row -- a phase chip, a summary, "as of", an avatar, a 190px select and a button,
 * which cannot fit in 174px -- spilled past it to a `documentElement.scrollWidth`
 * of 623. That is why the same number appeared on nine unrelated routes: what
 * widened the page was the shell, not the pane.
 *
 * The two numbers here and the `@media (max-width: 900px)` block in style.css
 * have to agree; one breakpoint, expressed twice because CSS and JS cannot share
 * a constant here. The nav itself is written once -- `<component :is>` swaps the
 * wrapper (a column, or a drawer over the page), so the two cannot drift.
 */
const navNarrow = useMediaQuery('(max-width: 900px)')
const navOpen = ref(false)
const navShell = computed(() => (navNarrow.value
  ? {
      is: ElDrawer,
      props: {
        modelValue: navOpen.value,
        'onUpdate:modelValue': (open) => { navOpen.value = open },
        direction: 'ltr',
        size: '264px',
        title: 'navigation',
        bodyClass: 'aim-nav',
        class: 'aim-nav-drawer',
      },
    }
  : { is: ElAside, props: { width: '216px', class: 'aim-aside aim-nav' } }))

/**
 * The palette is one class on <html> and a preference that outlives the tab.
 *
 * Every colour on the board is already a token in style.css -- light values on
 * `:root`, the dark ones verbatim under `html.dark` -- and Element Plus scopes
 * its own dark variables to that same class, so the whole feature is the class
 * plus somewhere to remember the choice. VueUse's `useColorMode` owns both: it
 * is the standard implementation (20k+ stars) of exactly this, it writes the
 * choice to localStorage, and it keeps the class on <html> in sync with it.
 *
 * `initialValue: 'light'` rather than the default `'auto'` is deliberate: the
 * card's default is light, and a reader on a dark desktop has not asked this
 * board to be dark. The handler below sets 'light'/'dark' explicitly, so the
 * stored value is the choice the reader made and not a note that the operating
 * system happens to agree with it.
 */
const palette = useColorMode({
  storageKey: 'aim-palette',
  initialValue: 'light',
  modes: { dark: 'dark', light: '' },
})
/**
 * The palette is applied in index.html as well as here, and that duplication is
 * the point. `useColorMode` reads the stored choice when main.js runs, which is
 * after the bundle has arrived -- one paint too late, so a reload of a dark board
 * flashed white first. An inline script in index.html reads the same key and puts
 * the class on <html> before the first paint; this watcher keeps the two in step
 * from then on, and it is the only writer of the class in the app.
 */
watch(palette, (mode) => {
  document.documentElement.classList.toggle('dark', mode === 'dark')
}, { immediate: true })
const dark = computed(() => palette.value === 'dark')
const togglePalette = () => { palette.value = dark.value ? 'light' : 'dark' }

/**
 * The shell mounts the one drawer, so a task opened from a report row, a blocker
 * id or a milestone row is the same drawer as a card, and the pane the reader
 * arrived in does not have to know anything about it.
 */
const taskDrawer = ctx.service('taskDrawer')
const drawerTask = computed(() => {
  const id = taskDrawer.state.id
  return board.tasks.find((task) => task.id === id) || taskDrawer.state.task
})
/**
 * A drawer does not outlive the reading it belonged to.
 *
 * The drawer lives in the shell, so it survives the pane it was opened from being
 * torn down. That is what makes "the same drawer from every surface" possible,
 * and it is also how a task can end up floating over a page that has nothing to
 * do with it -- open a blocker on a report row, walk to the plan, and the board
 * is showing something the reader has left. Same defect as a dead-end identifier,
 * one layer up, so: leaving the list closes the item.
 *
 * Only the path counts. Opening the drawer never navigates, and the moves that
 * happen *inside* a list -- a filter, an anchor -- are query and hash, so they do
 * not close what the reader is looking at.
 */
watch(() => route.path, () => taskDrawer.close())

/**
 * The nav drawer closes itself the same way: a reader who picks a page has left
 * it, and on a 390px screen a drawer that stays open covers the page they just
 * asked for. Clicking the item the reader is already on fires no navigation, so
 * the menu's own `select` closes that case too.
 */
watch(() => route.path, () => { navOpen.value = false })
watch(navNarrow, () => { navOpen.value = false })

/**
 * A navigation whose chunk is not on the server any more must say so.
 *
 * Every pane is a dynamic import, so its file is named after its content. A
 * rebuild renames every one of them, and a tab that was open across the rebuild
 * is still holding the old names: the click asks the server for a file that no
 * longer exists, the import rejects, `vue-router` logs "Failed to fetch
 * dynamically imported module" and leaves the URL where it was, and the reader
 * gets a nav that does nothing at all -- measured for T-0179, and the worst
 * failure this shell can have, because the board looks alive while it is dead.
 *
 * The router reports it as a rejected navigation and the browser as an error
 * event, so both are listened to: a navigation rejected because the reader
 * clicked something else is not this, and a preload of a pane behind a link
 * fails without any navigation at all. A navigation that *does* land clears the
 * message -- once a pane has arrived the URL and the page agree again.
 *
 * No poll and no retry: the bundle moves once, and the fix is a reload, which is
 * the reader's call and not something this page does under their hands.
 */
const router = useRouter()
const stale = ref(false)
const looksStale = (message) => /dynamically imported module|Importing a module script failed|Unable to preload/i.test(String(message))
router.onError((error) => { if (looksStale(error?.message || error)) stale.value = true })
const onChunkError = (event) => {
  const target = event.target
  if (target?.tagName === 'SCRIPT' && looksStale(target.src || '')) stale.value = true
  if (looksStale(event.message || '')) stale.value = true
}
onMounted(() => {
  window.addEventListener('error', onChunkError, true)
  window.addEventListener('unhandledrejection', onChunkError)
})
onBeforeUnmount(() => {
  window.removeEventListener('error', onChunkError, true)
  window.removeEventListener('unhandledrejection', onChunkError)
})
router.afterEach(() => { stale.value = false })
// A named function rather than `window.location` in the template: a template
// expression resolves against the render context, and the global is not in it.
const reload = () => { window.location.reload() }

/**
 * A render error must not be able to brick the page.
 *
 * The drawer is mounted by the shell, and `el-drawer` mounts its overlay before
 * its panel renders. So when anything inside the panel throws while rendering,
 * the panel never appears and the overlay stays -- a full-screen invisible modal
 * that swallows every click, including the nav, and survives a route change. A
 * broken panel is a bad panel; an invisible modal over a working page is a board
 * the reader can only escape by reloading, with nothing on screen to tell him so.
 *
 * Measured, before this: `TaskDecisionDrawer.vue` read three names it never
 * bound, so *every* click on *every* work item left `overlay: 1, drawer: 0` and
 * left the URL unchanged when the nav was clicked through it.
 *
 * So: whatever a pane or the drawer throws, the drawer closes and the reader
 * keeps a page he can use. The error is logged rather than swallowed -- a
 * failure that hides itself is the thing this project keeps measuring.
 */
onErrorCaptured((err, instance, info) => {
  taskDrawer.close()
  console.error('[aimboard] render error; the drawer was closed to keep the page usable:', info, err)
  return false
})
const views = ctx.views
const current = computed(() => views.find((v) => v.key === route.meta.view))
/**
 * The header says the phase in English and in full sentences, because it is the
 * one line that tells the leader what they may do next. The protocol value is in
 * the tooltip and one link away on Help & concepts; it is not the label.
 */
const phase = computed(() => phaseConcept(board.phase))
const phaseType = computed(() => (['SEALED_DIVERGENT', 'COMMIT', 'SYNTHESIS'].includes(board.phase) ? 'warning'
  : board.phase === '-' ? 'info' : 'success'))
const stamp = computed(() => (board.doc?.generated_at || '').replace('T', ' ').slice(0, 19))
/**
 * The one count on every screen, over the record, and it says which set it read.
 *
 * It used to be `board.tasks` and `board.overdue` -- the plan file merged with
 * the record -- so the numbers above every pane were partly a count of `plan/*.json`
 * lines, in the same voice as work, with no authority word anywhere. That is the
 * set the store's own comment calls out (`stores/board.js`, the block above
 * `recordedOverdue`: "the panes that draw the merged board on purpose -- Items,
 * Kanban, Gantt, Plan -- keep reading `tasks`; this is for the page that counts"),
 * reached from the one surface that is on *every* page.
 *
 * Measured 2026-09-22 on this tree, `/api/state` folded at `date(2026,9,22)`:
 * 177 rows, of which 87 are plan seeds -- 72 of them reading `status: done` and 15
 * `dropped` from the plan text, none of them with an event behind them -- and 90
 * are recorded. Both counts happen to be right today: 22 rows of the merge are not
 * terminal and all 22 are `store only`, and the 3 late rows are all `store only`.
 * The verdict does not rest on that: a number that is right by coincidence of the
 * fold is one plan edit away from counting promises as work, and the header never
 * told the reader which of the two universes it had counted.
 *
 * So the work numbers read `recorded`, and the promises are printed beside them as
 * promises rather than dropped -- a reader who wants the plan's size still gets it,
 * in the one line that does not read as work.
 */
const counts = computed(() => ({
  open: board.recorded.filter((t) => !board.terminal.includes(t.status)).length,
  late: board.recordedOverdue.length,
  blocked: (board.recordedByStatus.blocked || []).length,
  promises: board.seedOnly.length,
}))
const navGroups = computed(() => {
  const byKey = new Map(views.map((view) => [view.key, view]))
  return [
    { title: 'Work', keys: ['attention', 'kanban', 'gantt', 'items'] },
    { title: 'Conversation', keys: ['chat'] },
    { title: 'Insight', keys: ['reports'] },
    { title: 'Governance', keys: ['barrier', 'plan', 'org'] },
    // Concepts last, and in the nav rather than hidden behind a "?": the reader
    // who needs it is the one who does not yet know what to look for.
    { title: 'Reference', keys: ['help'] },
  ].map((group) => ({
    title: group.title,
    views: group.keys.map((key) => byKey.get(key)).filter(Boolean),
  })).filter((group) => group.views.length)
})

/**
 * The one deferral the reader did not cause, and so the one that needs a
 * different sentence above the pane.
 *
 * `deferred` is one flag with two producers (stores/board.js:425-429, 443-450):
 * an obstruction the reader's own state presents, and a refresh whose fetch
 * failed. The store refuses to call the second one the record moving -- its
 * comment at stores/board.js:444-446 says in as many words that doing so "would
 * be the dashboard inventing an event" -- and the shell must not print the event
 * the store declined to name. The digest poll failed there, so nothing was
 * observed to have moved.
 *
 * The shell makes no distinction of its own: it compares the store's reason and
 * renders one of two sentences. If the store rewords that reason this falls back
 * to the sentence the banner already had, which is the only failure this branch
 * can have.
 */
const deferredByFailure = computed(() => board.deferredReason === 'the server could not be reached')
</script>

<template>
  <el-container class="aim-shell">
    <!-- First in the document, so one Tab reaches the reading pane from anywhere
         and the reader is not walked through seven nav items to get past them. -->
    <a class="aim-skip" href="#aim-main">skip to the reading pane</a>
    <!-- One nav, two wrappers: the column when there is room, the drawer when
         there is not. See `navShell` above. -->
    <component :is="navShell.is" v-bind="navShell.props">
      <div class="aim-brand">
        <h1><span class="aim-mark">aim</span> board</h1>
        <div class="aim-sub">
          <div>{{ board.doc?.root?.split('/').pop() || '…' }} · {{ board.doc?.as_of }}</div>
          <!-- The record's numbers first and named, then the plan's count in its
               own word. `on the record` is the same phrase `OverviewPane.vue:155`
               puts on the work signals, because it is the same distinction: a
               promise has no item to move, so it is not a number to act on. -->
          <div>{{ counts.open }} open · {{ counts.late }} late · {{ counts.blocked }} blocked
            — on the record</div>
          <div v-if="counts.promises">{{ counts.promises }} plan promise(s), not work</div>
        </div>
      </div>
      <el-menu :default-active="route.path" router @select="navOpen = false">
        <el-menu-item-group v-for="group in navGroups" :key="group.title" :title="group.title">
          <el-menu-item v-for="v in group.views" :key="v.key" :index="`/${v.key}`">
            <el-icon><component :is="v.icon || 'Grid'" /></el-icon>
            <span>{{ v.title }}</span>
          </el-menu-item>
        </el-menu-item-group>
      </el-menu>
      <div class="aim-links aim-dim">
        <div style="margin-bottom:6px">for a foreign tool</div>
        <el-button-group>
          <el-button size="small" tag="a" href="/api/state">json</el-button>
          <el-button size="small" tag="a" href="/board.csv">csv</el-button>
          <el-button size="small" tag="a" href="/board.ics">ical</el-button>
        </el-button-group>
      </div>
    </component>

    <el-container>
      <el-header height="auto" class="aim-header">
        <!-- The drawer's handle, and only where there is a drawer: an aside that
             hides itself with no way back is a missing nav, not a drawer. The
             name is the one T-0160 searches for. -->
        <el-button v-if="navNarrow" class="aim-nav-toggle" size="small" text
                   :aria-label="navOpen ? 'close the navigation menu' : 'open the navigation menu'"
                   :aria-expanded="navOpen" @click="navOpen = !navOpen">
          <el-icon><Menu /></el-icon>
        </el-button>
        <!-- The chip is the same component the audit page uses: one place knows
             what a phase is called, and one place knows that a tooltip around a
             link must not eat the key that activates it. -->
        <PhaseChip :phase="board.phase" :type="phaseType" effect="dark" round link />
        <span class="aim-dim aim-header-phase" style="font-size:11.5px">{{ phase.summary }}</span>
        <span v-if="board.withheld" class="aim-dim" style="font-size:11.5px">
          {{ board.withheld }} withheld from this view
        </span>
        <span style="flex:1" />
        <span class="aim-dim" style="font-size:11px">as of {{ stamp }}</span>
        <OwnerAvatar :id="board.viewer" :size="20" />
        <el-select :model-value="board.viewer" size="small" class="aim-viewer" @change="board.setViewer"
                   placeholder="whose view">
          <el-option v-for="(a, id) in board.agents" :key="id" :value="id" :label="`${id} · ${a.kind}`" />
        </el-select>
        <!-- Named, and the label says what the press will do rather than what the
             current palette is; `aria-pressed` carries the state. -->
        <el-button class="aim-theme-toggle" size="small" text
                   :aria-label="dark ? 'switch the board to the light palette' : 'switch the board to the dark palette'"
                   :aria-pressed="dark" :title="dark ? 'light palette' : 'dark palette'"
                   @click="togglePalette">
          <el-icon><Sunny v-if="dark" /><Moon v-else /></el-icon>
        </el-button>
        <el-button size="small" :loading="board.loading" @click="board.load()">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </el-header>

      <el-main id="aim-main" tabindex="-1" :class="['aim-main', { 'aim-main-conversation': current?.key === 'chat' }]">
        <!--
          Not a warning. A refresh is not an error, and the board updates itself;
          this line exists only for the case where it deliberately did not, so the
          reader is told what is waiting and given one quiet way to take it now.
        -->
        <div v-if="board.deferred" class="aim-deferred">
          <span v-if="deferredByFailure" class="aim-dim">
            the board could not be read — the record it is showing is the last one it had.
          </span>
          <span v-else class="aim-dim">
            newer activity on the record — held back because {{ board.deferredReason }}.
          </span>
          <el-button size="small" text type="primary" @click="board.update({ force: true })">
            update now
          </el-button>
        </div>
        <el-alert v-if="board.error" type="error" show-icon :closable="false" style="margin-bottom:14px"
                  :title="`the board could not be read: ${board.error}`" />
        <!-- Not an error about the record, so it does not look like one: the pane
             could not be fetched because the build it was named in is gone. It
             says which route was asked for, because on a 390px drawer the nav
             closes on click and the address bar is the only other clue. -->
        <el-alert v-if="stale" type="warning" show-icon :closable="false" style="margin-bottom:14px"
                  title="this page was built before the board was rebuilt, so the pane you asked for is no longer on the server"
                  :description="`nothing was loaded for ${route.path}, and the page you can see is the one you had. Reload to pick up the new build.`">
          <el-button size="small" text type="primary" @click="reload">reload</el-button>
        </el-alert>
        <div class="aim-page">
          <h2>{{ current?.title }}</h2>
          <span class="aim-sub">{{ current?.hint }}</span>
        </div>
        <el-skeleton v-if="!board.doc && board.loading" :rows="8" animated />
        <router-view v-else />
      </el-main>
    </el-container>
  </el-container>

  <TaskDecisionDrawer v-model="taskDrawer.state.open" :task="drawerTask"
                      :depth="taskDrawer.state.history.length"
                      @update:model-value="(open) => { if (!open) taskDrawer.close() }"
                      @back="taskDrawer.back({ tasks: board.tasks })" />
</template>
