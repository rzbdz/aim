// One pane. This file is the whole registration: the shell never names a pane.
export default {
  key: 'help',
  title: 'Help & concepts',
  hint: 'what the words mean, and what each phase lets you do',
  order: 90,
  icon: 'QuestionFilled',
  component: () => import('../panes/HelpPane.vue'),
}
