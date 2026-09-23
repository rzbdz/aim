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
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BOARD = HERE / "bin" / "aimboard.py"
results = []

PEER_DRAFT = "PEER-DRAFT-SECRET-omega"
PEER_SEAL = "PEER-SEAL-SECRET-omega"
OWN_SEAL = "OWN-SEAL-CLAIM-alpha"
ROOM_DRAFT = "ROOM-DRAFT-SECRET-omega"
ROOM_TWO_OPEN = "ROOM-TWO-OPENER-SENTENCE-omega"
ROOM_TWO_SECOND = "ROOM-TWO-SECOND-VOICE-omega"
MAIL_BODY = "MAIL-BODY-SECRET-omega"
XSS = "<script>alert('xss')</script>"


def esc_label(text):
    """The label as `page.esc` writes it, for the drawn-bytes assertion.

    The proxy is deliberate: `_build_line_html` returns `<span class="build-line">`
    and the substring (`<span`) is not in any fixture string. So this can tell a
    page that draws an item from a page that draws nothing, which is the only
    question asked of it -- the escaping itself is `esc`'s, tested where it lives.
    """
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))


# T-0252's own test asks `api.payload` what it publishes and `page.render_html`
# what it draws, so it imports the package rather than shelling out to `bin/aim`.
# Deferred to the call rather than done at import: this file's other tests run
# against the CLI, and an import at module scope would make a missing dependency
# in the package a collection error for all of them.
def _board_modules():
    sys.path.insert(0, str(HERE))
    from aimboard.api import payload
    from aimboard.fabric import load_fabric
    from aimboard.page import build_line, render_html
    return payload, load_fabric, render_html, build_line


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
        # The writer's own spelling: `aim task new` emits `event: "created"` with
        # the id in `task`. This fixture used to write `task.created` + `id`, which
        # the fold also accepts -- so "the renderer tolerates both spellings" was
        # really "the fixture had a typo and the renderer was taught to live with
        # it", and a tolerance that exists to excuse one file cannot tell a real
        # event from a foreign one.
        {"ts": "2026-09-21T00:00:01Z", "event": "created", "task": "T-9001", "actor": "codex",
         "title": PEER_DRAFT, "owner": "codex", "status": "doing", "visibility": "draft",
         "start": "2026-09-21", "due": "2026-09-23", "blocked_by": [], "milestone": "M9"},
        {"ts": "2026-09-21T00:00:02Z", "event": "created", "task": "T-9002", "actor": "claude-session1",
         "title": "a published item", "owner": "claude-session1", "status": "done",
         "visibility": "published", "start": "2026-09-21", "due": "2026-09-22",
         "blocked_by": ["T-9001"], "milestone": "M9"},
        {"ts": "2026-09-21T00:00:03Z", "event": "created", "task": "T-9003", "actor": "codex",
         "title": XSS, "owner": "codex", "status": "review", "visibility": "published",
         "start": "2026-09-22", "due": "2026-09-25", "blocked_by": [], "milestone": "M9"},
        # an event the fold cannot place: a move for a task whose creation the
        # fabric never saw. It must be counted and reported, not silently dropped.
        {"ts": "2026-09-21T00:00:04Z", "event": "moved", "task": "T-9999", "actor": "codex",
         "status": "doing"},
    ])
    jsonl(ch / "rooms" / "dev.jsonl", [
        {"ts": "2026-09-21T00:00:04Z", "agent": "codex", "body": ROOM_DRAFT,
         "mentions": ["claude-session1"], "hash": "h1"},
    ])
    # `author`/`created_by` are what `aim room new` writes, and the room gate reads
    # them (T-0249): the opener of a room is a fact in `rooms/<room>.json`, not
    # something to be inferred from who happened to speak. The two-voice rooms
    # below are the case that made this the fixture rather than an inference.
    write(ch / "rooms" / "dev.json", {"id": "dev", "topic": "fixture room", "visibility": "draft",
                                      "author": "codex", "created_by": "codex"})
    write(ch / "rooms" / "dev.cursors.json", {"claude-session1": {"last_hash": "", "ts": ""}})
    jsonl(ch / "rooms" / "two.jsonl", [
        {"ts": "2026-09-21T00:00:04Z", "agent": "codex", "body": ROOM_TWO_OPEN,
         "mentions": [], "hash": "t1"},
        {"ts": "2026-09-21T00:00:05Z", "agent": "claude-session1", "body": ROOM_TWO_SECOND,
         "mentions": [], "hash": "t2"},
    ])
    write(ch / "rooms" / "two.json", {"id": "two", "topic": "a room with two voices",
                                      "visibility": "draft", "author": "codex",
                                      "created_by": "codex"})
    jsonl(ch / "rooms" / "two.cursors.json", [])
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


def blocked_means_unmet_dependency():
    """C4: `reports.blocked` must mean an UNMET edge, not a drawn one.

    The defect, measured on the live board: the report listed every row that
    carried a `blocked_by`, so 24 of its 51 rows were `done` and one was
    `review`. A finished item cannot be blocked, whatever edge it carries, and a
    dependency whose target is already terminal is met rather than missing.

    Called directly rather than through a render: this is a rule about the fold,
    and a rule tested only through the HTML is a rule any template change can
    break.
    """
    sys.path.insert(0, str(HERE))
    from datetime import date
    from aimboard.fold import report_data

    def task(status, blocked_by):
        return {"title": f"a {status} item", "status": status, "owner": "x",
                "blocked_by": blocked_by, "events": []}

    tasks = {
        "T-A1": task("doing", ["T-A2"]),      # a live blocker -> blocked
        "T-A2": task("doing", []),            # the live blocker itself
        "T-A3": task("done", ["T-A2"]),       # terminal row, edge drawn -> not blocked
        "T-A4": task("doing", ["T-A3"]),      # only blocker is done -> met, not blocked
        "T-A5": task("dropped", ["T-A2"]),    # terminal row, edge drawn -> not blocked
    }
    rows = report_data(tasks, {}, date(2026, 9, 22))["blocked"]
    ids = {r["id"] for r in rows}
    check("an unmet dependency is reported as blocked", ids == {"T-A1"}, sorted(ids))
    check("a terminal row carrying a blocked_by edge is not blocked", "T-A3" not in ids)
    check("a row whose only blocker is terminal is not blocked", "T-A4" not in ids)
    check("a dropped row carrying a blocked_by edge is not blocked", "T-A5" not in ids)
    check("the blocked row keeps its published shape",
          all(k in (rows[0] if rows else {}) for k in
              ("id", "title", "status", "owner", "blocked_by")),
          json.dumps(rows[:1]))


