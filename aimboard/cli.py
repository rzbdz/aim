"""The command line."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs
from .const import LABELS
from .api import payload as json_state
from .exporters import export_csv, export_ical, json_payload
from .fabric import fabric_digest, load_fabric
from .fold import drift
from .gate import gate_channel, visible_tasks
from .page import render_html
from .primitives import now_iso, parse_day, read_json


def cmd_render(args):
    root = Path(args.root)
    if not root.exists():
        print(f"aimboard: no such root: {root}", file=sys.stderr)
        return 2
    as_of = parse_day(args.as_of) or datetime.now(timezone.utc).date()
    generated_at = args.generated_at or now_iso()
    plans = args.plan or ["plan/*.json"]
    state = load_fabric(root, plans, as_of)
    if args.channel:
        wanted = set(args.channel)
        state["channels"] = [c for c in state["channels"] if c["id"] in wanted]
        missing = wanted - {c["id"] for c in state["channels"]}
        if missing:
            print(f"aimboard: no such channel: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    if not state["channels"]:
        print(f"aimboard: no channels under {root}", file=sys.stderr)
        return 2
    viewer = args.viewer or state["channels"][0]["leader"] or "human"
    if viewer not in state["registry"]:
        print(f"aimboard: unknown viewer '{viewer}'. register first, or pass --as a registered id.",
              file=sys.stderr)
        return 2
    risks = {}
    for path in sorted(root.glob("plan/*.json")):
        doc = read_json(path)
        if isinstance(doc, dict):
            for key, value in doc.items():
                if isinstance(value, list) and key not in ("tasks", "milestones"):
                    risks.setdefault(key, []).extend(value)
                elif isinstance(value, dict) and key not in ("tasks", "milestones"):
                    risks.setdefault(key, value)
    drifts = drift(state["seed_tasks"], state["channels"][0]["tasks_recorded"])
    if args.drift:
        for d in drifts:
            print(f"{d['id']} {d['field']}: plan={d['plan']} store={d['store']}", file=sys.stderr)
    code = 0
    if args.json:
        out = json.dumps(json_payload(state, viewer, risks, generated_at),
                         indent=2, ensure_ascii=False, sort_keys=True)
    else:
        out = render_html(state, viewer, risks, generated_at, args.lang)
    if args.out:
        Path(args.out).write_text(out if out.endswith("\n") else out + "\n", encoding="utf-8")
        print(f"aimboard: wrote {args.out} ({len(out)} bytes) view of {state['root']} as {viewer}")
    else:
        print(out)
    if args.fail_on_unacked and state["unacked"]:
        code = 4
    if args.fail_on_drift and drifts:
        code = 5
    return code


def cmd_export(args):
    root = Path(args.root)
    as_of = parse_day(args.as_of) or datetime.now(timezone.utc).date()
    generated_at = args.generated_at or now_iso()
    state = load_fabric(root, args.plan or ["plan/*.json"], as_of)
    if not state["channels"]:
        print(f"aimboard: no channels under {root}", file=sys.stderr)
        return 2
    viewer = args.viewer or state["channels"][0]["leader"] or "human"
    if viewer not in state["registry"]:
        print(f"aimboard: unknown viewer '{viewer}'", file=sys.stderr)
        return 2
    tasks, hidden = visible_tasks(state, viewer, gate_channel(state, viewer, {}))
    if args.format == "csv":
        out = export_csv(tasks)
    elif args.format == "ical":
        out = export_ical(tasks, state["milestones"], generated_at)
    else:
        out = json.dumps(json_payload(state, viewer, {}, generated_at), indent=2,
                         ensure_ascii=False, sort_keys=True)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"aimboard: wrote {args.out} ({len(tasks)} item(s), {hidden} withheld, {args.format})")
    else:
        sys.stdout.write(out)
    return 0


def cmd_serve(args):
    """A local server, because a board you have to re-render by hand is a board
    you read once. Every request re-renders from disk, so the page cannot be
    stale - and `--refresh` makes the browser ask again on its own.

    Bound to 127.0.0.1 by default and it writes nothing: it is the same renderer
    behind a socket.

    It also serves the built front-end (web/dist) when there is one, and the JSON
    that front-end reads at /api/state. The gate is applied on the server, before
    serialisation: a browser is not trusted to hide what it was sent.
    """
    import http.server
    from pathlib import Path as _Path

    # web/dist lives beside the package, not under --root: --root is the fabric,
    # this is the application, and conflating them is how a dashboard ends up
    # looking for its own assets inside someone's project directory.
    web = _Path(__file__).resolve().parent.parent / "web" / "dist"
    content_types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                     ".css": "text/css; charset=utf-8", ".json": "application/json",
                     ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
                     ".woff2": "font/woff2", ".map": "application/json"}
    root = Path(args.root)
    as_of = parse_day(args.as_of)

    class Handler(http.server.BaseHTTPRequestHandler):
        def _state(self):
            """One load per request, shared by every endpoint that needs it."""
            now = datetime.now(timezone.utc).date()
            state = load_fabric(root, args.plan or ["plan/*.json"], as_of or now)
            if args.channel:
                state["channels"] = [c for c in state["channels"] if c["id"] in set(args.channel)]
            return state

        def _risks(self):
            risks = {}
            for path in sorted(root.glob("plan/*.json")):
                doc = read_json(path)
                if isinstance(doc, dict):
                    for key, value in doc.items():
                        if isinstance(value, list) and key not in ("tasks", "milestones"):
                            risks.setdefault(key, []).extend(value)
                        elif isinstance(value, dict) and key not in ("tasks", "milestones"):
                            risks.setdefault(key, value)
            return risks

        def _render(self, viewer, refresh):
            now = datetime.now(timezone.utc).date()
            state = load_fabric(root, args.plan or ["plan/*.json"], as_of or now)
            if args.channel:
                state["channels"] = [c for c in state["channels"] if c["id"] in set(args.channel)]
            risks = {}
            for path in sorted(root.glob("plan/*.json")):
                doc = read_json(path)
                if isinstance(doc, dict):
                    for key, value in doc.items():
                        if isinstance(value, list) and key not in ("tasks", "milestones"):
                            risks.setdefault(key, []).extend(value)
                        elif isinstance(value, dict) and key not in ("tasks", "milestones"):
                            risks.setdefault(key, value)
            # No meta refresh. The page is drawn once and then *watched*: the
            # browser polls a cheap digest and offers a refresh only when the
            # record has actually moved, because a board that reloads under your
            # hands is a board that throws away your place in it.
            return render_html(state, viewer, risks, now_iso(), args.lang,
                               digest=fabric_digest(root), poll_ms=refresh)

        def _viewer(self):
            if "as=" in (self.path or ""):
                return parse_qs(self.path.split("?", 1)[1]).get("as", [args.viewer or ""])[0]
            return args.viewer or (load_fabric(root, [], datetime.now(timezone.utc).date())["channels"][0]["leader"])

        def _send(self, body, ctype):
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _asset(self, path):
            """A file from the built front-end, or None. No path escapes it."""
            if not web.exists():
                return None
            target = (web / path.lstrip("/")).resolve()
            if web.resolve() not in target.parents and target != web.resolve():
                return None
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                return None
            mime = content_types.get(target.suffix, "application/octet-stream")
            return target.read_bytes(), mime

        def do_GET(self):
            path = (self.path or "/").split("?")[0]
            try:
                if path == "/api/state":
                    state = self._state()
                    body = json.dumps(json_state(state, self._viewer(), self._risks(), now_iso(),
                                                 digest=fabric_digest(root)),
                                      ensure_ascii=False)
                    self._send(body, "application/json; charset=utf-8")
                    return
                if path == "/api/digest":
                    self._send(json.dumps({"digest": fabric_digest(root), "generated_at": now_iso()}),
                               "application/json")
                    return
                if path == "/api/agents":
                    state = self._state()
                    self._send(json.dumps({"viewer": self._viewer(),
                                           "agents": {k: {"kind": v.get("kind", ""),
                                                          "model": v.get("model", "")}
                                                      for k, v in state["registry"].items()}},
                                          ensure_ascii=False), "application/json; charset=utf-8")
                    return
                if path == "/state.json":
                    payload = json.dumps({"digest": fabric_digest(root), "generated_at": now_iso()})
                    raw = payload.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if path in ("/", "/index.html", "/board.html"):
                    asset = self._asset("index.html")
                    if asset:
                        body, ctype = asset[0], asset[1]
                    else:
                        body, ctype = self._render(self._viewer(), args.refresh), "text/html; charset=utf-8"
                elif path == "/board.json":
                    state = load_fabric(root, args.plan or ["plan/*.json"],
                                        as_of or datetime.now(timezone.utc).date())
                    body = json.dumps(json_payload(state, self._viewer(), {}, now_iso()),
                                      indent=2, ensure_ascii=False, sort_keys=True)
                    ctype = "application/json"
                elif path == "/board.csv":
                    state = load_fabric(root, args.plan or ["plan/*.json"], as_of or datetime.now(timezone.utc).date())
                    tasks, _ = visible_tasks(state, self._viewer(), gate_channel(state, self._viewer(), {}))
                    body, ctype = export_csv(tasks), "text/csv"
                elif path == "/board.ics":
                    state = load_fabric(root, args.plan or ["plan/*.json"], as_of or datetime.now(timezone.utc).date())
                    tasks, _ = visible_tasks(state, self._viewer(), gate_channel(state, self._viewer(), {}))
                    body, ctype = export_ical(tasks, state["milestones"], now_iso()), "text/calendar"
                else:
                    asset = self._asset(path)
                    if not asset:
                        # a single-page app answers its own routes; anything that
                        # is not an asset and not an API path is the app's
                        asset = self._asset("index.html")
                    if not asset:
                        self.send_error(404)
                        return
                    body, ctype = asset[0], asset[1]
                self._send(body, ctype)
            except BrokenPipeError:
                pass
            except Exception as exc:                      # a broken render is a 500, not a dead server
                self.send_error(500, str(exc)[:200])

        def log_message(self, fmt, *a):
            if args.verbose:
                print(f"aimboard: {self.address_string()} {fmt % a}", file=sys.stderr)

    server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    host, port = server.server_address[0], server.server_address[1]
    print(f"aimboard: serving {root} on http://{host}:{port}/  as {args.viewer or 'the channel leader'}"
          + (f", polling for change every {args.refresh}s and offering a refresh rather than"
             f" forcing one" if args.refresh else ""))
    print(f"aimboard: front-end {'web/dist (vue)' if (web / 'index.html').exists() else 'server-rendered html (no web/dist; run npm --prefix web run build)'}"
          f"; json at /api/state; ?as=<agent> for that agent's view")
    print("aimboard: ctrl-c to stop. Views: /#/kanban /#/gantt /#/chat /#/reports /#/barrier /#/plan")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\naimboard: stopped")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="aimboard",
        description="Read-only dashboard over an aim fabric: kanban, gantt, chat, barrier audit.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render the board (HTML by default, --json for the fold)")
    r.add_argument("--root", default=os.environ.get("AIM_ROOT", "/root/tmp/agent-im"))
    r.add_argument("--channel", action="append", help="limit to a channel (repeatable)")
    r.add_argument("--as", dest="viewer", default=None,
                   help="whose view this is; defaults to the channel leader. A participant in a "
                        "divergence phase cannot see peer seals or peer drafts.")
    r.add_argument("--out", default=None, help="write here instead of stdout")
    r.add_argument("--json", action="store_true", help="emit the folded state instead of HTML")
    r.add_argument("--lang", default="en", choices=sorted(LABELS))
    r.add_argument("--as-of", default=None, help="the date the board is drawn for (default: today UTC)")
    r.add_argument("--generated-at", default=None, help="stamp, for reproducible renders")
    r.add_argument("--plan", action="append", default=None, help="plan glob (default plan/*.json)")
    r.add_argument("--drift", action="store_true", help="print plan-versus-store disagreements")
    r.add_argument("--fail-on-unacked", action="store_true", help="exit 4 if a demanded ack is outstanding")
    r.add_argument("--fail-on-drift", action="store_true", help="exit 5 if the plan and the store disagree")
    r.set_defaults(func=cmd_render)
    e = sub.add_parser("export", help="same fold, for a foreign tool: csv, ical or json")
    e.add_argument("--root", default=os.environ.get("AIM_ROOT", "/root/tmp/agent-im"))
    e.add_argument("--format", default="csv", choices=["csv", "ical", "json"])
    e.add_argument("--out", default=None)
    e.add_argument("--as", dest="viewer", default=None)
    e.add_argument("--as-of", default=None)
    e.add_argument("--generated-at", default=None)
    e.add_argument("--plan", action="append", default=None)
    e.set_defaults(func=cmd_export)
    v = sub.add_parser("serve", help="a local, always-fresh view of the board")
    v.add_argument("--root", default=os.environ.get("AIM_ROOT", "/root/tmp/agent-im"))
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8777)
    v.add_argument("--as", dest="viewer", default=None)
    v.add_argument("--channel", action="append", default=None)
    v.add_argument("--lang", default="en", choices=sorted(LABELS))
    v.add_argument("--as-of", default=None)
    v.add_argument("--refresh", type=int, default=20,
                   help="seconds between change checks; the page offers a refresh instead of "
                        "taking itself away from you (0 disables the check)")
    v.add_argument("--plan", action="append", default=None)
    v.add_argument("--verbose", action="store_true")
    v.set_defaults(func=cmd_serve)
    args = parser.parse_args(argv)
    return args.func(args)
