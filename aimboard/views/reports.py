"""A view. Registering one is the whole extension point."""
from datetime import timedelta
from ..fold import task_history
from ..primitives import day_of, esc


def render_reports(tasks, milestones, as_of, labels):
    hist = task_history(tasks)
    dated = {t: h for t, h in hist.items() if h["created"]}
    done = {t: h for t, h in dated.items() if h["done"]}
    cycles = []
    for tid, h in done.items():
        a, b = day_of(h["created"]), day_of(h["done"])
        if a and b:
            cycles.append((b - a).days)
    cycles.sort()
    median = cycles[len(cycles) // 2] if cycles else None
    days = [as_of - timedelta(days=n) for n in range(13, -1, -1)]
    series = []
    for d in days:
        remaining = sum(1 for h in dated.values()
                        if day_of(h["created"]) <= d and not (h["done"] and day_of(h["done"]) <= d))
        series.append((d, remaining))
    throughput = {}
    for h in done.values():
        d = day_of(h["done"])
        throughput[d] = throughput.get(d, 0) + 1
    blocked = [(tid, h["task"]) for tid, h in hist.items() if h["task"].get("blocked_by")
               or h["task"].get("status") == "blocked"]
    open_blockers = "".join(
        f'<tr><td>{esc(tid)}</td><td>{esc(t.get("title",""))}</td>'
        f'<td>{esc(", ".join(t.get("blocked_by") or []))}</td>'
        f'<td>{esc(t.get("status",""))}</td><td>{esc(t.get("owner",""))}</td></tr>'
        for tid, t in sorted(blocked))
    if not open_blockers:
        open_blockers = '<tr><td colspan="5" class="dim">no work item is waiting on another.</td></tr>'
    chart = ""
    if dated:
        w, h, pad = 560, 160, 34
        hi = max(r for _, r in series) or 1
        step = (w - pad) / max(1, len(series) - 1)
        pts = " ".join(f"{pad + i * step:.1f},{h - pad - (r / hi) * (h - 2 * pad):.1f}"
                       for i, (_, r) in enumerate(series))
        bars = ""
        tmax = max(throughput.values()) if throughput else 1
        for i, d in enumerate(days):
            n = throughput.get(d, 0)
            if not n:
                continue
            bh = (n / tmax) * 40
            bars += (f'<rect class="thr" x="{pad + i * step - 4:.1f}" y="{h - pad - bh:.1f}" '
                     f'width="8" height="{bh:.1f}"><title>{n} done on {d}</title></rect>')
        labels_axis = "".join(
            f'<text x="{pad + i * step:.1f}" y="{h - 12}" class="axis">{d.isoformat()[5:]}</text>'
            for i, (d, _) in enumerate(series) if i % 3 == 0)
        chart = (f'<svg class="burndown" viewBox="0 0 {w} {h}" width="100%" role="img" '
                 f'aria-label="remaining work items per day, last 14 days">'
                 f'<line x1="{pad}" y1="{h - pad}" x2="{w - 6}" y2="{h - pad}" class="grid week"/>'
                 f'<line x1="{pad}" y1="{pad // 2}" x2="{pad}" y2="{h - pad}" class="grid week"/>'
                 f'{bars}<polyline class="line" points="{pts}"/>{labels_axis}'
                 f'<text x="{pad + 4}" y="{pad // 2 - 4}" class="axis">remaining (max {hi})</text>'
                 f'</svg>')
    else:
        chart = ('<p class="empty">no recorded work items yet: the burndown is drawn from task '
                 'events, and a seed file has none. Nothing here is inferred from today.</p>')
    cov = (f'{len(done)}/{len(dated)} recorded item(s) have a done transition; '
           f'{len(tasks) - len(dated)} item(s) are plan seed only and are absent from the chart')
    return f'''<h4>burndown, last 14 days</h4>
{chart}
<p class="note">{esc(cov)}</p>
<h4>throughput and cycle time</h4>
<p>{len(done)} item(s) completed · median cycle time {esc(median if median is not None else "-")} day(s) · mean {
   esc(round(sum(cycles) / len(cycles), 1) if cycles else "-")} day(s)</p>
<h4>what is waiting on what</h4>
<table class="items"><tr><th>id</th><th>title</th><th>blocked by</th><th>status</th><th>owner</th></tr>{open_blockers}</table>'''


def build(page):
    """Page(tasks, milestones, as_of)"""
    return render_reports(page.tasks, page.milestones, page.as_of, None)


def plugin(ctx):
    ctx.register_view("reports", "Reports", "报表", build, order=60)