def unassigned_rows_hours_and_the_claim():
    """T-0226/T-0227/T-0212: the fold must publish the unowned state, the hours, the claim.

    Three defects on one row of output:

      * `owner: ""` ("nobody has taken this") and a row that never carried an
        `owner` field both drew as an empty cell, so a board could not tell a
        recorded state from a payload that forgot the field;
      * an unowned row published no claim command, and the exact argv *is* the
        control T-0227 asks for;
      * a `created` event carrying `estimate_hours` reached `flow_series`, which
        folds raw events, but not the board, because `fold_tasks` copies only
        PLAN_FIELDS -- and the board had no opinion about the declared unit.

    Called against the fold directly rather than through a render: these are
    rules about the fold's own output, and a rule tested only through a template
    is a rule the next template change can break.
    """
    sys.path.insert(0, str(HERE))
    try:
        from aimboard.fold import (claim_command, declared_hours, fold_tasks,
                                   merge_plan)
    except ImportError as exc:                       # the state this test exists to end
        check("the fold publishes the claim helpers", False, str(exc))
        return

    events = [
        {"ts": "2026-09-21T00:00:01Z", "event": "created", "task": "T-U1", "actor": "codex",
         "title": "born unowned", "owner": "", "status": "backlog",
         "context_id": "hello", "estimate_hours": 4},
        {"ts": "2026-09-21T00:00:02Z", "event": "created", "task": "T-U2", "actor": "codex",
         "title": "never named an owner", "status": "backlog", "context_id": "hello"},
        {"ts": "2026-09-21T00:00:03Z", "event": "created", "task": "T-U3", "actor": "codex",
         "title": "taken", "owner": "claude-session1", "status": "doing",
         "context_id": "hello", "estimate_hours": 2},
        {"ts": "2026-09-21T00:00:04Z", "event": "created", "task": "T-U4", "actor": "codex",
         "title": "no channel to name", "owner": "", "status": "backlog"},
        {"ts": "2026-09-21T00:00:05Z", "event": "created", "task": "T-U5", "actor": "codex",
         "title": "taken then released", "owner": "codex", "status": "doing",
         "context_id": "hello", "estimate_hours": 1.5},
        {"ts": "2026-09-21T00:00:06Z", "event": "assigned", "task": "T-U5", "actor": "codex",
         "owner": ""},
    ]
    seeds = {
        # a plan seed, still in points: the fold must NOT invent the hours
        "T-U6": {"id": "T-U6", "title": "a seed in points", "owner": "", "status": "backlog",
                 "estimate": 3, "context_id": "hello"},
        # a seed with no owner key at all
        "T-U7": {"id": "T-U7", "title": "a seed with no owner key", "status": "ready"},
    }
    recorded, _unknown = fold_tasks(events)
    for tid in ("T-U1", "T-U2", "T-U3", "T-U5"):
        # what `fabric.load_fabric` stamps before the merge
        recorded[tid]["channel"] = "hello"
    rows = merge_plan(seeds, recorded)

    check("an empty owner is published as an empty string, not None",
          rows["T-U1"].get("owner") == "" and rows["T-U1"].get("owner") is not None)
    check("a row that never carried an owner still gets the key, as ''",
          "owner" in rows["T-U2"] and rows["T-U2"].get("owner") == "")
    check("'' and a name are two different published states",
          rows["T-U3"].get("owner") == "claude-session1"
          and rows["T-U1"].get("owner") != rows["T-U3"].get("owner"))
    check("a seed with no owner key is normalised the same way",
          "owner" in rows["T-U7"] and rows["T-U7"].get("owner") == "")

    check("an unowned row publishes the claim it offers: verb, channel, id",
          rows["T-U1"].get("claim") == {"verb": "aim task claim",
                                        "channel": "hello", "id": "T-U1"},
          json.dumps(rows["T-U1"].get("claim")))
    check("an owned row publishes no claim at all",
          rows["T-U3"].get("claim", "missing") is None)
    check("a released row is unowned again and offers the claim again",
          rows["T-U5"].get("owner") == "" and rows["T-U5"].get("claim") is not None
          and rows["T-U5"].get("estimate_hours") == 1.5)
    check("the exact command names the seat the surface holds",
          claim_command(rows["T-U1"], "claude-session1")
          == "aim task claim --as claude-session1 --channel hello --id T-U1",
          claim_command(rows["T-U1"], "claude-session1"))
    check("no command is drawn with a hole where the seat goes",
          claim_command(rows["T-U1"], "") == "")
    check("an owned row yields no command even for a seat",
          claim_command(rows["T-U3"], "claude-session1") == "")
    check("a row with no channel offers no control rather than a broken one",
          rows["T-U4"].get("claim") == {"verb": "aim task claim", "channel": "",
                                        "id": "T-U4"}
          and claim_command(rows["T-U4"], "codex") == "")

    check("a recorded estimate reaches the board row in hours",
          rows["T-U1"].get("estimate_hours") == 4)
    check("an absent estimate is None on the row, not 0 and not a dropped key",
          "estimate_hours" in rows["T-U2"] and rows["T-U2"].get("estimate_hours") is None
          and rows["T-U2"].get("estimate_hours") != 0)
    check("a plan seed's points are not converted into hours by the fold",
          rows["T-U6"].get("estimate") == 3
          and rows["T-U6"].get("estimate_hours") is None,
          f"estimate={rows['T-U6'].get('estimate')!r} "
          f"estimate_hours={rows['T-U6'].get('estimate_hours')!r}")
    check("only a real number is hours: a string or a bool is not",
          declared_hours(2) == 2 and declared_hours(0) == 0
          and declared_hours("4") is None and declared_hours(True) is None
          and declared_hours(None) is None)


