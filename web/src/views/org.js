// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'org',
  title: 'Org',
  hint: 'who is in each channel, who may dispatch to whom, and what is not recorded',
  order: 75,
  icon: 'Share',
  component: () => import('../panes/OrgPane.vue'),
}
