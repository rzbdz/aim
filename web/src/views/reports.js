// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'reports',
  title: 'Reports',
  titleZh: '报告',
  hint: 'burndown, cycle time, and what is waiting on what',
  order: 60,
  icon: 'TrendCharts',
  component: () => import('../panes/ReportsPane.vue'),
}
