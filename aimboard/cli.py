"""The command line."""
import argparse
import errno
import json
import subprocess
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs
from .const import LABELS
from .api import payload as json_state
from .exporters import export_csv, export_ical, json_payload
from .fabric import fabric_digest, load_fabric
from .revision import describe as describe_revision
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


def canonical_port():
    """The one port this project's board is served on.

    The leader's instruction, verbatim: "要求基础设施必须绑定一个端口号啊，如果那个
    端口被占用，就调查杀死他，而不是经常变换使用". A moving port is a movable
    interface: every probe script, every bookmark, every URL in a report and every
    peer that learned where the board lives has to be updated by hand, and the
    hand that forgets is the one that files a finding against the wrong build.

    Set AIM_PORT to override, which is a deliberate act, not a fallback.
    """
    raw = os.environ.get("AIM_PORT", "").strip()
    if raw.isdigit():
        return int(raw)
    return 8777


def port_holder(port):
    """(pid, cmdline) of the process listening on `port`, or None.

    /proc rather than lsof/ss: this must work in a container with no lsof, and it
    must not shell out. Only the listening socket is wanted, so a client
    connected *to* the port is not mistaken for the holder.
    """
    inodes = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            f = line.split()
            if len(f) < 10:
                continue
            try:
                local = int(f[1].split(":")[1], 16)
            except (IndexError, ValueError):
                continue
            if local == port and f[3] == "0A":   # 0A = LISTEN
                inodes.add(f[9])
    if not inodes:
        return None
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            for fd in (entry / "fd").iterdir():
                try:
                    target = os.readlink(fd)
                except OSError:
                    continue
                if target.startswith("socket:[") and target[8:-1] in inodes:
                    cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").strip()
                    return int(entry.name), cmd.decode("utf-8", "replace")
        except OSError:
            continue
    return None


def take_port(host, port, root, verbose=False):
    """Take the canonical port, replacing our own stale server if it holds it.

    The rule is asymmetric on purpose. A previous `aimboard serve` for this same
    checkout is ours and is replaced: it holds a port the project declared, it is
    serving a bundle that may already be stale, and asking a human to hunt it
    down is how a project ends up with three boards on three ports and no idea
    which one answered.

    A process that is not ours is not killed. Reporting who holds it and refusing
    is the honest outcome; killing a stranger's process to take a port is not a
    convenience this tool should have.
    """
    holder = port_holder(port)
    if not holder:
        return None
    pid, cmd = holder
    # Ownership by working directory, not by the command line. A server started
    # as `python3 -u bin/aimboard.py serve` names no absolute path, so matching
    # the root against argv refuses to replace our *own* server -- measured: the
    # first version of this function did exactly that, and printed "that is not
    # an aimboard serve for /root/tmp/agent-im" about a server that was.
    try:
        cwd = os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        cwd = ""
    ours = "aimboard" in cmd and (cwd == str(root) or str(root) in cmd)
    if not ours and not getattr(take_port, "force", False):
        raise SystemExit(
            f"aimboard: port {port} is held by pid {pid}: {cmd or '(no cmdline)'}\n"
            f"         that is not an `aimboard serve` for {root}, so this will not kill it.\n"
            f"         Free the port, or run with AIM_PORT=<other> if you really mean to move."
        )
    import signal
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        raise SystemExit(f"aimboard: could not take port {port} from pid {pid}: {exc}")
    for _ in range(40):
        time.sleep(0.1)
        if not port_holder(port):
            print(f"aimboard: took port {port} from a stale `aimboard serve` (pid {pid})")
            return holder
    os.kill(pid, signal.SIGKILL)
    time.sleep(0.3)
    print(f"aimboard: killed pid {pid} which would not release port {port}")
    return holder


