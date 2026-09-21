#!/usr/bin/env python3
"""Tests for aimboard: the board must be a view of the record, and nothing else.

Two of these are the reason the file exists rather than a hand-check:

  * the **absence** tests - a participant in a divergence phase must not be able
    to reach a peer's sealed claim or draft task through the dashboard. Not
    hidden with CSS: absent from the bytes, because a view that is one grep away
    from what `aim` refuses to show is a route around the refusal;
  * the **read-only** test - the renderer must not touch a single byte of the
    fabric. A renderer that can write fabric state is a second implementation of
    the write discipline, and this project has already measured where that leads.

Run: python3 tests/test_aimboard.py     (exit code = number of failures)
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BOARD = HERE / "bin" / "aimboard.py"
results = []

PEER_DRAFT = "PEER-DRAFT-SECRET-omega"
PEER_SEAL = "PEER-SEAL-SECRET-omega"
OWN_SEAL = "OWN-SEAL-CLAIM-alpha"
ROOM_DRAFT = "ROOM-DRAFT-SECRET-omega"
MAIL_BODY = "MAIL-BODY-SECRET-omega"
XSS = "<script>alert('xss')</script>"


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def jsonl(path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")


def chained(recs):
    """The same chain `append_chained` writes: `prev` hashes the previous record.

    A hand-written ledger record with no `hash` is not a record this fabric can
    extend -- `append_chained` refuses rather than guessing, which is right, and
    which means a fixture that skips the chain can never observe a recorded
    refusal. Keeping the fixture honest here is the difference between testing
    the ledger and testing a file that looks like one.
    """
    out, prev = [], "genesis"
    for rec in recs:
        rec = {**rec, "prev": prev}
        rec["hash"] = hashlib.sha256(json.dumps(
            {k: v for k, v in rec.items() if k != "hash"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        prev = rec["hash"]
        out.append(rec)
    return out


def fixture(root, phase="SEALED_DIVERGENT"):
    (root / "registry.json").parent.mkdir(parents=True, exist_ok=True)
    write(root / "registry.json", {"agents": {
        "human": {"id": "human", "kind": "human"},
        "codex": {"id": "codex", "kind": "codex"},
        "claude-session1": {"id": "claude-session1", "kind": "claude"},
        "claude-session2": {"id": "claude-session2", "kind": "claude"},
    }})
    ch = root / "channels" / "hello"
    write(ch / "manifest.json", {
        "id": "hello", "topic": "fixture", "leader": "human", "synthesizer": "",
        "participants": ["codex", "claude-session1"],
        "barrier": {"phase": phase, "round": 0, "history": [{"phase": "SEALED_DIVERGENT", "by": "human"}]},
    })
    write(ch / "seals" / "claude-session1.json",
          {"agent": "claude-session1", "ts": "2026-09-21T00:00:01Z", "digest": "aaaa1111bbbb",
           "private_log_hashes": ["x"],
           "claims": [{"id": "c1", "claim": OWN_SEAL, "confidence": 0.9, "kill_if": "k1"}]})
    write(ch / "seals" / "codex.json",
          {"agent": "codex", "ts": "2026-09-21T00:00:02Z", "digest": "cccc2222dddd",
           "private_log_hashes": ["y"],
           "claims": [{"id": "c2", "claim": PEER_SEAL, "confidence": 0.9, "kill_if": "k2"}]})
    jsonl(ch / "tasks.jsonl", [
        {"ts": "2026-09-21T00:00:01Z", "event": "task.created", "id": "T-9001", "actor": "codex",
         "title": PEER_DRAFT, "owner": "codex", "status": "doing", "visibility": "draft",
         "start": "2026-09-21", "due": "2026-09-23", "blocked_by": [], "milestone": "M9"},
        {"ts": "2026-09-21T00:00:02Z", "event": "task.created", "id": "T-9002", "actor": "claude-session1",
         "title": "a published item", "owner": "claude-session1", "status": "done",
         "visibility": "published", "start": "2026-09-21", "due": "2026-09-22",
         "blocked_by": ["T-9001"], "milestone": "M9"},
        {"ts": "2026-09-21T00:00:03Z", "event": "task.created", "id": "T-9003", "actor": "codex",
         "title": XSS, "owner": "codex", "status": "review", "visibility": "published",
         "start": "2026-09-22", "due": "2026-09-25", "blocked_by": [], "milestone": "M9"},
    ])
    jsonl(ch / "rooms" / "dev.jsonl", [
        {"ts": "2026-09-21T00:00:04Z", "agent": "codex", "body": ROOM_DRAFT,
         "mentions": ["claude-session1"], "hash": "h1"},
    ])
    write(ch / "rooms" / "dev.json", {"id": "dev", "topic": "fixture room", "visibility": "draft"})
    write(ch / "rooms" / "dev.cursors.json", {"claude-session1": {"last_hash": "", "ts": ""}})
    jsonl(ch / "ledger.jsonl", chained([
        {"ts": "2026-09-21T00:00:05Z", "event": "seal", "agent": "claude-session1", "digest": "aaaa1111bbbb"},
        {"ts": "2026-09-21T00:00:06Z", "event": "refusal", "agent": "codex", "action": "read_others",
         "class": "barrier", "phase": "SEALED_DIVERGENT", "reason": "REFUSED: no"},
    ]))
    jsonl(ch / "log.jsonl", [{"ts": "2026-09-21T00:00:07Z", "from": "codex", "body": "on the record"}])
    jsonl(ch / "private" / "codex.jsonl",
          [{"ts": "2026-09-21T00:00:06Z", "body": "PRIVATE-REASONING-SECRET"}])
    write(root / "outbox" / "codex" / "20260921T000008.000Z-claude-session1.json",
          {"msg_id": "20260921T000008.000Z-claude-session1", "from": "claude-session1", "to": "codex",
           "ts": "2026-09-21T00:00:08Z", "subject": "hi", "body": MAIL_BODY, "bytes": len(MAIL_BODY),
           "body_sha256": hashlib.sha256(MAIL_BODY.encode()).hexdigest(), "ack_required": True})
    write(root / "plan" / "plan.json", {
        "as_of": "2026-09-21",
        "milestones": [{"id": "M9", "name": "fixture milestone", "due": "2026-09-24",
                        "accept": "n/a"}],
        "tasks": [
            {"id": "T-9001", "title": PEER_DRAFT, "owner": "codex", "status": "backlog",
             "visibility": "draft", "start": "2026-09-21", "due": "2026-09-23", "milestone": "M9"},
            {"id": "T-9004", "title": "a seed-only item", "owner": "claude-session1",
             "status": "ready", "visibility": "published", "start": "2026-09-23",
             "due": "2026-09-26", "milestone": "M9"},
        ],
    })


def snapshot(root):
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def render(root, out, *extra):
    return subprocess.run(
        [sys.executable, str(BOARD), "render", "--root", str(root), "--out", str(out),
         "--as-of", "2026-09-21", "--generated-at", "2026-09-21T00:00:00.000Z", *extra],
        capture_output=True, text=True, timeout=120)


def main():
    work = Path(tempfile.mkdtemp(prefix="aimboard-test-"))
    try:
        root = work / "fabric"
        fixture(root)

        print("== the renderer as the leader (the default view) ==")
        html_path = work / "leader.html"
        before = snapshot(root)
        p = render(root, html_path)
        after = snapshot(root)
        check("render exits 0", p.returncode == 0, p.stderr)
        check("the renderer wrote only the file it was asked for", before == after,
              "fabric changed: " + ", ".join(sorted(set(after) ^ set(before))) or
              "content changed")
        html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        check("every kanban column is present",
              all(f'data-col="{s}"' in html for s in
                  ["backlog", "ready", "doing", "review", "done", "blocked", "dropped"]))
        check("the published store task is on the board", "a published item" in html)
        check("the seed-only task is on the board", "a seed-only item" in html)
        check("provenance is labelled per card", "plan seed" in html)
        check("the gantt draws bars for dated work", html.count('class="bar s-') >= 3)
        check("the gantt draws the dependency edge", '<path class="dep"' in html)
        check("the gantt marks the milestone", 'class="msdiamond"' in html)
        check("the gantt marks today", 'class="today"' in html)
        check("the barrier panel counts the refusal", "read_others" in html)
        check("the seal claims of the leader view are rendered", PEER_SEAL in html and OWN_SEAL in html)
        check("the draft task is rendered for the leader", PEER_DRAFT in html)
        check("chain verification is reported", "chain verification" in html)
        check("the board names the phase it was drawn in", "SEALED_DIVERGENT" in html)

        print("== the renderer as a participant inside the barrier ==")
        peer = work / "claude.html"
        p = render(root, peer, "--as", "claude-session1")
        # A render that fails should say why, rather than raising FileNotFoundError
        # three lines later and hiding the reason it failed.
        check("participant view renders", p.returncode == 0, p.stderr or p.stdout)
        if p.returncode != 0:
            print("  stderr:", (p.stderr or p.stdout)[-800:])
            return finish()
        peer_html = peer.read_text(encoding="utf-8")
        check("ABSENCE: the peer seal claim is not in the bytes", PEER_SEAL not in peer_html,
              "the dashboard is a route around the cross-read refusal")
        check("ABSENCE: the peer draft task is not in the bytes", PEER_DRAFT not in peer_html)
        check("ABSENCE: the peer draft room message is not in the bytes", ROOM_DRAFT not in peer_html)
        check("the viewer's own seal claim is still visible", OWN_SEAL in peer_html)
        check("withheld items are declared, not silently dropped", "withheld" in peer_html)
        print("== the conversation, and who may read it ==")
        check("the leader sees the message body", MAIL_BODY in html,
              "the leader reads the conversations they are steering")
        check("the recipient sees the message body", MAIL_BODY in peer_html)
        third = work / "third.html"
        render(root, third, "--as", "claude-session2")
        third_html = third.read_text(encoding="utf-8")
        # T-0041: a registered agent who is not a participant of this channel is
        # refused by `aim` outright ("'outsider' is not a participant"), so the
        # renderer must not be the route around that refusal. Every gate branch
        # used to test membership of `participants`, which meant a stranger took
        # the else on all three and was served the bytes.
        stranger = work / "stranger.html"
        render(root, stranger, "--as", "claude-session2")
        stranger_html = stranger.read_text(encoding="utf-8")
        check("ABSENCE: a registered non-participant gets no peer draft", PEER_DRAFT not in stranger_html)
        check("ABSENCE: a registered non-participant gets no peer seal", PEER_SEAL not in stranger_html)
        check("ABSENCE: a registered non-participant gets no draft room message", ROOM_DRAFT not in stranger_html)
        p = subprocess.run([sys.executable, str(BOARD), "render", "--root", str(root), "--json",
                            "--as", "claude-session2"], capture_output=True, text=True, timeout=120)
        check("ABSENCE: nor through the json, which is the same gate one layer down",
              PEER_DRAFT not in p.stdout and PEER_SEAL not in p.stdout)
        check("ABSENCE: a bystander sees neither end of someone else's mail",
              MAIL_BODY not in third_html, "claude-session2 is not on this message")
        check("the bystander's board says how much is withheld", "withheld from this view" in third_html)
        check("the unacked handoff is visible as unacked",
              "20260921T000008" in html and "no ack" in html)
        check("peer private reasoning is never rendered",
              "PRIVATE-REASONING-SECRET" not in html)

        print("== escaping ==")
        check("a script tag in a title renders as text", "&lt;script&gt;" in html)
        check("a script tag in a title does not open an element", "<script>alert" not in html)

        print("== the machine-readable view ==")
        p = subprocess.run([sys.executable, str(BOARD), "render", "--root", str(root), "--json"],
                           capture_output=True, text=True, timeout=120)
        doc = json.loads(p.stdout)
        check("--json exits 0", p.returncode == 0, p.stderr)
        check("--json folds the same tasks the html shows",
              "T-9001" in doc["tasks"] and "T-9004" in doc["tasks"])
        check("--json reports the phase", doc["phases"]["hello"]["phase"] == "SEALED_DIVERGENT")
        check("--json reports the withheld count", doc["withheld_tasks"] == 0)
        p = subprocess.run([sys.executable, str(BOARD), "render", "--root", str(root), "--json",
                            "--as", "claude-session1"], capture_output=True, text=True, timeout=120)
        doc = json.loads(p.stdout)
        check("--json honours the gate too", doc["withheld_tasks"] == 1 and PEER_DRAFT not in p.stdout)

        print("== determinism ==")
        a, b = work / "a.html", work / "b.html"
        render(root, a)
        render(root, b)
        check("two renders with the same flags are byte-identical", a.read_bytes() == b.read_bytes())

        print("== exit codes as a gate ==")
        p = render(root, work / "u.html", "--fail-on-unacked")
        check("--fail-on-unacked exits 4 when an ack is owed", p.returncode == 4, f"got {p.returncode}")
        p = render(root, work / "d.html", "--fail-on-drift")
        check("--fail-on-drift exits 5 when the plan and the store disagree", p.returncode == 5,
              f"got {p.returncode}")
        p = render(root, work / "n.html", "--as", "nobody")
        check("an unregistered viewer is refused", p.returncode == 2)
        p = render(root, work / "c.html", "--channel", "nosuch")
        check("an unknown channel is refused", p.returncode == 2)

        print("== reports ==")
        check("the burndown is drawn when the store has history", 'class="burndown"' in html)
        check("the burndown says what it does not cover", "plan seed only" in html)
        check("cycle time is reported", "median cycle time" in html)
        check("open blockers are listed", "what is waiting on what" in html)

        print("== export ==")
        csv_path, ics_path = work / "b.csv", work / "b.ics"
        p = subprocess.run([sys.executable, str(BOARD), "export", "--root", str(root),
                            "--format", "csv", "--out", str(csv_path)],
                           capture_output=True, text=True, timeout=120)
        rows = csv_path.read_text(encoding="utf-8").strip().splitlines()
        check("csv export exits 0", p.returncode == 0, p.stderr)
        check("csv has a header and one row per visible work item", len(rows) == 5, f"{len(rows)} rows")
        check("csv quotes a title containing a comma", all(r.count('"') % 2 == 0 for r in rows))
        p = subprocess.run([sys.executable, str(BOARD), "export", "--root", str(root),
                            "--format", "csv", "--as", "claude-session1"],
                           capture_output=True, text=True, timeout=120)
        check("ABSENCE: csv export honours the gate", PEER_DRAFT not in p.stdout)
        p = subprocess.run([sys.executable, str(BOARD), "export", "--root", str(root),
                            "--format", "ical", "--out", str(ics_path)],
                           capture_output=True, text=True, timeout=120)
        ics = ics_path.read_bytes().decode("utf-8")   # bytes: read_text would fold CRLF to LF
        check("ical export exits 0", p.returncode == 0, p.stderr)
        check("ical has a VEVENT per dated item plus each milestone",
              ics.count("BEGIN:VEVENT") >= 5, str(ics.count("BEGIN:VEVENT")))
        check("ical dates are all-day, so no timezone can shift them",
              "DTSTART;VALUE=DATE:" in ics and "DTSTART:" not in ics)
        check("ical is CRLF-terminated as the format requires", ics.endswith("END:VCALENDAR\r\n"))
        print("== serve ==")
        # A second route to the same renderer is a second chance to leak: a gate
        # applied in `render_html` and forgotten in the handler is exactly the
        # shape of bug this file exists to catch. Checked before the barrier
        # opens, because a check made after it opens asserts nothing.
        import urllib.request
        import urllib.error
        # -u matters: the server prints the address it bound to stdout, and a
        # block-buffered pipe means the test waits for a line the server has
        # already "sent". Reading forever for an address that is sitting in a
        # buffer is a test that hangs, not a test that fails.
        srv = subprocess.Popen([sys.executable, "-u", str(BOARD), "serve", "--root", str(root),
                                "--port", "0", "--as-of", "2026-09-21"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            url, said, deadline = None, [], time.time() + 30
            while time.time() < deadline:
                said.append(srv.stdout.readline())
                if srv.poll() is not None:
                    break
                m = re.search(r"http://[\d.]+:(\d+)/", "".join(said))
                if m:
                    url = f"http://127.0.0.1:{m.group(1)}"
                    break
            check("serve announces the address it actually bound",
                  url is not None, "".join(said)[-300:])
            if url:
                body = urllib.request.urlopen(url + "/", timeout=20).read().decode()
                # `/` is now the built front-end: a shell that fetches the record,
                # rather than a page with the record baked into it. So the shell
                # must carry no board data, and the API must carry all of it.
                check("serve answers / with the front-end shell", 'id="app"' in body)
                check("the shell carries no board data at all",
                      PEER_DRAFT not in body and "T-9001" not in body and MAIL_BODY not in body)
                doc = json.loads(urllib.request.urlopen(url + "/api/state", timeout=20).read().decode())
                check("serve answers /api/state with the folded board",
                      "T-9001" in doc["tasks"] and doc["statuses"])
                check("the api says what it withheld rather than hiding the count",
                      "withheld_tasks" in doc)
                legacy = json.loads(urllib.request.urlopen(url + "/board.json", timeout=20).read().decode())
                check("serve still answers /board.json for a foreign tool",
                      "tasks" in legacy and "phases" in legacy)
                gated = urllib.request.urlopen(url + "/?as=claude-session1", timeout=20).read().decode()
                check("ABSENCE: the served view honours the gate too",
                      PEER_SEAL not in gated and PEER_DRAFT not in gated)
                stranger_view = urllib.request.urlopen(url + "/?as=claude-session2", timeout=20).read().decode()
                check("ABSENCE: a stranger is refused the same bytes over http",
                      PEER_SEAL not in stranger_view and PEER_DRAFT not in stranger_view)
                js = json.loads(urllib.request.urlopen(url + "/api/state?as=claude-session2", timeout=20).read().decode())
                check("ABSENCE: the api the front-end reads applies the gate server-side",
                      PEER_DRAFT not in json.dumps(js) and PEER_SEAL not in json.dumps(js))
                check("serve answers /board.ics",
                      "BEGIN:VCALENDAR" in urllib.request.urlopen(url + "/board.ics", timeout=20).read().decode())
        finally:
            srv.terminate()
            srv.wait(timeout=20)

        print("== the write path from a browser (T-0141) ==")
        # A dashboard that can write is a second writer unless it does not write
        # at all and runs the one that already exists instead. So these checks are
        # not "can the browser write" -- that is the easy half -- but "can the
        # browser write *anything*, as *anyone*". Every check below is a way the
        # endpoint could be a second implementation of the write discipline.
        #
        # The viewer travels in the query string, which is why `?as=` is part of
        # every probe: the body is the caller's, the viewer is the server's.

        def serve_extra(served_root, *extra):
            proc = subprocess.Popen([sys.executable, "-u", str(BOARD), "serve", "--root", str(served_root),
                                     "--port", "0", "--as-of", "2026-09-21", *extra],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            said, deadline = [], time.time() + 30
            while time.time() < deadline:
                said.append(proc.stdout.readline())
                if proc.poll() is not None:
                    break
                m = re.search(r"http://[\d.]+:(\d+)/", "".join(said))
                if m:
                    return f"http://127.0.0.1:{m.group(1)}", proc
            return None, proc

        def post(url, argv, viewer="codex", origin="self", body_extra=None):
            payload = {"argv": argv, **(body_extra or {})}
            req = urllib.request.Request(
                f"{url}/api/command?as={viewer}", method="POST",
                data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            if origin == "self":
                req.add_header("Origin", url)
            elif origin:
                req.add_header("Origin", origin)
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                return json.loads(e.read().decode())

        ro_url, ro_proc = serve_extra(root)
        try:
            check("a read-only server announces /api/command as off", ro_url is not None)
            if ro_url:
                ro = post(ro_url, ["say", "--channel", "hello", "--body", "should not land"])
                check("without --allow-write the browser cannot write at all",
                      ro.get("rc") == 126 and "allow-write" in ro.get("stderr", ""), json.dumps(ro))
                check("and the refusal names the flag that would permit it",
                      "--allow-write" in ro.get("stderr", ""))
        finally:
            ro_proc.terminate()
            ro_proc.wait(timeout=20)

        url2, proc2 = serve_extra(root, "--allow-write")
        try:
            check("a writable server starts", url2 is not None)
            if url2:
                ledger_before = (root / "channels" / "hello" / "ledger.jsonl").read_text().count("\n")
                registry_before = (root / "registry.json").read_text()
                check("a request with no Origin is refused",
                      post(url2, ["say", "--channel", "hello", "--body", "no origin"],
                           origin=None).get("rc") == 126)
                r = post(url2, ["say", "--channel", "hello", "--body", "cross origin"],
                         origin="http://evil.example")
                check("a request from another origin is refused", r.get("rc") == 126, json.dumps(r))
                r = post(url2, ["register", "--as", "attacker", "--kind", "codex"])
                check("a verb outside the allowlist is refused before a subprocess exists",
                      r.get("rc") == 126 and "allowlist" in r.get("stderr", ""), json.dumps(r))
                check("and the refused verb left no agent behind",
                      (root / "registry.json").read_text() == registry_before)
                r = post(url2, ["say", "--as", "attacker", "--channel", "hello",
                                "--body", "WRITE-PATH-PROBE-alpha"],
                         viewer="claude-session1", body_extra={"as": "attacker"})
                check("the command runs", r.get("ok") is True, json.dumps(r))
                # The viewer selector is a read-side affordance (`?as=`), and it
                # must not reach the write. The server has no --viewer here, so its
                # identity is the channel leader -- and a request that asks to
                # write as claude-session1, with the same claim in the body, must
                # still write as the leader. Anything else is forgery with a URL.
                check("a --as in the arguments is dropped, not honoured",
                      r.get("argv", []).count("--as") == 1 and r["argv"][-1] == "human",
                      json.dumps(r.get("argv")))
                said = "".join(r.get("stdout", "") + r.get("stderr", ""))
                check("the write lands under the server's identity, not the claimed name",
                      "attacker" not in said, said)
                private = root / "channels" / "hello" / "private" / "human.jsonl"
                check("the message is in the author's private log, where `aim` puts it",
                      private.exists() and "WRITE-PATH-PROBE-alpha" in private.read_text())
                check("and not in the log of the name the request asked for",
                      not (root / "channels" / "hello" / "private" / "claude-session1.jsonl").exists())
                check("the caller's body cannot rename the writer",
                      "attacker" not in (root / "registry.json").read_text())
                posture = json.loads(urllib.request.urlopen(
                    f"{url2}/api/state?as=claude-session1", timeout=20).read().decode())["write"]
                check("the payload declares the write posture, so the composer need not guess",
                      posture == {"enabled": True, "as": "human"}, json.dumps(posture))
                # `reveal` refuses for anyone while the phase is SEALED_DIVERGENT,
                # so this probe measures the recording path rather than the
                # author's rank -- the author here is the leader, who may advance
                # the barrier and therefore could not be refused that way.
                r = post(url2, ["reveal", "--channel", "hello", "--claim-id", "c1"])
                check("a verb the tool refuses returns the tool's own refusal",
                      r.get("rc") == 2 and "REFUSED" in r.get("stderr", ""),
                      json.dumps(r))
                ledger_after = (root / "channels" / "hello" / "ledger.jsonl").read_text()
                check("and the refusal is recorded, not merely reported",
                      ledger_after.count("\n") == ledger_before + 1
                      and '"event": "refusal"' in ledger_after.splitlines()[-1])
                rec = json.loads(ledger_after.splitlines()[-1])
                check("the recorded refusal names the act and the actor",
                      rec.get("action") == "reveal" and rec.get("agent") == "human"
                      and rec.get("class") == "barrier", json.dumps(rec))
        finally:
            proc2.terminate()
            proc2.wait(timeout=20)

        print("== the same writes, on a fabric the tool built ==")
        # The fixture above is hand-written, and `aim verify` is right to refuse a
        # chain nobody wrote: hand-made records have no `hash`, so a refusal that
        # would be recorded cannot be. That is fine for probing refusals and
        # useless for proving one *was* recorded -- so this block builds the fabric
        # with `aim` itself and asks the verifier afterwards. Same standard the
        # renderer attack was held to: a real fabric, not a plausible-looking file.
        real = work / "real"
        renv = os.environ | {"AIM_ROOT": str(real)}

        def aim(*argv):
            return subprocess.run([str(HERE / "bin" / "aim"), *argv], capture_output=True,
                                  text=True, env=renv, timeout=60)

        check("the tool builds the fabric itself", aim("init").returncode == 0)
        for who, kind in (("human", "human"), ("codex", "codex"), ("claude-session1", "claude")):
            aim("register", "--as", who, "--kind", kind)
        opened_ch = aim("new-channel", "--id", "dev", "--topic", "write path",
                        "--participants", "codex,claude-session1", "--leader", "human")
        check("and a channel in it, sealed by nobody yet", opened_ch.returncode == 0, opened_ch.stderr)

        url3, proc3 = serve_extra(real, "--allow-write", "--as", "codex")
        try:
            check("the board serves that fabric", url3 is not None)
            if url3:
                # The served root and the default root differ on purpose. `bin/aim`
                # takes its fabric from AIM_ROOT, so a server that shells out
                # without passing the root it serves appends the write to somebody
                # else's record -- and the write looks successful from here.
                default_ledger = HERE / "channels" / "dev" / "ledger.jsonl"
                default_before = default_ledger.read_text() if default_ledger.exists() else ""
                led = real / "channels" / "dev" / "ledger.jsonl"
                lines = lambda p: p.read_text().count("\n") if p.exists() else 0
                before = lines(led)
                # `--viewer codex` is what makes this a write by codex, and the
                # request asking for `?as=human` is what must not make it a write
                # by the leader -- the leader *may* advance the barrier, so if the
                # query string were believed this command would succeed and there
                # would be no refusal left to record.
                posture = json.loads(urllib.request.urlopen(
                    f"{url3}/api/state?as=human", timeout=20).read().decode())["write"]
                check("the author is the server's --viewer, not the query string's `as`",
                      posture == {"enabled": True, "as": "codex"}, json.dumps(posture))
                r = post(url3, ["advance", "--channel", "dev", "--to", "COMMIT", "--note", "probe"],
                         viewer="human")
                check("the tool's refusal comes back through the browser unchanged",
                      r.get("rc") == 2 and "may not advance the barrier" in r.get("stderr", ""),
                      json.dumps(r))
                check("the refusal is in the served fabric's ledger",
                      lines(led) == before + 1)
                check("and not in the default fabric's, which was never asked to do this",
                      (default_ledger.read_text() if default_ledger.exists() else "") == default_before)
                v = aim("verify", "--channel", "dev")
                check("the chain verifies after the browser wrote to it", v.returncode == 0,
                      (v.stdout + v.stderr)[-400:])
        finally:
            proc3.terminate()
            proc3.wait(timeout=20)

        print("== the board after the barrier opens ==")
        write(root / "channels" / "hello" / "manifest.json", json.loads(
            (root / "channels" / "hello" / "manifest.json").read_text()) | {
            "barrier": {"phase": "CROSS_EXAMINE", "round": 1,
                        "history": [{"phase": "SEALED_DIVERGENT"}, {"phase": "CROSS_EXAMINE"}]}})
        opened = work / "opened.html"
        render(root, opened, "--as", "claude-session1")
        opened_html = opened.read_text(encoding="utf-8")
        check("after the barrier opens a participant sees the peer draft", PEER_DRAFT in opened_html)
        check("after the barrier opens a participant sees the peer seal", PEER_SEAL in opened_html)

    finally:
        shutil.rmtree(work, ignore_errors=True)

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("failed:")
        for name in failed:
            print(f"  - {name}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