def room_gate_keeps_the_opener_and_refuses_the_stranger():
    """T-0249, both halves, on a fabric the tool built.

    The card's two findings, and each is one line of a gate:

      * **a second voice evicts the author.** `room_authors` used to return the
        set of everyone who had spoken, and `set()` as soon as a room had two
        voices -- so `visible_rooms` withheld the room from the agent who opened
        it, and it stayed withheld forever. The second half of the same rule was
        worse than the first: `room publish` is author-exempted, so the *only*
        caller who could open the room again was one the old `_room_author`
        returned `""` for, i.e. nobody.
      * **a human stranger could read and publish it.** The CLI's draft gate was
        `kind != "human"`, which reads as "the leader is exempt" and behaves as
        "anyone the registry calls human is exempt". Measured before the fix: a
        registered human who was neither a participant nor the leader read a draft
        room's messages (`room meta`, rc 0) and published it (`room publish`,
        rc 0, recorded in the ledger as a barrier event), while the peer the phase
        is meant to stop was correctly refused.

    Built by `aim` rather than hand-written, for this file's usual reason -- and
    because the CLI half is where the eviction was reachable, so a fixture would
    have measured a fixture. The board half is then read through the same
    `load_rooms`/`visible_rooms` the renderer uses.

    The second voice here is the **leader**, and that choice is the card's own
    finding rather than a convenience: the draft gate exempts the leader, so the
    leader is the one agent whose words can land in a peer's draft room during a
    divergence phase. That is exactly the sequence that locked the author out.
    """
    sys.path.insert(0, str(HERE))
    from datetime import date
    from aimboard import fabric, gate

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env = dict(os.environ, AIM_ROOT=str(root))

        def aim(*argv):
            return subprocess.run([str(HERE / "bin" / "aim"), *argv], capture_output=True,
                                  text=True, env=env, timeout=60)

        def norm(text):
            return re.sub(r"\s+", " ", text.replace("\\n", " ")).strip()

        aim("init")
        for who, kind in (("alpha", "claude"), ("beta", "codex"),
                          ("lead", "human"), ("otherh", "human")):
            aim("register", "--as", who, "--kind", kind)
        opened = aim("new-channel", "--id", "ch", "--topic", "T-0249 room gate",
                     "--participants", "alpha,beta", "--leader", "lead")
        check("T-0249: the test channel is in a divergence phase",
              "SEALED_DIVERGENT" in opened.stdout, opened.stdout + opened.stderr)
        check("T-0249: alpha opens a draft room and writes in it",
              aim("room", "new", "--as", "alpha", "--channel", "ch", "--id", "r1").returncode == 0
              and aim("room", "say", "--as", "alpha", "--channel", "ch", "--id", "r1",
                      "--body", "alpha opens this room").returncode == 0)
        second = aim("room", "say", "--as", "lead", "--channel", "ch", "--id", "r1",
                     "--body", "the leader answers in it")
        check("T-0249: a second voice joins the author's draft room",
              second.returncode == 0, second.stderr)
        told_what = norm(aim("room", "list", "--as", "alpha", "--channel", "ch").stdout)
        check("T-0249 HALF 1: the author's own draft room is not withheld from the author "
              "after a second voice speaks in it",
              "r1" in told_what and "withheld" not in told_what, told_what)
        meta = aim("room", "meta", "--as", "alpha", "--channel", "ch", "--id", "r1")
        check("T-0249 HALF 1: the author can still read the room they opened",
              meta.returncode == 0 and '"author": "alpha"' in meta.stdout,
              (meta.stdout + meta.stderr)[-300:])
        pub = aim("room", "publish", "--as", "alpha", "--channel", "ch", "--id", "r1",
                  "--reason", "the author opens it")
        check("T-0249 HALF 1: and can still open it, which nobody could after the second voice",
              pub.returncode == 0 and "published" in norm(pub.stdout), pub.stderr)

        # The row the fix must NOT weaken: a peer still cannot read a draft room.
        aim("room", "new", "--as", "alpha", "--channel", "ch", "--id", "r2")
        aim("room", "say", "--as", "alpha", "--channel", "ch", "--id", "r2",
            "--body", "alpha draft")
        peer = aim("room", "say", "--as", "beta", "--channel", "ch", "--id", "r2",
                   "--body", "beta invites itself")
        check("T-0249: a participant who is not the author is still refused a draft room",
              peer.returncode == 2 and "not its author" in peer.stderr, peer.stderr)

        stranger_read = aim("room", "meta", "--as", "otherh", "--channel", "ch", "--id", "r2")
        check("T-0249 HALF 2: a human stranger cannot read a draft room they are not in",
              stranger_read.returncode == 2 and "beta invites itself" not in stranger_read.stdout,
              (stranger_read.stdout + stranger_read.stderr)[-300:])
        stranger_pub = aim("room", "publish", "--as", "otherh", "--channel", "ch",
                           "--id", "r2", "--reason", "stranger")
        check("T-0249 HALF 2: nor publish it",
              stranger_pub.returncode == 2 and "room_published" not in stranger_pub.stdout,
              (stranger_pub.stdout + stranger_pub.stderr)[-300:])
        check("T-0249 HALF 2: and the refusal is recorded, not merely printed",
              aim("room", "list", "--as", "otherh", "--channel", "ch").returncode == 2)
        ledger = (root / "channels" / "ch" / "ledger.jsonl").read_text()
        refusals = [json.loads(l) for l in ledger.splitlines()
                    if '"event": "refusal"' in l and '"otherh"' in l]
        check("T-0249 HALF 2: the stranger's attempts are in the ledger, named and classed",
              len(refusals) >= 2 and all(r.get("class") == "barrier" for r in refusals),
              json.dumps(refusals[-1:] if refusals else []))
        check("T-0249 HALF 2: the stranger published nothing",
              ledger.count("room_published") == 1,
              f"{ledger.count('room_published')} publish row(s), expected only the author's")
        check("T-0249: the leader is still the audience",
              aim("room", "meta", "--as", "lead", "--channel", "ch", "--id", "r2").returncode == 0)

        # The board half. `author` is the metadata half of the rule and used to be
        # dropped by `load_rooms`, so the two-voice room reached `visible_rooms`
        # with no author evidence at all -- the loaded room is asserted directly,
        # because "the gate reads a field the loader never forwards" is a bug the
        # end-to-end render cannot distinguish from a correct refusal.
        state = fabric.load_fabric(root, [], date(2026, 9, 23))
        ch = next(c for c in state["channels"] if c["id"] == "ch")
        r1 = next(r for r in ch["rooms"] if r["id"] == "r1")
        check("T-0249: the loader forwards the room's author to the gate",
              r1.get("author") == "alpha", json.dumps({k: v for k, v in r1.items()
                                                       if k != "messages"}))
        check("T-0249: the gate names exactly one author for a two-voice room",
              gate.room_authors(r1) == {"alpha"}, sorted(gate.room_authors(r1)))
        visible, hidden = gate.visible_rooms(state, ch, "alpha")
        check("T-0249 HALF 1 on the board: the author sees their own room",
              "r1" in [r["id"] for r in visible], f"visible={[r['id'] for r in visible]} hidden={hidden}")
        visible_b, hidden_b = gate.visible_rooms(state, ch, "beta")
        check("T-0249: and a peer is still withheld from a draft room",
              "r2" not in [r["id"] for r in visible_b] and hidden_b >= 1,
              f"visible={[r['id'] for r in visible_b]} hidden={hidden_b}")

        # The provenance arm, which is the one case that still refuses everybody:
        # a room's log naming an opener its metadata does not is a contradiction,
        # and `""` is this rule's way of saying "nobody may read this". `getattr`
        # rather than an attribute access on purpose -- on a tree without the fix
        # this check must *fail*, and an AttributeError here would end the run
        # before it printed its count, which is a crash reported as a failure
        # rather than a measurement.
        decider = getattr(gate, "room_author_from_metadata", None)
        check("T-0249: the room's author rule has a home in gate.py, and reads provenance",
              decider is not None
              and decider({"author": "alpha"}, "beta") == ""
              and decider({"author": "alpha"}, "alpha") == "alpha"
              and decider({}, "alpha") == "alpha",
              f"decider={decider!r}")


