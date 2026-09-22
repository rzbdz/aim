// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'chat',
  title: 'Conversations',
  titleZh: '会话',
  hint: 'what was said, and only what this viewer may read',
  order: 50,
  icon: 'ChatDotRound',
  component: () => import('../panes/ChatPane.vue'),
}
