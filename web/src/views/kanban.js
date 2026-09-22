// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'kanban',
  title: 'Kanban',
  titleZh: '看板',
  hint: 'work items by status — a view of the log, never a file of its own',
  order: 20,
  icon: 'Grid',
  component: () => import('../panes/KanbanPane.vue'),
}
