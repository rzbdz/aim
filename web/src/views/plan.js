// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'plan',
  title: 'Plan & risks',
  titleZh: '计划与风险',
  hint: 'milestones, risks, decisions and the non-goals',
  order: 80,
  icon: 'Notebook',
  component: () => import('../panes/PlanPane.vue'),
}
