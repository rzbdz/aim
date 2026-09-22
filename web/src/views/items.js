// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'items',
  title: 'Work items',
  hint: 'every work item, with the fields that make it verifiable',
  order: 40,
  icon: 'List',
  component: () => import('../panes/ItemsPane.vue'),
}
