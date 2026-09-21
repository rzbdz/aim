"""A view. Registering one is the whole extension point."""
from ..components import deadline
from ..const import STATUSES
from ..primitives import esc


def render_table(tasks, as_of):
    head = ("<tr><th>id</th><th>title</th><th>status</th><th>owner</th><th>milestone</th>"
            "<th>start</th><th>due</th><th>blocked by</th><th>provenance</th></tr>")
    body = ""
    for tid, task in sorted(tasks.items()):
        due, late = deadline(task, as_of)
        body += (f'<tr data-owner="{esc(task.get("owner",""))}" data-status="{esc(task.get("status",""))}" '
                 f'data-milestone="{esc(task.get("milestone",""))}" data-tags="{esc(" ".join(task.get("tags") or []))}">'
                 f'<td class="tid">{esc(tid)}</td><td>{esc(task.get("title",""))}</td>'
                 f'<td><span class="dot s-{esc(task.get("status",""))}"></span> {esc(task.get("status",""))}</td>'
                 f'<td>{esc(task.get("owner",""))}</td><td>{esc(task.get("milestone",""))}</td>'
                 f'<td>{esc(task.get("start",""))}</td><td class="{late.strip()}">{esc(due)}</td>'
                 f'<td>{esc(", ".join(task.get("blocked_by") or []))}</td>'
                 f'<td class="dim">{esc(task.get("provenance",""))}</td></tr>')
    owners = sorted({t.get("owner", "") for t in tasks.values()} - {""})
    options = "".join(f'<option value="{esc(o)}">{esc(o)}</option>' for o in owners)
    mso = "".join(f'<option value="{esc(m)}">{esc(m)}</option>' for m in sorted({t.get("milestone", "") for t in tasks.values()} - {""}))
    return f'''<div class="filters">
  <label>owner <select data-filter="owner"><option value="">all</option>{options}</select></label>
  <label>status <select data-filter="status"><option value="">all</option>{"".join(f'<option value="{s}">{s}</option>' for s in STATUSES)}</select></label>
  <label>milestone <select data-filter="milestone"><option value="">all</option>{mso}</select></label>
  <label>tag <input data-filter="tag" placeholder="dogfood"></label>
</div>
<table class="items">{head}{body}</table>'''


def build(page):
    """Page(tasks, as_of)"""
    return render_table(page.tasks, page.as_of)


def plugin(ctx):
    ctx.register_view("table", "Work items", "工作项", build, order=40)
