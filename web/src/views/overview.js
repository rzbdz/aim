// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'overview',
  title: 'Overview',
  titleZh: '概览',
  hint: 'the board at a glance, folded from the record',
  order: 10,
  icon: 'DataBoard',
  component: () => import('../panes/OverviewPane.vue'),
}
