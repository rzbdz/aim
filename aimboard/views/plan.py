"""A view. Registering one is the whole extension point."""
from ..const import TERMINAL
from ..primitives import esc


def render_plan(state, risks, labels):
    ms = ""
    for mid, m in sorted(state["milestones"].items()):
        total = sum(1 for t in state["seed_tasks"].values() if t.get("milestone") == mid)
        done = sum(1 for t in state["seed_tasks"].values()
                   if t.get("milestone") == mid and t.get("status") in TERMINAL)
        pct = int(100 * done / total) if total else 0
        ms += (f'<tr><td>{esc(mid)}</td><td>{esc(m.get("name",""))}</td><td>{esc(m.get("due",""))}</td>'
               f'<td>{done}/{total}</td><td><span class="meter"><span style="width:{pct}%"></span></span> {pct}%</td>'
               f'<td class="dim">{esc(m.get("accept",""))}</td></tr>')
    rk = ""
    for r in risks.get("risks", []):
        rk += (f'<tr><td>{esc(r["id"])}</td><td>{esc(r["risk"])}</td><td>{esc(r["likelihood"])}</td>'
               f'<td>{esc(r["impact"])}</td><td>{esc(r["owner"])}</td><td>{esc(r["mitigation"])}</td>'
               f'<td class="dim">{esc(r.get("kill_if",""))}</td></tr>')
    dec = "".join(f'<li><b>{esc(d["id"])}</b> {esc(d["decision"])}<p class="dim">because {esc(d["because"])}</p></li>'
                  for d in risks.get("decisions", []))
    ng = "".join(f'<li>{esc(x)}</li>' for x in risks.get("non_goals", []))
    raci = "".join(f'<tr><td>{esc(r["area"])}</td><td>{esc(r["responsible"])}</td><td>{esc(r["accountable"])}</td>'
                   f'<td>{esc(r["consulted"])}</td></tr>' for r in risks.get("raci", []))
    dog = risks.get("dogfooding", {})
    doghtml = ""
    if dog:
        doghtml = (f'<h4>dogfooding</h4><p>{esc(dog.get("rule",""))}</p><ul class="plain">'
                   + "".join(f'<li>{esc(p)}</li>' for p in dog.get("practices", [])) + "</ul>"
                   + f'<p class="dim">kill_if: {esc(dog.get("kill_if",""))}</p>')
    return f'''<h4>milestones</h4>
<table class="items"><tr><th>id</th><th>name</th><th>due</th><th>done</th><th>progress</th><th>acceptance</th></tr>{ms}</table>
<h4>risks</h4>
<table class="items"><tr><th>id</th><th>risk</th><th>likelihood</th><th>impact</th><th>owner</th><th>mitigation</th><th>kill_if</th></tr>{rk}</table>
<h4>decisions</h4><ul class="plain">{dec}</ul>
<h4>non-goals</h4><ul class="plain">{ng}</ul>
<h4>who does what</h4>
<table class="items"><tr><th>area</th><th>responsible</th><th>accountable</th><th>consulted</th></tr>{raci}</table>
{doghtml}'''


def build(page):
    """Page(state, risks)"""
    return render_plan(page.state, page.risks, None)


def plugin(ctx):
    ctx.register_view("plan", "Plan & risk", "计划与风险", build, order=80)
