// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'attention',
  title: 'Attention',
  hint: 'only what needs you now; everything else lives in its own pane',
  order: 10,
  icon: 'DataBoard',
  component: () => import('../panes/OverviewPane.vue'),
}
