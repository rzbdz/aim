"""The shell.

Renders whatever views are registered, in order, and nothing else. It does not
know the name of a single pane: that is the property the kernel exists to give,
and it is why adding a view does not touch this file.
"""
from datetime import date

from .const import LABELS
from .gate import gate_channel, visible_tasks
from .kernel import Context, Page
from .primitives import esc, parse_day
from .views import load_builtin
from .web import CSS, JS


def build_context():
    """A context with the built-in views loaded. Third parties can `use` more."""
    return load_builtin(Context("aimboard"))


def render_page(board_ctx, page):
    panes = []
    for view in board_ctx.views:
        title = view["title_zh"] if page.lang == "zh" else view["title"]
        panes.append((view["key"], title, view["render"](page)))
    nav = "".join(
        f'<button data-tab="{key}" aria-selected="{"true" if n == 0 else "false"}">{esc(title)}</button>'
        for n, (key, title, _) in enumerate(panes))
    body = "".join(
        f'<section class="pane{" active" if n == 0 else ""}" id="pane-{key}">{html}</section>'
        for n, (key, _, html) in enumerate(panes))
    stale = (f'generated {esc(page.generated_at)} · as of {esc(page.state["as_of"])} · '
             f'viewer {esc(page.viewer)} '
             f'({esc(page.state["registry"].get(page.viewer, {}).get("kind", "?"))}) · '
             f'root {esc(page.state["root"])} · phase {esc(page.phase)}')
    digest = page.digest or ""
    return f'''<!doctype html>
<html lang="{esc(page.lang)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>aim board - {esc(page.state["root"].split("/")[-1])}</title>
<style>{CSS}</style></head><body>
<div id="stale" class="stalebar" hidden>new activity on the record since this page was drawn
  <button onclick="location.reload()">refresh</button></div>
<header class="top">
  <h1>aim board</h1>
  <div class="meta">{stale}</div>
  <nav role="tablist">{nav}</nav>
</header>
<main>{body}</main>
<script>window.__digest = "{digest}"; window.__pollMs = {int(page.poll_ms or 0)};</script>
<script>{JS}</script>
</body></html>'''


def render_html(state, viewer, risks, generated_at, lang="en", board_ctx=None,
                digest=None, poll_ms=0):
    """The compatible entry point: build a context, a Page, and render."""
    board_ctx = board_ctx or build_context()
    channels = state["channels"]
    channel = gate_channel(state, viewer, channels[0] if channels else {})
    tasks, hidden = visible_tasks(state, viewer, channel)
    as_of = parse_day(state["as_of"]) or date.today()
    page = Page(state=state, viewer=viewer, risks=risks or {}, generated_at=generated_at,
                lang=lang, labels=LABELS.get(lang, LABELS["en"]), tasks=tasks, hidden=hidden,
                milestones=state["milestones"], as_of=as_of, channels=channels,
                digest=digest, poll_ms=poll_ms)
    page.phase = channel.get("phase", "-")
    return render_page(board_ctx, page)
