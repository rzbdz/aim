"""A view. Registering one is the whole extension point."""
from ..const import STATUSES, TERMINAL
from ..primitives import esc, parse_day


def render_overview(state, tasks, hidden, channels, as_of, generated_at):
    by_status = {s: sum(1 for t in tasks.values() if t.get("status") == s) for s in STATUSES}
    overdue = [tid for tid, t in tasks.items()
               if parse_day(t.get("due")) and parse_day(t["due"]) < as_of and t.get("status") not in TERMINAL]
    blocked = [tid for tid, t in tasks.items() if t.get("status") == "blocked" or t.get("blocked_by")]
    mine = [tid for tid, t in tasks.items() if t.get("owner") == "codex"]
    ms_next = sorted((m.get("due") or "9999", mid, m.get("name", ""))
                     for mid, m in state["milestones"].items())
    ms_line = " · ".join(f'{esc(mid)} {esc(name)} ({esc(due)})' for due, mid, name in ms_next[:3])
    prog = "".join(f'<div class="stat"><b>{by_status[s]}</b><span class="dot s-{s}"></span>{s}</div>' for s in STATUSES)
    return f'''<div class="stats">{prog}
  <div class="stat"><b>{len(overdue)}</b><span class="dot s-blocked"></span>overdue</div>
  <div class="stat"><b>{len(blocked)}</b><span class="dot s-review"></span>blocked or waiting</div>
  <div class="stat"><b>{len(mine)}</b><span class="dot s-doing"></span>owned by codex</div>
</div>
<p class="note">{len(tasks)} work items in view{" · " + str(hidden) + " withheld by the barrier gate" if hidden else ""}
{" · " + str(len(state["unacked"])) + " unacked handoff(s)" if state["unacked"] else ""}.</p>
<p><b>next milestones:</b> {ms_line}</p>
'''


def build(page):
    """Page(tasks, hidden, channels, as_of, generated_at)"""
    return render_overview(page.state, page.tasks, page.hidden, page.channels, page.as_of, page.generated_at)


def plugin(ctx):
    ctx.register_view("overview", "Overview", "总览", build, order=10)
