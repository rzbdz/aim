/**
 * Markdown, by three libraries that already exist and are all well past a
 * thousand stars (verified, see design/09): `markdown-it` for parsing,
 * `highlight.js` for fenced code, `github-markdown-css` for typography.
 *
 * The one thing configured rather than adopted is `html: false`. A message body
 * here is text another agent wrote; rendering it as HTML in the leader's browser
 * would make the fabric an injection channel. Markdown is a formatting language,
 * not permission to execute.
 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/common'

export function markdownPlugin(ctx) {
  const md = new MarkdownIt({
    html: false,
    linkify: true,
    breaks: true,
    highlight(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        try { return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value } catch { /* fall through */ }
      }
      return ''
    },
  })
  ctx.provide('markdown', {
    render: (text) => md.render(text || ''),
    /** counting words is how the reader gets "this is long, jump to the end" */
    size: (text) => (text || '').length,
  })
}
