// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'gantt',
  title: 'Gantt',
  hint: 'dates, dependencies and milestones; drag inside the chart to zoom',
  order: 30,
  icon: 'Calendar',
  component: () => import('../panes/GanttPane.vue'),
}
