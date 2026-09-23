#!/usr/bin/env python3
"""T-0168: the state payload stays JSON-serializable once a task completes.

`/api/state` is one payload, assembled by `aimboard.api.payload`, and its
`reports` section is folded by `aimboard.fold.report_data`. Once a task reached
`done` that fold keyed its throughput dict by `datetime.date` and published it
as `sorted(throughput.items())` -- a list of pairs, so the date travelled as a
*value* and `json.dumps` raised `Object of type date is not JSON serializable`.
The dashboard was a 500 the moment any card finished.

The check is hermetic: a throwaway AIM_ROOT under /tmp, one task moved
created -> ready -> doing -> review -> done through the real `aim` CLI, then the
same payload path the endpoint calls. Three of these are the reason the file
exists rather than a hand-read of the JSON at 127.0.0.1:8777:

  * `json.dumps` runs over the *whole* payload, so a date hiding in a section
    nobody thought to look at is caught, not just one in `throughput`;
  * `throughput` rows are exactly `[ISO date string, count]` -- a row that kept
    the count but went back to a date object still fails, which is the shape the
    fix actually bought;
  * the previous implementation of `report_data` (read out of git at the commit
    that fixed it) is run over the same fabric and must *still* raise. A test
    that only asserts the new shape cannot tell "fixed" from "throughput went
    empty", and the card's acceptance asks for both halves.

Measured at revision `536433e` with a dirty working tree (`aimboard/api.py`,
`aimboard/cli.py`, `aimboard/gate.py` modified); `/api/revision` reports
`stale: true`, so the built bundle is older than the source measured here. The
live endpoint was read once as well: `GET /api/state` -> 200 with
`reports.throughput == [["2026-09-22", 14]]`. This test does not touch it --
port 8777 belongs to the leader.

Run: python3 tests/test_state_json.py     (exit code = number of failures)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
AIM = HERE / "bin" / "aim"
sys.path.insert(0, str(HERE))

from aimboard import api                                    # noqa: E402
from aimboard.fabric import load_fabric                     # noqa: E402

ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
result = []


def check(name, ok, detail=""):
    result.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))


def aim(env, *argv):
    return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                          env=env, capture_output=True, text=True, timeout=120)


def date_values(obj, path="$"):
    """Every place a date/datetime is hiding in the payload, with its path.

    `json.dumps` reports the first one and stops, which is fine for a human and
    useless for a test that has to say what it found. A `datetime` is a `date`,
    so one isinstance covers both.
    """
    if isinstance(obj, (date, datetime)):
        return [(path, repr(obj))]
    if isinstance(obj, dict):
        found = []
        for key, val in obj.items():
            found += date_values(key, f"{path}.<key>") + date_values(val, f"{path}.{key}")
        return found
    if isinstance(obj, (list, tuple)):
        found = []
        for i, val in enumerate(obj):
            found += date_values(val, f"{path}[{i}]")
        return found
    return []


def build_completed_task(root):
    """One card, start to finish, through the CLI that writes the record."""
    env = dict(os.environ, AIM_ROOT=str(root))
    for argv in (("init",),
                 ("register", "--as", "worker", "--kind", "codex"),
                 ("register", "--as", "boss", "--kind", "human"),
                 ("new-channel", "--id", "statejson", "--topic", "state json",
                  "--participants", "worker,boss", "--leader", "boss")):
        p = aim(env, *argv)
        if p.returncode != 0:
            return None, f"aim {' '.join(argv)} -> rc {p.returncode}: {p.stderr.strip()}"
    p = aim(env, "task", "new", "--as", "boss", "--channel", "statejson",
            "--title", "a task that finishes", "--owner", "worker",
            "--accept", "the state payload serialises")
    ids = re.findall(r"T-\d+", p.stdout)
    if p.returncode != 0 or not ids:
        return None, f"aim task new -> rc {p.returncode}: {p.stdout}{p.stderr}"
    tid = ids[0]
    for to in ("ready", "doing", "review", "done"):
        # T-0251: `review -> done` requires the measurement the closer made, so
        # the fixture states one on the closing edge. It is a fixture line, not a
        # claim about the payload path this file is about -- without it the walk
        # stops at `done` and every check below reads a fabric with no completed
        # task, which is how this file failed (3 passed, 5 failed) when the gate
        # landed.
        extra = (["--evidence", "T-0251 fixture: the card is walked to done for the payload"]
                 if to == "done" else [])
        p = aim(env, "task", "move", "--as", "boss", "--channel", "statejson",
                "--id", tid, "--to", to, *extra)
        if p.returncode != 0:
            return tid, f"moved -> {to}: rc {p.returncode}: {p.stderr.strip()}"
    return tid, ""


def events_of(root):
    path = root / "channels" / "statejson" / "tasks.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def previous_implementation_check(state):
    """The same fabric folded by report_data as it was before the fix.

    Read out of git rather than copied into this file: a copy would be a second
    implementation that drifts, and the question is what the shipped code did.
    """
    src = subprocess.run(["git", "-C", str(HERE), "show", "a266655^:aimboard/fold.py"],
                         capture_output=True, text=True)
    if src.returncode != 0:
        print("  SKIP  previous implementation could not be read from git "
              f"({src.stderr.strip() or 'no a266655^'}); this check was not made")
        return
    old = types.ModuleType("aimboard.fold_before_a266655")
    old.__package__ = "aimboard"
    exec(compile(src.stdout, "fold-before-a266655.py", "exec"), old.__dict__)
    real = api.report_data
    try:
        api.report_data = old.report_data
        try:
            json.dumps(api.payload(state, "boss", {}), ensure_ascii=False)
            raised = ""
        except TypeError as exc:
            raised = f"{type(exc).__name__}: {exc}"
    finally:
        api.report_data = real
    check("the previous implementation still raises, so this test can tell them apart",
          "date is not JSON serializable" in raised, f"raised: {raised or 'nothing'}")


def main():
    root = Path(tempfile.mkdtemp(prefix="state-json-", dir="/tmp"))
    try:
        tid, detail = build_completed_task(root)
        check("the record holds a created event and a moved->done event",
              bool(tid) and not detail, detail or f"task {tid}")
        events = events_of(root)
        check("created is recorded", any(e.get("event") == "created" and e.get("task") == tid
                                         for e in events),
              f"events={json.dumps(events)[:400]}")
        done_events = [e for e in events if e.get("event") == "moved" and e.get("task") == tid
                       and e.get("to") == "done"]
        check("moved->done is recorded", len(done_events) == 1,
              f"moved->done rows: {len(done_events)}")

        as_of = date.today()
        state = load_fabric(root, ["plan/*.json"], as_of)
        payload = api.payload(state, "boss", {})
        reports = payload["reports"]
        check("the payload path has at least one completed task",
              reports["with_history"] >= 1, f"with_history={reports['with_history']}")

        try:
            json.dumps(payload, ensure_ascii=False)
            serialised, err = True, ""
        except TypeError as exc:
            serialised, err = False, f"{type(exc).__name__}: {exc}"
        check("json.dumps(the /api/state payload) succeeds", serialised, err)

        hidden = date_values(payload)
        check("no date or datetime value survives anywhere in the payload",
              not hidden, f"{len(hidden)} found, first {hidden[0] if hidden else ''}")

        throughput = reports["throughput"]
        rows_ok = (isinstance(throughput, list) and throughput and all(
            isinstance(row, (list, tuple)) and len(row) == 2
            and isinstance(row[0], str) and ISO_DAY.match(row[0])
            and isinstance(row[1], int) and not isinstance(row[1], bool)
            for row in throughput))
        check("throughput is a list of [ISO date string, count] rows", rows_ok,
              f"throughput={throughput!r}")
        if rows_ok and done_events:
            day = str(done_events[0].get("ts", ""))[:10]
            counts = dict((k, v) for k, v in throughput if isinstance(k, str))
            check("the one row is the day the task was moved to done, counted once",
                  counts.get(day) == 1 and len(counts) == 1,
                  f"rows={counts} recorded done day={day}")

        previous_implementation_check(state)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    failed = [r for r in result if not r[1]]
    print(f"\n{len(result) - len(failed)} passed, {len(failed)} failed")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