def phase_provenance_names_the_channel():
    """T-0252: the payload's top-level `phase` must name the channel it came from.

    The defect, measured on the live root 2026-09-23 through `api.payload` itself:
    the header's chip draws `board.phase`, and that is `gate_channel`'s *default*
    channel's phase -- a function whose docstring answers a question about tasks
    ("which channel's phase governs a task that does not name one",
    `aimboard/gate.py:37`). So three of the four seats read a different channel's
    phase and nothing in the payload said so:

        claude-session1  SYNTHESIS  barrier-v0  participation   6 raw rows
        human            SYNTHESIS  barrier-v0  tasks_exists    6 raw rows
        codex            SEALED_DIVERGENT  dev  participation   0 raw rows
        codex-orangement COMMIT     hello      participation 501 raw rows

    Two halves, and the second is the one a renderer cannot fake: the payload
    names the channel, *and* two seats on one root get different provenance. A fix
    that hard-coded a single channel would pass the first check on the fixture and
    fail the second.

    Built from `bin/aim` rather than hand-written files, for the reason this file
    already gives elsewhere: a fixture assembled by hand proves the renderer
    tolerates a fixture. Two channels, because the finding is a disagreement
    between seats and one channel cannot disagree with itself:

      * `dev` -- `codex` is a participant, no task store at all;
      * `hello` -- `codex` is a participant, and the only store.

    The two `new-channel` calls are in that order, and `load_fabric` sorts, so
    `dev` is the channel the participation arm reaches first. The arm assertion is
    the one that makes this test about the *provenance* rather than about
    `gate_channel`: `human` participates in no channel, so the leader's result must
    say `tasks_exists`, which is a different arm of the same function and therefore
    a different claim about the same number. Which channel that arm lands on is
    `gate_channel`'s and this test does not pin it -- it asserts that the named
    channel really is the one the phase was read from, and that the arm it names is
    the one that really chose. The selection rule itself is the leader's call, not
    a rendering one.
    """
    def phase_and_provenance(root, seat):
        from datetime import date as _date
        payload, load_fabric, _render, _line = _board_modules()
        state = load_fabric(root, [], _date(2026, 9, 23))
        doc = payload(state, seat, None)
        # `.get`, not `[]`, and the absence is asserted below rather than raised
        # here. A `KeyError` out of a helper is a *crash*: the runner reports it
        # as a failure, but it aborts the whole function on the first check, so
        # an unlabelled phase reads as "the test is broken" instead of as the
        # finding it is. Measured by reverting the fix in a scratch copy: the
        # `[]` version raised at this line and none of the seven checks after it
        # reported anything. A gate that cannot say *what* is missing is worse
        # than one that says nothing.
        return doc.get("phase"), doc.get("phase_channel")

    def phase_of(root, channel):
        # Same reason as the helper above: with no channel named, this would be
        # `channels//manifest.json` and raise, which reports "the test broke"
        # instead of "the payload named nothing".
        if not channel:
            return "<no channel named>"
        return json.loads((root / "channels" / channel / "manifest.json")
                          .read_text())["barrier"]["phase"]

    work = Path(tempfile.mkdtemp(prefix="aimboard-t0252-"))
    try:
        root = work / "fabric"
        env = os.environ | {"AIM_ROOT": str(root)}

        def aim(*argv):
            return subprocess.run([str(HERE / "bin" / "aim"), *argv], capture_output=True,
                                  text=True, env=env, timeout=60)

        if aim("init").returncode != 0:
            check("the fabric for the phase-provenance test builds", False,
                  "`aim init` failed in " + str(root))
            return
        for who, kind in (("human", "human"), ("codex", "codex"),
                          ("claude-session1", "claude")):
            aim("register", "--as", who, "--kind", kind)
        # `new-channel` opens a channel at SEALED_DIVERGENT, its first phase, so the
        # phases these seats are shown are not all the same string. `hello` is moved
        # on to COMMIT -- by the leader, which is who `advance` allows -- so that
        # "the payload names a channel" cannot be satisfied by two channels that
        # happen to agree, and so the provenance has something to be right about.
        for cid, parts in (("dev", "codex,claude-session1"), ("hello", "codex,claude-session1")):
            aim("new-channel", "--id", cid, "--topic", "t", "--participants", parts,
                "--leader", "human")
        moved = aim("advance", "--as", "human", "--channel", "hello", "--to", "COMMIT",
                    "--note", "fixture")
        check("the fixture's second channel carries a phase of its own",
              moved.returncode == 0 and phase_of(root, "hello") == "COMMIT"
              and phase_of(root, "dev") == "SEALED_DIVERGENT",
              (moved.stderr or moved.stdout)[-200:] +
              f" dev={phase_of(root, 'dev')!r} hello={phase_of(root, 'hello')!r}")
        # Exactly one channel carries a task store, and it is *not* the one the
        # leader's arm is asserted on: `tasks_exists` is what the leader's
        # provenance must say, whatever channel that arm lands on.
        aim("task", "new", "--as", "codex", "--channel", "hello", "--title", "stored work",
            "--owner", "codex", "--status", "doing")

        phase, prov = phase_and_provenance(root, "codex")
        # T-0252 (a): the payload names the channel its `phase` came from. This is
        # the check that fails when the key is absent, so it is stated in terms of
        # the key's *shape and content* and not in terms of anything downstream:
        # an assertion that reached for `prov["id"]` first would report the
        # absence as a `TypeError` and take the two checks after it with it.
        check("T-0252 (a): the payload publishes the channel its phase came from, always",
              isinstance(prov, dict) and set(prov) == {"id", "arm"} and bool(prov.get("id")),
              f"phase={phase!r} phase_channel={json.dumps(prov) if isinstance(prov, dict) else prov!r}"
              " -- no `phase_channel` on the payload, which is the defect this test exists for")
        prov = prov if isinstance(prov, dict) else {}
        check("codex's provenance names the channel codex's phase was read from",
              prov.get("id") == "dev" and prov.get("arm") == "participation",
              f"{json.dumps(prov)} (channels sort: "
              f"{[p.name for p in sorted((root / 'channels').iterdir())]})")
        # Read through the *named* channel rather than a literal: the claim is
        # "the phase published is the phase of the channel the provenance names",
        # and a check that hard-coded `dev` would pass on a payload that named
        # nothing at all. Measured by reverting the fix in a scratch copy, where
        # the literal form stayed green. `gate_channel`'s participation arm is
        # asserted one check below, so this one does not have to pin the channel.
        named = str(prov.get("id") or "")
        check("the phase the payload publishes is that channel's own phase",
              named != "" and phase == phase_of(root, named) == "SEALED_DIVERGENT",
              f"phase={phase!r} channel={named!r} "
              f"manifest={phase_of(root, named)!r}")

        leader_phase, leader_prov = phase_and_provenance(root, "human")
        leader_prov = leader_prov if isinstance(leader_prov, dict) else {}
        check("the leader, a participant of nothing, is told the arm that chose theirs",
              leader_prov.get("arm") == "tasks_exists", json.dumps(leader_prov))
        check("and the channel it names really holds the task store",
              (root / "channels" / str(leader_prov.get("id")) / "tasks.jsonl").exists(),
              f"phase={leader_phase!r} provenance={json.dumps(leader_prov)}")

        # T-0252 (b), the half a hard-coded channel cannot pass: two seats, one
        # root, two different channels, each labelled with its own. A fix that
        # pinned one channel would pass (a) and fail here.
        check("T-0252 (b): two seats on one root are shown different channels, and told which",
              bool(prov.get("id")) and bool(leader_prov.get("id"))
              and prov.get("id") != leader_prov.get("id") and prov != leader_prov,
              f"codex={json.dumps(prov)} human={json.dumps(leader_prov)}")

        # Same *rule*, different root: no channels at all, so the phase falls back
        # to `-` and the provenance must be empty rather than naming a channel that
        # is not there. The two roots differ in exactly one way (channels vs none)
        # so a provenance that is really the phase's origin and one that is just
        # "the first channel" cannot both pass this pair.
        bare = work / "bare"
        bare.mkdir(parents=True, exist_ok=True)
        write(bare / "registry.json", {"agents": {"human": {"id": "human", "kind": "human"}}})
        bare_phase, bare_prov = phase_and_provenance(bare, "human")
        check("a root with no channel publishes no phase and no channel to name",
              bare_phase == "-" and isinstance(bare_prov, dict) and bare_prov.get("id") == "",
              json.dumps(bare_prov) if isinstance(bare_prov, dict) else repr(bare_prov))

        # The no-JS path is the same defect one layer down (`page.py`), so it is
        # asserted here rather than left to a hand-read of the HTML.
        from datetime import date as _date
        _payload, load_fabric, render_html, _line = _board_modules()
        html = render_html(load_fabric(root, [], _date(2026, 9, 23)), "codex", {},
                           "2026-09-23T00:00:00.000Z")
        check("the no-JS render names the same channel in its meta line",
              f"from channel #{prov.get('id')}" in html, "no `from channel #` in the rendered meta")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def created_by_comes_from_the_created_event():
    """T-0250: the folded card's `created_by` is the `created` event's `actor`.

    The union `bin/aim` implements (`_visible_to`: `owner == who or
    created_by == who`) has a second arm `aimboard/fold.py` never fed: the fold
    copied only `PLAN_FIELDS` off a `created` record and the store writes no
    `created_by` on one, so the renderer's card had no such key at all
    [measured on this store: `'created_by' in <folded card>` is False for every
    card, while the same card's `created` event carries `actor`; 105 `created`
    rows, 0 carrying a literal `created_by`]. `gate.visible_tasks` exempts
    `viewer in (task.owner, task.created_by)`, so with the key absent that arm
    could never fire.

    Three checks, because the value can be right for three different reasons:
    the key exists; it is the *event's* actor and not the owner; and it follows
    the event rather than any literal `created_by` the record carries, which is
    the one an event could be trusted about and a plan seed could not.

    Called against the fold directly rather than through a render, for the
    reason the other two fold tests here give: a rule tested only through a
    template is a rule the next template change can break.
    """
    sys.path.insert(0, str(HERE))
    try:
        from aimboard.fold import fold_tasks, merge_plan
    except ImportError as exc:                       # the state this test exists to end
        check("the fold exists to be asked", False, str(exc))
        return

    events = [
        # created by claude-session1, then handed to codex: the one record the
        # union's two arms can disagree about, which is the whole point.
        {"ts": "2026-09-21T00:00:01Z", "event": "created", "task": "T-C1",
         "actor": "claude-session1", "title": "a card its author handed away",
         "owner": "codex", "status": "ready", "visibility": "draft",
         "context_id": "hello"},
        # a literal `created_by` on the event disagrees with its `actor`: the
        # event is the authority, and no plan file may move that.
        {"ts": "2026-09-21T00:00:02Z", "event": "created", "task": "T-C2",
         "actor": "codex", "created_by": "someone-else", "title": "a record that names two authors",
         "owner": "", "status": "backlog", "visibility": "draft", "context_id": "hello"},
        {"ts": "2026-09-21T00:00:03Z", "event": "created", "task": "T-C3",
         "actor": "claude-session1", "title": "never renamed",
         "owner": "", "status": "backlog", "visibility": "draft", "context_id": "hello"},
        {"ts": "2026-09-21T00:00:04Z", "event": "assigned", "task": "T-C3",
         "actor": "codex", "owner": "codex"},
    ]
    recorded, _unknown = fold_tasks(events)
    for tid in ("T-C1", "T-C2", "T-C3"):
        recorded[tid]["channel"] = "hello"
    merged = merge_plan({}, recorded)

    check("a folded card carries the key at all", "created_by" in merged["T-C1"],
          sorted(merged["T-C1"]))
    check("the value is the created event's actor, not the owner",
          merged["T-C1"].get("created_by") == "claude-session1"
          and merged["T-C1"].get("owner") == "codex",
          f"created_by={merged['T-C1'].get('created_by')!r} "
          f"owner={merged['T-C1'].get('owner')!r}")
    check("a literal created_by on the record does not override the actor",
          merged["T-C2"].get("created_by") == "codex",
          repr(merged["T-C2"].get("created_by")))
    check("handing the card to a peer does not move the author",
          merged["T-C3"].get("created_by") == "claude-session1"
          and merged["T-C3"].get("owner") == "codex")
    check("the gate's second arm now has something to fire on",
          merged["T-C1"].get("created_by") not in (None, "")
          and merged["T-C1"].get("created_by") != merged["T-C1"].get("owner"))


