// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'barrier',
  title: 'Audit & barrier',
  titleZh: '审计与屏障',
  hint: 'phases, seals, refusals, and the chain all of it is written into',
  order: 70,
  icon: 'Lock',
  component: () => import('../panes/BarrierPane.vue'),
}
