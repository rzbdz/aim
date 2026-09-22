// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'barrier',
  title: 'Audit & barrier',
  hint: 'the phase, seals, refusals and hash chain of each channel',
  order: 70,
  icon: 'Lock',
  component: () => import('../panes/BarrierPane.vue'),
}