def cmd_serve(args):
    """A local server, because a board you have to re-render by hand is a board
    you read once. Every request re-renders from disk, so the page cannot be
    stale - and `--refresh` makes the browser ask again on its own.

    Bound to 127.0.0.1 by default and it writes nothing: it is the same renderer
    behind a socket.

    It also serves the built front-end (web/dist) when there is one, and the JSON
    that front-end reads at /api/state. The gate is applied on the server, before
    serialisation: a browser is not trusted to hide what it was sent.

    With --allow-write it also accepts POST /api/command, which runs one allowlisted
    `aim` command and returns its stdout, stderr and exit code. The dashboard does
    not implement the write discipline; it *invokes* it, so a write from the browser
    lands in the ledger with a refusal recorded if the tool refused, exactly as if it
    had been typed. Three things are not negotiable here: no shell (argv only), the
    identity is the server's own and never the request's (design/06 R1), and the
    request must come from this origin, so a page the leader happens to have open
    cannot quietly write into their fabric.
    """
    import http.server
    from pathlib import Path as _Path

    # web/dist lives beside the package, not under --root: --root is the fabric,
    # this is the application, and conflating them is how a dashboard ends up
    # looking for its own assets inside someone's project directory.
    web = _Path(__file__).resolve().parent.parent / "web" / "dist"
    aim_bin = _Path(__file__).resolve().parent.parent / "bin" / "aim"
    # The dashboard is a *client* of the one writer, never a second one. These are
    # the verbs it may hand to `bin/aim`; anything else is refused here, before a
    # subprocess exists. A write that cannot be expressed as a command the leader
    # could have typed is a write this project does not want.
    # Commands, not verbs: `task publish` is admitted by `task`, and a bare
    # `publish` in this set would be an entry for something that does not exist.
    writable = {"say", "push", "confirm", "task", "advance", "request-advance", "reveal"}
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

        def _writer(self):
            """Who a write from this dashboard is from. Never the query string.

            design/06 R1: `?as=` chooses whose eyes you read through, which is a
            borrowed view and costs nothing. The same parameter choosing whose
            hands you write with is forgery -- the record would say the leader
            spoke when the leader did not, and a URL is not a credential. So a
            write is from the identity the server was started as, and a caller
            who wants a different one starts a different server.
            """
            return args.viewer or (load_fabric(root, [], datetime.now(timezone.utc).date())["channels"][0]["leader"])

        def _origin_ok(self):
            """A cross-origin page must not be able to drive this, even blind."""
            origin = self.headers.get("Origin") or self.headers.get("Referer") or ""
            if not origin:
                return False
            host = self.headers.get("Host") or f"127.0.0.1:{port}"
            allowed = {f"http://{host}", f"http://localhost:{port}", f"http://127.0.0.1:{port}"}
            return any(origin == a or origin.startswith(a + "/") for a in allowed)

        def _public_configs(self):
            """Flat [(task, config)] of every doorbell config, for the push ops.

            The module's push operations take a flat list of (task, config)
            pairs, which is the shape a foreign client implies (a config is
            addressed by task). Folding `push.jsonl` here, next to the fabric
            load, keeps the one place that knows the wire. A config whose record
            was superseded by a later append is dropped the same way the module's
            own read would drop it (newest state per config id).
            """
            from json import loads as _loads
            live = {}
            if (root / "channels").is_dir():
                for path in sorted((root / "channels").glob("*/push.jsonl")):
                    try:
                        recs = [_loads(l) for l in path.read_text().splitlines() if l.strip()]
                    except (OSError, ValueError):
                        continue
                    for r in recs:
                        if r.get("event") == "deleted":
                            live.pop((r.get("task"), r.get("configId")), None)
                            continue
                        if r.get("event") == "doorbell_created":
                            live[(r.get("task"), r.get("configId"))] = r
            return [(task, c) for (task, _cid), c in live.items()]

        def _rpc_POST(self):
            """Serve the A2A JSON-RPC surface at /rpc (T-0122)."""
            try:
                length = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                self._send(json.dumps({"jsonrpc": "2.0", "id": None,
                                       "error": {"code": -32700, "message": "Parse error"}}),
                           "application/json; charset=utf-8")
                return
            method = req.get("method") or ""
            params = req.get("params") or {}
            try:
                sys.path.insert(0, str(aim_bin.resolve().parent.parent))
                from aimboard.a2a import handle_rpc
            except Exception as exc:
                self._send(json.dumps({"jsonrpc": "2.0",
                                       "id": req.get("id"),
                                       "error": {"code": -32004, "message": f"Unsupported operation: {exc}"}}),
                           "application/json; charset=utf-8")
                return
            state = self._state()
            response, mime = handle_rpc(
                method, dict(params) if isinstance(params, dict) else {},
                request_id=req.get("id", 1),
                viewer=self._viewer(),
                tasks=state.get("tasks", {}),
                channels=state.get("channels", []),
                registry=state.get("registry", {}),
                configs=self._public_configs(),
            )
            if mime == "text/event-stream":
                # One honest event, then close: the stream contract is honoured
                # by its content-type, and a client that opened an SSE reader
                # gets the error as the event it expects, not a JSON body it
                # would hang on forever.
                body = f"data: {json.dumps(response, ensure_ascii=False)}\n\n"
                header = "text/event-stream; charset=utf-8"
            else:
                body = json.dumps(response, ensure_ascii=False)
                header = "application/json; charset=utf-8"
            self._send(body, header)

        def do_POST(self):
            path = (self.path or "/").split("?")[0]
            # The A2A JSON-RPC surface (T-0122). Seven operations route to their
            # real backing functions; the four that have none answer honestly
            # with UnsupportedOperationError. The viewer is the server's own
            # identity, never a field in the request, which is the same rule
            # /api/command and mcp.py keep: a caller that could name its own
            # author could forge one. Note the allow-write gate deliberately does
            # NOT apply here — A2A callers are the fabric's peers, not the
            # dashboard browser, and §3.4 makes `pushNotifications` only
            # meaningful if CreateTaskPushNotificationConfig can actually be
            # called. This is the one judgement in the surface; it is stated in
            # design/07 and re-evaluated there.
            if path == "/rpc":
                self._rpc_POST()
                return
            if path != "/api/command":
                self.send_error(404)
                return
            if not args.allow_write:
                self._send(json.dumps({"ok": False, "rc": 126,
                                       "stderr": "this server was started without --allow-write, "
                                                 "so the dashboard can read and cannot write"}),
                           "application/json; charset=utf-8")
                return
            if not self._origin_ok():
                self._send(json.dumps({"ok": False, "rc": 126,
                                       "stderr": "refused: the request did not come from this origin"}),
                           "application/json; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except Exception as exc:
                self._send(json.dumps({"ok": False, "rc": 2, "stderr": f"bad request: {exc}"}),
                           "application/json; charset=utf-8")
                return
            argv = [str(x) for x in (body.get("argv") or [])]
            # Not the query string and not the body: see `_writer`. Any --as in
            # argv is dropped below and the server's own identity appended after
            # it, so there is one place in this file where a write's author is
            # decided and no argument can reach it.
            viewer = self._writer() or "<agent-id>"
            if not argv or argv[0] not in writable:
                self._send(json.dumps({"ok": False, "rc": 126,
                                       "stderr": f"refused: {argv[:1] or ['(empty)']} is not in the dashboard's "
                                                 f"allowlist: {', '.join(sorted(writable))}"}),
                           "application/json; charset=utf-8")
                return
            # identity is the server's to assert, not the caller's to claim: any
            # --as in the request is dropped and the viewer's is appended
            cleaned, skip = [], False
            for a in argv:
                if skip:
                    skip = False
                    continue
                if a == "--as":
                    skip = True
                    continue
                cleaned.append(a)
            argv = cleaned + ["--as", str(viewer)]
            # `bin/aim` resolves its fabric from AIM_ROOT, not from the cwd and not
            # from an argument. Serving somebody's fabric while shelling out to the
            # default one would append this write to the wrong record -- the exact
            # failure this endpoint exists to make impossible. So the root the
            # server was told to serve is the root the command runs against.
            env = os.environ | {"AIM_ROOT": str(root)}
            try:
                done = subprocess.run([str(aim_bin), *argv], capture_output=True, text=True,
                                      timeout=30, env=env)
                self._send(json.dumps({"ok": done.returncode == 0, "rc": done.returncode,
                                       "argv": argv, "stdout": done.stdout, "stderr": done.stderr},
                                      ensure_ascii=False), "application/json; charset=utf-8")
            except subprocess.TimeoutExpired:
                self._send(json.dumps({"ok": False, "rc": 124, "stderr": "the command did not finish in 30s"}),
                           "application/json; charset=utf-8")
            except Exception as exc:
                self._send(json.dumps({"ok": False, "rc": 1, "stderr": str(exc)}),
                           "application/json; charset=utf-8")

        def _send(self, body, ctype, status=200):
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(status)
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
                                                 digest=fabric_digest(root),
                                                 write={"enabled": bool(args.allow_write),
                                                        "as": self._writer() if args.allow_write else ""}),
                                      ensure_ascii=False)
                    self._send(body, "application/json; charset=utf-8")
                    return
                if path == "/api/digest":
                    self._send(json.dumps({"digest": fabric_digest(root), "generated_at": now_iso()}),
                               "application/json")
                    return
                if path == "/api/revision":
                    self._send(json.dumps(describe_revision(root, web), ensure_ascii=False),
                               "application/json; charset=utf-8")
                    return
                if path.startswith("/api/"):
                    # An unhandled API path is a 404, never the app.
                    #
                    # Measured by a peer agent on its first day: `/api/flow`
                    # returned index.html with HTTP 200 -- the requested endpoint
                    # did not exist, and the answer said "fine". A 404 is a fact;
                    # a 200 carrying HTML is a lie, and the consumer that trusts it
                    # (an orchestrator polling for a flow series) folds the SPA's
                    # markup as if it were data. The comment below this used to
                    # claim the fallback excluded API paths and the code did not;
                    # that gap is the whole bug.
                    self._send(json.dumps({
                        "error": "no such endpoint",
                        "path": path,
                        "endpoints": ["/api/state", "/api/digest", "/api/agents",
                                      "/api/revision", "/api/command (POST, --allow-write)"],
                    }, ensure_ascii=False), "application/json; charset=utf-8", status=404)
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

    try:
        server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        if exc.errno not in (errno.EADDRINUSE, errno.EACCES):
            raise
        take_port(args.host, args.port, root)
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
    v.add_argument("--port", type=int, default=canonical_port(),
                   help="canonical port; a stale `aimboard serve` holding it is replaced, "
                        "not avoided (AIM_PORT to move it deliberately)")
    v.add_argument("--as", dest="viewer", default=None)
    v.add_argument("--channel", action="append", default=None)
    v.add_argument("--lang", default="en", choices=sorted(LABELS))
    v.add_argument("--as-of", default=None)
    v.add_argument("--refresh", type=int, default=20,
                   help="seconds between change checks; the page offers a refresh instead of "
                        "taking itself away from you (0 disables the check)")
    v.add_argument("--plan", action="append", default=None)
    v.add_argument("--allow-write", action="store_true",
                   help="accept POST /api/command, which runs an allowlisted aim command as the "
                        "identity this server was started as (--as, default the channel leader), "
                        "never as whoever the request names. Off by default: a dashboard that can "
                        "write is a second client of the write discipline, and the leader should "
                        "have to say yes to that out loud.")
    v.add_argument("--verbose", action="store_true")
    v.set_defaults(func=cmd_serve)
    args = parser.parse_args(argv)
    return args.func(args)
