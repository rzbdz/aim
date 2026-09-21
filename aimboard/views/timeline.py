"""A view. Registering one is the whole extension point."""
from datetime import timedelta
from ..const import STATUSES
from ..primitives import esc, parse_day


def render_gantt(milestones, tasks, as_of):
    dated = {tid: t for tid, t in tasks.items() if parse_day(t.get("start")) or parse_day(t.get("due"))}
    undated = sorted(tid for tid, t in tasks.items() if not (parse_day(t.get("start")) or parse_day(t.get("due"))))
    days = [parse_day(t.get("start")) or parse_day(t.get("due")) for t in dated.values()]
    days += [parse_day(t.get("due")) for t in dated.values() if parse_day(t.get("due"))]
    days += [d for d in (parse_day(m.get("due")) for m in milestones.values()) if d]
    if not days:
        return ('<p class="empty">no dates anywhere: every bar in a gantt is a promise, '
                'and this plan has not made one yet.</p>')
    lo, hi = min(days) - timedelta(days=1), max(days) + timedelta(days=1)
    span = max(1, (hi - lo).days)
    label_w, day_w, row_h = 250, max(9, min(26, int(900 / span))), 24
    width = label_w + span * day_w + 40
    groups = {}
    for tid, task in sorted(dated.items()):
        groups.setdefault(task.get("milestone") or "-", []).append((tid, task))
    rows, y = [], 30
    for ms_id in sorted(groups, key=lambda m: (m == "-", m)):
        ms = milestones.get(ms_id, {})
        ms_due = parse_day(ms.get("due"))
        rows.append(f'<g class="msrow"><rect x="0" y="{y-2}" width="{width}" height="{row_h}" class="msbg"/>'
                    f'<text x="6" y="{y+14}" class="mslabel">{esc(ms_id)} {esc(ms.get("name",""))}</text>')
        if ms_due:
            x = label_w + (ms_due - lo).days * day_w
            rows.append(f'<polygon points="{x},{y+6} {x+6},{y+12} {x},{y+18} {x-6},{y+12}" class="msdiamond"/>')
        rows.append("</g>")
        y += row_h
        for tid, task in groups[ms_id]:
            start, due = parse_day(task.get("start")), parse_day(task.get("due"))
            status = task.get("status", "backlog")
            label = f'{tid} {task.get("title","")}'
            if len(label) > 44:
                label = label[:43] + "…"
            rows.append(f'<text x="6" y="{y+15}" class="rlabel" title="{esc(task.get("title",""))}">'
                        f'{esc(label)}</text>')
            if start and due:
                x1 = label_w + (start - lo).days * day_w
                w = max(6, (due - start).days * day_w + day_w * 0.8)
                rows.append(f'<rect class="bar s-{status}" x="{x1:.1f}" y="{y+5}" width="{w:.1f}" '
                            f'height="{row_h-12}" rx="3"><title>{esc(tid)}: {esc(task.get("title",""))} '
                            f'[{status}] {start} to {due}</title></rect>')
                rows.append(f'<text x="{x1+w+5:.1f}" y="{y+15}" class="barlabel">{esc(status)}</text>')
            else:
                only = due or start
                x = label_w + (only - lo).days * day_w
                rows.append(f'<polygon points="{x},{y+5} {x+5},{y+12} {x},{y+19} {x-5},{y+12}" '
                            f'class="msdiamond"><title>{esc(tid)}: one date only, {only}</title></polygon>')
                rows.append(f'<text x="{x+8:.1f}" y="{y+15}" class="barlabel">{esc(status)} (one date)</text>')
            y += row_h
        y += 6
    grid = ""
    tick = lo
    while tick <= hi:
        x = label_w + (tick - lo).days * day_w
        is_monday = tick.weekday() == 0
        grid += (f'<line x1="{x:.1f}" y1="30" x2="{x:.1f}" y2="{y}" class="grid{" week" if is_monday else ""}"/>')
        if is_monday:
            grid += f'<text x="{x+3:.1f}" y="20" class="axis">{tick.isoformat()[5:]}</text>'
        tick += timedelta(days=1)
    edges = ""
    ypos = {}
    yy = 30
    for ms_id in sorted(groups, key=lambda m: (m == "-", m)):
        yy += row_h
        for tid, task in groups[ms_id]:
            ypos[tid] = yy + row_h / 2
            yy += row_h
        yy += 6
    for tid, task in dated.items():
        start = parse_day(task.get("start")) or parse_day(task.get("due"))
        for blocker in task.get("blocked_by") or []:
            if blocker not in ypos or tid not in ypos or blocker not in dated:
                continue
            bdue = parse_day(dated[blocker].get("due")) or parse_day(dated[blocker].get("start"))
            if not bdue or not start:
                continue
            x1 = label_w + (bdue - lo).days * day_w + day_w
            x2 = label_w + (start - lo).days * day_w
            y1, y2 = ypos[blocker], ypos[tid]
            mid = x1 + 6
            edges += (f'<path class="dep" d="M{x1:.1f},{y1:.1f} L{mid:.1f},{y1:.1f} '
                      f'L{mid:.1f},{y2:.1f} L{x2-2:.1f},{y2:.1f}"><title>{esc(blocker)} blocks {esc(tid)}</title></path>')
    today = ""
    if lo <= as_of <= hi:
        x = label_w + (as_of - lo).days * day_w
        today = (f'<line x1="{x:.1f}" y1="24" x2="{x:.1f}" y2="{y}" class="today"/>'
                 f'<text x="{x+3:.1f}" y="{y+12}" class="todaylabel">{esc(as_of.isoformat())}</text>')
    legend = " ".join(
        f'<span class="lg"><span class="dot s-{s}"></span>{s}</span>' for s in STATUSES)
    note = ""
    if undated:
        note = (f'<p class="note">{len(undated)} item(s) have no dates and are not drawn: '
                f'{esc(", ".join(undated))}</p>')
    return f'''<p class="legend">{legend}</p>
<svg class="gantt" viewBox="0 0 {width} {y+20}" width="100%" role="img"
     aria-label="gantt chart, {len(dated)} dated work items, as of {esc(as_of.isoformat())}">
  <g class="gridlayer">{grid}</g>
  <g class="edgelayer">{edges}</g>
  <g class="rowlayer">{"".join(rows)}</g>
  {today}
</svg>{note}'''


def build(page):
    """Page(milestones, tasks, as_of)"""
    return render_gantt(page.milestones, page.tasks, page.as_of)


def plugin(ctx):
    ctx.register_view("gantt", "Timeline", "甘特图", build, order=30)
