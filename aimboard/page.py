"""The shell.

Renders whatever views are registered, in order, and nothing else. It does not
know the name of a single pane: that is the property the kernel exists to give,
and it is why adding a view does not touch this file.
"""
from datetime import date
from pathlib import Path

from .api import phase_channel_provenance
from .const import LABELS
from .gate import gate_channel, visible_tasks
from .kernel import Context, Page
from .primitives import esc, parse_day
from .revision import default_dist, describe as describe_revision
from .views import load_builtin
from .web import CSS, JS


def build_context():
    """A context with the built-in views loaded. Third parties can `use` more."""
    return load_builtin(Context("aimboard"))


def render_page(board_ctx, page, build=None):
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
    # T-0252. `phase` alone is the default channel's phase with nothing naming the
    # channel, which is the defect the `/api/state` half of this card fixes, so the
    # no-JS line owes the reader the same noun. Drawn only when there is one to
    # name: a root with no channel prints `phase -` above, and `from channel -`
    # beside it would be inventing a noun rather than labelling a value.
    provenance = getattr(page, "phase_channel", None) or {}
    if provenance.get("id"):
        stale += (f'<span class="phase-from">from channel #{esc(provenance["id"])}'
                  f' ({esc(provenance.get("arm", ""))})</span>')
    # T-0196: the build this page was drawn by, on the line that already carries the
    # page's own identity (generated/as-of/viewer/root/phase). Drawn last because it
    # is the one item there that is about the *program* rather than about the record
    # it is drawing.
    stale += _build_line_html(build or {})
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


def build_line(payload=None):
    """The build this page was drawn by, from the payload when there is one.

    T-0196. The accept line is "the page states the revision and whether the tree
    was dirty", and until this existed the payload carried both and *no page
    printed either*: `__AIM_REVISION__` is defined by `vite.config.js` and read by
    nothing; `theme.js:46` claims "the shell already says which build is serving"
    when it does not; and both halves of the served bundle (measured this session:
    `index.html` and `index-*.js` fetched from 8777 and hashed against `web/dist`)
    contain the substrings `revision`, `stale` and `dirty` zero times.

    The payload's own block is preferred over recomputing it here: that is the block
    `/api/state` publishes, and a page that disagreed with the JSON API would be the
    second answer to one question this repo keeps filing cards about. When there is
    no payload (the `aimboard render` export) it is recomputed with the same function
    the endpoint uses.

    Three sentences come out of the pair, and they are different claims: the bundle
    was built from a *dirty* tree; the bundle was built from a **different commit**
    than the server runs; the source has changed *since* the build (`stale`, the
    content-hash comparison `revision.py:129-132` makes). The first is exactly the
    case `stale` cannot see -- it carries no hash of the label -- so it is drawn on
    its own rather than inferred from `stale`.
    """
    rev = (payload or {}).get("revision") if payload else None
    if not isinstance(rev, dict):
        rev = describe_revision(Path(__file__).resolve().parent.parent, default_dist())
    bundle = rev.get("bundle") if isinstance(rev.get("bundle"), dict) else None
    if not bundle:
        return {"known": False,
                "why": "no build left a revision record for this page to name"}
    label = str(bundle.get("revision") or "")
    fabric = str(rev.get("fabric") or "")
    head = label.split("+")[0].split("-")[0]
    behind = bool(head) and bool(fabric) and head != fabric.split("+")[0]
    return {"known": True, "label": label or "(no revision recorded)",
            "built_at": str(bundle.get("built_at") or ""),
            "dirty": bool(bundle.get("dirty")), "fabric": fabric, "behind": behind,
            "stale": rev.get("stale")}


def _build_line_html(inv):
    """`build_line` as one line of the header, escaped. Empty when nothing recorded."""
    if not inv.get("known"):
        return ""
    bits = f'build {esc(inv["label"])}'
    if inv.get("built_at"):
        bits += f' · built {esc(inv["built_at"])}'
    if inv["dirty"]:
        bits += (' · the tree was <b>dirty</b> at build time, so these bytes are not '
                 f'the committed code of <code>{esc(inv["label"])}</code>')
    if inv["behind"]:
        bits += (f' · the tree has moved since: the server runs '
                 f'<code>{esc(inv["fabric"])}</code>')
    if inv["stale"] is True:
        bits += (' · <b>stale</b>: the source changed since the build, so this page is '
                 'drawing code that no longer exists')
    elif inv["stale"] is None:
        bits += ' · the bundle recorded no source hash, so whether it is current is unknown'
    return f'<span class="build-line">{bits}</span>'


def render_html(state, viewer, risks, generated_at, lang="en", board_ctx=None,
                digest=None, poll_ms=0, payload=None):
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
    # T-0252, the no-JS half: `/api/state` names the channel its `phase` came from,
    # and this path reads the same `gate_channel` default, so it owes the reader the
    # same noun. The provenance is computed by `api.phase_channel_provenance` rather
    # than re-derived here, because a second copy of "which arm chose" is exactly the
    # two-answers-to-one-question shape this repo keeps finding; what this file owns
    # is drawing it, which it does below.
    page.phase_channel = phase_channel_provenance(state, viewer, channel)
    return render_page(board_ctx, page, build=build_line(payload))
