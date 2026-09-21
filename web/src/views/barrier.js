// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'barrier',
  title: 'Barrier & audit',
  titleZh: '屏障与审计',
  hint: 'phases, seals, refusals, and the chain all of it is written into',
  order: 70,
  icon: 'Lock',
  component: () => import('../panes/BarrierPane.vue'),
}