def a_task_edit_moves_the_field_the_board_draws():
    """T-0246: `aim task edit` writes an event the fold had no branch for.

    The accept line is exact, and it has two halves that fail independently:

        "With bin/aim:2330 emitting \\"edited\\" and aimboard/fold.py having no
         branch for it, fold_tasks returns tasks_unknown_events = 0 and the
         edited field unchanged; after the fix, a task edit moves the field the
         board draws."

    Both are reproduced below, against the store's own bytes rather than a
    fixture this test invents: the events are **emitted by the verb** into a
    scratch root, because a hand-written `edited` event proves only that this
    test and the fold agree about a shape, and the shape is the thing that was
    in doubt. The card is then folded through `aimboard.fold.fold_tasks` -- and
    rendered through `bin/aimboard.py render --json`, so "the field the board
    draws" is read off the board's own payload rather than asserted of it.

    The second half is the one the card's *title* is about. The counter could
    not fire on `edited`, and the reason is a branch order rather than a missing
    name: `edited` arrives after a `created` the fold read, so it took the
    "ordinary event of a card that exists" branch, matched no event branch below
    it, and left the loop with nothing counted -- as did every *other* unknown
    name, which is why the check below folds a missing name onto a **known**
    card. Written that way on purpose: on an unknown card the old code already
    counted it, so a check that used one would have passed before the fix.
    """
    sys.path.insert(0, str(HERE))
    from aimboard.fold import fold_tasks

    work = Path(tempfile.mkdtemp(prefix="aimboard-t0246-"))
    try:
        root = work / "fabric"
        env = {**os.environ, "AIM_ROOT": str(root)}

        def run(*args):
            return subprocess.run([str(HERE / "bin" / "aim"), *args],
                                  capture_output=True, text=True, timeout=120, env=env)

        p = run("init")
        check("T-0246: the scratch fabric initialises", p.returncode == 0,
              (p.stdout + p.stderr)[-300:])
        for agent, kind in (("human", "human"), ("alpha", "claude")):
            run("register", "--as", agent, "--kind", kind)
        p = run("new-channel", "--id", "ch", "--topic", "T-0246", "--leader", "human",
                "--participants", "alpha")
        check("T-0246: the scratch channel opens", p.returncode == 0,
              (p.stdout + p.stderr)[-300:])
        p = run("task", "new", "--as", "alpha", "--channel", "ch", "--title", "a card",
                "--owner", "alpha", "--milestone", "M1")
        check("T-0246: a card exists, filed under M1", p.returncode == 0,
              (p.stdout + p.stderr)[-300:])
        p = run("task", "edit", "--as", "alpha", "--channel", "ch", "--id", "T-0001",
                "--milestone", "M2", "--reason", "filed under the wrong milestone")
        check("T-0246: the edit reports the field moving, M1 -> M2",
              p.returncode == 0 and "milestone M1 -> M2" in p.stdout,
              (p.stdout + p.stderr)[-300:])

        store = root / "channels" / "ch" / "tasks.jsonl"
        events = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
        names = [e.get("event") for e in events]
        check("T-0246: the store carries the verb's own `edited` event",
              names == ["created", "edited"], names)
        check("T-0246: and it carries changes as [{field, from, to}]",
              events[-1].get("changes") == [{"field": "milestone", "from": "M1", "to": "M2"}],
              json.dumps(events[-1].get("changes")))

        items, unknown = fold_tasks(events)
        check("T-0246: the fold has a branch for `edited`, so it is not unknown",
              unknown == 0, f"tasks_unknown_events = {unknown}")
        check("T-0246: folding the store moves the edited field",
              items.get("T-0001", {}).get("milestone") == "M2",
              f"milestone = {items.get('T-0001', {}).get('milestone')!r}")
        check("T-0246: and records what the field was, so the before is not lost",
              items.get("T-0001", {}).get("milestone_was") == "M1",
              f"milestone_was = {items.get('T-0001', {}).get('milestone_was')!r}")

        # The field the board draws, read off the board's own output.
        p = subprocess.run([sys.executable, str(BOARD), "render", "--root", str(root),
                            "--json", "--as-of", "2026-09-23",
                            "--generated-at", "2026-09-23T00:00:00.000Z"],
                           capture_output=True, text=True, timeout=120)
        check("T-0246: the board's own view renders", p.returncode == 0, p.stderr[-300:])
        doc = json.loads(p.stdout) if p.returncode == 0 else {}
        row = doc.get("tasks", {}).get("T-0001", {})
        check("T-0246: the row the board draws carries the milestone the edit moved it to",
              row.get("milestone") == "M2", json.dumps(row.get("milestone")))
        check("T-0246: and the board's stray-event count is 0, because nothing is stray",
              doc.get("unplaced_events") == 0, json.dumps(doc.get("unplaced_events")))

        # The counter, on an event name outside the vocabulary -- on a card the
        # fold HAS seen. `totally_made_up` is the name the card's own report used,
        # and it is the one that stays 0 under the old branch order.
        stray, stray_count = fold_tasks(events + [
            {"ts": "2026-09-23T00:00:09.000Z", "event": "totally_made_up",
             "actor": "alpha", "context_id": "ch", "task": "T-0001"}])
        check("T-0246: an event name outside the vocabulary increments the counter, "
              "even on a card the fold has seen",
              stray_count == 1, f"tasks_unknown_events = {stray_count}")
        check("T-0246: and the stray event does not land on the card as board state",
              len(stray.get("T-0001", {}).get("events", [])) == 2,
              f"events = {len(stray.get('T-0001', {}).get('events', []))}")
        # A retraction is a name *in* the vocabulary, read and deliberately undone,
        # so it must stay uncounted -- the false alarm the retraction exists to
        # avoid, and the case a counter that fires on any name would produce.
        _, after_retract = fold_tasks(events + [
            {"ts": "2026-09-23T00:00:10.000Z", "event": "retracted",
             "actor": "alpha", "context_id": "ch", "task": "T-0001", "reason": "oops"}])
        check("T-0246: a retraction is a known name, so it is not counted as stray",
              after_retract == 0, f"tasks_unknown_events = {after_retract}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def a_dirty_bundle_is_stated_on_the_page():
    """T-0196: the page states the revision it was built from, and whether the tree
    was dirty.

    The card's accept line, verbatim:

        One writable board answers on its port, started with an explicit --as, and
        the page states the revision and whether the tree was dirty.

    The payload half already existed (`revision.bundle.revision` and
    `revision.bundle.dirty`, written by `web/vite.config.js` at build time) and no
    page printed it. Measured 2026-09-23 on the live root, before this fix:

      * the served `index.html` and `index-*.js` (fetched from 8777 and hashed
        against `web/dist`: `686211a5...` and `bec8aa58...`, both equal) contain the
        substrings `revision`, `stale` and `dirty` **zero** times;
      * `__AIM_REVISION__` is defined in `web/vite.config.js:95` and read by
        **nothing** in `web/src`;
      * `web/src/theme.js:46` claims "the shell already says which build is
        serving" while `App.vue`'s only `stale` is the chunk-404 alert, which fires
        on a rebuild and is silent about a dirty build.

    Three checks, and the second is the one this card exists for. `stale` is the
    content-hash comparison (`aimboard/revision.py:129-132`) and it is **false** for
    a dirty bundle whose sources have not moved since the build -- correct, and not
    the question the accept line asks. `describe_revision` never reads
    `bundle.revision` or `bundle.dirty` to decide `stale`; measured by handing it
    four bundle records that differ only in the label (`11bce31+dirty`, `f3ab9cd`,
    `deadbee`, `''`) with one hash: all four answered `stale=False`. So the dirty
    flag has to be drawn from the flag, not inferred from `stale`.

    No subprocess and no fixture fabric: `build_line` is a function of the payload,
    and the payload here is the live root's own, which is the tree the card was
    written against. `render_page` is exercised through `render_html` for the same
    reason -- the line has to reach the bytes, and a helper that returns a string
    nobody draws is the defect this test is written against.
    """
    from datetime import date
    payload, load_fabric, render_html, build_line = _board_modules()
    state = load_fabric(HERE, [], date(2026, 9, 23))
    doc = payload(state, "codex", None)
    rev = doc.get("revision") or {}

    # Non-vacuity first: if the live root ever stops carrying a bundle record, this
    # test must say so rather than pass on an absence.
    bundle = rev.get("bundle")
    check("T-0196: the live payload names the bundle it is serving",
          isinstance(bundle, dict) and bool(bundle.get("revision")), json.dumps(bundle))

    inv = build_line(doc)
    check("T-0196: build_line reads the version out of the payload, not out of the tree",
          inv.get("label") == (bundle or {}).get("revision") and bool(inv.get("label")),
          f"label={inv.get('label')!r} bundle.revision={(bundle or {}).get('revision')!r}")

    html = render_html(state, "codex", {}, "2026-09-23T00:00:00.000Z", payload=doc)
    meta = re.search(r'<div class="meta">(.*?)</div>', html, re.S)
    drawn = meta.group(1) if meta else ""
    check("T-0196: the page draws that revision",
          bool(inv.get("label")) and esc_label(inv["label"]) in drawn,
          f"label={inv.get('label')!r} not in the header meta line")
    # ...and says the tree was dirty when it was built, which is the half `stale`
    # cannot carry. The live bundle was built dirty (measured this session:
    # `bundle.dirty` true, `bundle.revision` `11bce31+dirty`), so the page must say
    # so in words. The word is what a reader reads; a `<b>dirty</b>` with no
    # sentence around it would be a label with no claim.
    if (bundle or {}).get("dirty"):
        check("T-0196: and says the tree was dirty when the bundle was built",
              "dirty" in drawn and "not the committed code" in drawn,
              "the header does not state the dirty build in words")
    else:
        check("T-0196: a clean bundle does not claim to be dirty",
              "dirty" not in drawn, "a clean build is drawn as dirty")
    # The control, and it is the finding: `stale` is a content-hash comparison, so a
    # dirty bundle whose sources have not moved is `stale: False`. Correct as a
    # statement about the bytes, and *not* a statement that the page is committed
    # code. The page must not let the two be read as one another.
    check("T-0196: `stale` is the content-hash answer and does not carry the dirty flag",
          (bundle or {}).get("source_sha256") == rev.get("front_end_sha256"),
          f"bundle hash {(bundle or {}).get('source_sha256')!r} != current {rev.get('front_end_sha256')!r}")
    if (bundle or {}).get("dirty") and rev.get("stale") is False:
        check("T-0196: a page that is not stale but is dirty says BOTH",
              "dirty" in drawn and "stale" not in drawn.lower().replace("stalebar", ""),
              "a dirty, not-stale bundle must say dirty and not stale")


    # ---- and the half a browser actually receives ------------------------------
    # The checks above read `render_html`, and on this server that path is dead for
    # every browser: `GET /` takes the asset branch (`web/dist/index.html` exists),
    # so the built shell is served and `_render` is that branch's `else`. Measured
    # this session on the canonical board: `GET /` -> 1876 bytes, `grep build-line`
    # -> 0, byte-identical to `web/dist/index.html`. A line drawn only in
    # `render_html` would be the same defect this card is about, one layer out, so
    # the served bytes are asserted here too -- on a server started for the purpose
    # and stopped in the `finally` below, so the canonical board is not touched.
    served = Path(tempfile.mkdtemp(prefix="aimboard-served-"))
    shutil.rmtree(served)
    shutil.copytree(state["root"], served)
    proc = subprocess.Popen(
        [sys.executable, "-u", str(BOARD), "serve", "--root", str(served),
         "--port", "0", "--as", "codex"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        url, said = None, []
        deadline = time.time() + 30
        while time.time() < deadline:
            said.append(proc.stdout.readline())
            if proc.poll() is not None:
                break
            m = re.search(r"http://[\d.]+:(\d+)/", "".join(said))
            if m:
                url = f"http://127.0.0.1:{m.group(1)}"
                break
        check("T-0196: a served board starts for the served-bytes check", url is not None,
              "".join(said)[-400:])
        if url:
            with urllib.request.urlopen(f"{url}/", timeout=20) as r:
                page_bytes = r.read().decode("utf-8")
            check("T-0196: the page a browser is served states the revision it was built from",
                  "build-line" in page_bytes and "build " in page_bytes,
                  "no build line in the bytes the server returns for /")
            # The same two facts the payload carries, in the page the reader gets.
            live = json.loads(urllib.request.urlopen(f"{url}/api/state?as=codex",
                                                     timeout=20).read().decode())["revision"]
            lb = live.get("bundle") or {}
            check("T-0196: and the served page names the same revision the payload does",
                  f'build {lb.get("revision")}' in page_bytes,
                  f'payload says {lb.get("revision")!r}, page does not print it')
            check("T-0196: and says the tree was dirty, because the served bundle was built dirty",
                  ("was <b>dirty</b>" in page_bytes) == bool(lb.get("dirty")),
                  f'bundle.dirty={lb.get("dirty")} while the page says dirty='
                  f'{"was <b>dirty</b>" in page_bytes}')
            # The fixture root carries no `web/dist`, so this also pins the "nothing
            # recorded" branch: an honest absence rather than an invented label.
            # `class="build-line"`, not the bare substring: the injected block carries
            # the rule twice (`.build-line` and `html.dark .build-line`) beside the one
            # span, so the raw substring is 3 and the *element* count is what says
            # "one line" rather than "one line plus its stylesheet".
            SEL = 'class="build-line"'
            check("T-0196: the served shell carries exactly one build line",
                  page_bytes.count(SEL) == 1, f"{SEL} x{page_bytes.count(SEL)}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()

    # The three sentences as separate claims, on synthesized records: a build from a
    # different commit is a different statement from a build from a dirty one, and a
    # page that printed one for the other would be the same defect one step over.
    def said(**kw):
        base = {"known": True, "label": "2930c74+dirty", "built_at": "2026-09-22T16:42:05.059Z",
                "dirty": True, "fabric": "085c84f", "behind": True, "stale": False}
        base.update(kw)
        from aimboard.page import _build_line_html
        return re.sub(r"<[^>]+>", "", _build_line_html(base))

    dirty_behind = said()
    check("T-0196: a bundle from a dirty tree at another commit says both",
          "dirty" in dirty_behind and "the tree has moved since" in dirty_behind
          and "085c84f" in dirty_behind, dirty_behind)
    clean_fresh = said(label="11bce31", dirty=False, fabric="11bce31", behind=False)
    check("T-0196: a clean bundle at the running revision claims neither",
          "dirty" not in clean_fresh and "moved since" not in clean_fresh
          and "stale" not in clean_fresh, clean_fresh)
    moved = said(label="11bce31", dirty=False, fabric="11bce31", behind=False, stale=True)
    check("T-0196: a bundle the source has outrun is named stale",
          "stale" in moved and "no longer exists" in moved, moved)
    unknown = said(label="x", dirty=False, fabric="x", behind=False, stale=None)
    check("T-0196: an unknown hash is drawn as unknown, never as fresh",
          "unknown" in unknown and "stale" not in unknown, unknown)


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
        check("an event the fold could not place is counted, not silently dropped",
              doc["unplaced_events"] == 1,
              json.dumps({k: doc[k] for k in ("unplaced_events",)}))
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
                # T-0228: /api/agents was advertised by the 404 body (and by
                # web/src/api.js:54) but the `startswith("/api/")` catch-all was
                # dispatched before its branch, so the endpoint 404ed while
                # naming itself. Prove the endpoint answers and, stronger, that
                # the 404 body's own list cannot disagree with the dispatch:
                # every endpoint it advertises must answer 200.
                agents = json.loads(urllib.request.urlopen(url + "/api/agents", timeout=20).read().decode())
                check("serve answers /api/agents instead of its own 404",
                      agents.get("agents") == doc.get("agents"), json.dumps(agents)[:200])
                check("the agents payload names the viewer it answered as",
                      agents.get("viewer") == doc.get("viewer"), json.dumps(agents)[:200])
                try:
                    urllib.request.urlopen(url + "/api/no-such-endpoint", timeout=20)
                    advertised, bad404 = [], "no 404 for an unknown api path"
                except urllib.error.HTTPError as e:
                    bad404 = "" if e.code == 404 else f"got {e.code}"
                    advertised = json.loads(e.read().decode()).get("endpoints", [])
                check("an unknown api path 404s and lists the real endpoints",
                      bad404 == "" and advertised, bad404 or str(advertised))
                for label in advertised:
                    ep = label.partition(" ")[0]
                    # The check is "the body advertises a route and the route
                    # answers", and a POST route answers a POST. This used to key
                    # on the exact suffix `(POST, --allow-write)`, so `/rpc (POST)`
                    # -- a POST-only route that is advertised in the same list --
                    # was probed with a GET, got the 405 its own handler documents
                    # for a GET, and was reported as an endpoint that does not
                    # answer. A listing that says POST and a probe that sends GET
                    # cannot agree, however right both halves are.
                    if "(POST" in label:
                        req = urllib.request.Request(f"{url}{ep}", method="POST", data=b"{}",
                                                     headers={"Content-Type": "application/json"})
                    else:
                        req = f"{url}{ep}"
                    try:
                        with urllib.request.urlopen(req, timeout=20) as r:
                            code = r.status
                    except urllib.error.HTTPError as e:
                        code = e.code
                    check(f"the 404 body advertises {ep} and it answers 200",
                          code == 200, f"got {code}")
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
                # `--private` since T-0230: this probe is about *who the writer
                # ends up being*, and `hello` is in SEALED_DIVERGENT, where the
                # public channel is shut. Before the fix the write reached the
                # private log because the phase happened to be closed -- the
                # silent downgrade the card names -- so the probe asserted a
                # destination nobody had asked for. The destination is declared
                # now, and the checks below still read the same two logs: the
                # server's identity, not the claimed name.
                r = post(url2, ["say", "--private", "--as", "attacker", "--channel", "hello",
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

    print("== the fold publishes unassigned, hours and the claim (T-0226/7, T-0212) ==")
    unassigned_rows_hours_and_the_claim()

    print("== reports.blocked means an unmet dependency (C4) ==")
    blocked_means_unmet_dependency()

    print("== the header's phase names the channel it came from (T-0252) ==")
    phase_provenance_names_the_channel()

    print("== a folded card carries the author its created event names (T-0250) ==")
    created_by_comes_from_the_created_event()

    print("== an edit event moves the field, and an unknown name is counted (T-0246) ==")
    a_task_edit_moves_the_field_the_board_draws()

    print("== a room's opener is not evicted by a second voice, and a human stranger cannot open it (T-0249) ==")
    room_gate_keeps_the_opener_and_refuses_the_stranger()

    print("== the page names the build it was drawn by, and says whether it was dirty (T-0196) ==")
    a_dirty_bundle_is_stated_on_the_page()

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("failed:")
        for name in failed:
            print(f"  - {name}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
