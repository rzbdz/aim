"""A view. Registering one is the whole extension point."""
from ..gate import may_see_peer_secrets
from ..primitives import esc


def render_barrier(state, viewer, labels):
    blocks = []
    for ch in state["channels"]:
        phase = ch["phase"]
        secrets = may_see_peer_secrets(state, ch, viewer)
        sealed = ""
        for who in ch["participants"]:
            seal = ch["seals"].get(who)
            if not seal:
                sealed += f'<li>{esc(who)}: <span class="warn">not sealed</span></li>'
                continue
            claims = seal.get("claims") or []
            digest = (seal.get("digest") or seal.get("private_log_sha256") or "")[:12]
            # The gate withholds a *peer's* claims. Your own seal is your own
            # commitment and `aim` lets you read your own log; a dashboard that
            # hid it too would be more restrictive than the tool it renders.
            if secrets or who == viewer:
                body = "".join(
                    f'<li><b>{esc(c.get("id",""))}</b> c={esc(c.get("confidence",""))} '
                    f'<p>{esc(c.get("claim",""))}</p>'
                    f'<p class="dim">kill_if: {esc(c.get("kill_if",""))}</p></li>' for c in claims)
                sealed += (f'<li>{esc(who)}: sealed <code>{esc(digest)}…</code>, {len(claims)} claim(s)'
                           f'<ul class="plain">{body}</ul></li>')
            else:
                sealed += (f'<li>{esc(who)}: sealed <code>{esc(digest)}…</code>, {len(claims)} claim(s) '
                           f'<span class="dim">(contents withheld: this viewer is a participant and the '
                           f'channel is in {esc(phase)})</span></li>')
        refus = ""
        for r in ch["refusals"]:
            refus += (f'<tr><td>{esc(r.get("ts","")[11:19])}</td><td>{esc(r.get("agent",""))}</td>'
                      f'<td>{esc(r.get("action",""))}</td><td>{esc(r.get("class",""))}</td>'
                      f'<td>{esc(r.get("phase",""))}</td><td class="dim">{esc((r.get("reason") or "")[:110])}</td></tr>')
        if not refus:
            refus = '<tr><td colspan="6" class="dim">no refusals: nobody has leaned on this barrier yet, which is not the same as everybody behaving.</td></tr>'
        chain = "".join(
            f'<li><code>{esc(name)}</code>: <b class="{"ok" if v["state"]=="OK" else "warn"}">{esc(v["state"])}</b> '
            f'{v["records"]} record(s) {esc(v["why"])}</li>' for name, v in ch["chain"].items())
        hist = " -> ".join(esc(h.get("phase", "")) for h in ch["history"])
        tasks_note = (f'{len(ch["tasks_recorded"])} task event(s) recorded' if ch["tasks_exists"]
                      else 'no tasks.jsonl yet: the board is showing the plan seed, not the store')
        blocks.append(f'''<h3>#{esc(ch["id"])} - {esc(phase)} round {esc(ch["round"])}</h3>
<p class="dim">{esc(ch["manifest"].get("topic",""))}</p>
<p>leader <b>{esc(ch["leader"])}</b> | participants {esc(", ".join(ch["participants"]))} | {hist}</p>
<p class="dim">{esc(tasks_note)}</p>
<ul class="plain">{sealed}</ul>
<h4>refusals, from the ledger</h4>
<table class="items"><tr><th>ts</th><th>agent</th><th>action</th><th>class</th><th>phase</th><th>reason</th></tr>{refus}</table>
<h4>chain verification (done here, independently of bin/aim)</h4>
<ul class="plain">{chain}</ul>''')
    if not blocks:
        blocks.append('<p class="empty">no channels found under this root.</p>')
    return "".join(blocks)


def build(page):
    """Page(state, viewer)"""
    return render_barrier(page.state, page.viewer, None)


def plugin(ctx):
    ctx.register_view("barrier", "Barrier & audit", "屏障与审计", build, order=70)
