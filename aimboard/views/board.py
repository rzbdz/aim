"""A view. Registering one is the whole extension point."""
from ..components import card_html
from ..const import STATUSES


def render_kanban(tasks, as_of):
    cols = []
    for status in STATUSES:
        items = [t for t in tasks.items() if t[1].get("status") == status]
        items.sort(key=lambda kv: (kv[1].get("due") or "9999", kv[0]))
        cards = "".join(card_html(tid, task, as_of) for tid, task in items)
        cols.append(f'''<section class="col" data-col="{status}">
  <h3><span class="dot s-{status}"></span>{status} <span class="count">{len(items)}</span></h3>
  <div class="colbody">{cards or '<p class="empty">nothing here</p>'}</div>
</section>''')
    return f'<div class="board">{"".join(cols)}</div>'


def build(page):
    """Page(tasks, as_of)"""
    return render_kanban(page.tasks, page.as_of)


def plugin(ctx):
    ctx.register_view("kanban", "Board", "看板", build, order=20)
