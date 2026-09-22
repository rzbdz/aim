#!/usr/bin/env python3
"""T-0217, server half: `GET /api/flow` must be a dense, reconcilable series.

The endpoint exists so a machine can compute "is the pipeline saturated" from
the store's own events without scraping the HTML. Two of these checks are the
reason the file exists rather than a hand-read of the JSON:

  * the series is folded from the **raw** event list. `fold_tasks` erases a
    retracted card and drops a record it cannot place, so a series folded
    through it could publish neither `unplaced` nor `retracted`. The test folds
    the same events both ways and asserts the two disagree in exactly the way
    the contract predicts.
  * the dispatcher strips the query string off `self.path` at `aimboard/cli.py`
    before the flow handler runs. If the handler parsed the stripped path,
    every parameter would silently become its default -- `window=1h` would
    answer 144 buckets. The HTTP check asserts `window=1h` answers 6.

Run: python3 tests/test_flow_api.py     (exit code = number of failures)
"""
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BOARD = HERE / "bin" / "aimboard.py"
sys.path.insert(0, str(HERE))

from aimboard.fold import flow_series, fold_tasks, parse_span   # noqa: E402

NOW = datetime(2026, 9, 22, 12, 5, 0, tzinfo=timezone.utc)   # end 12:10, 1h -> 11:10
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))


def ev(ts, event, task, actor="codex", **kw):
    return {"ts": ts, "event": event, "task": task, "actor": actor, **kw}


def row_at(series, start):
    for row in series:
        if row["start"] == start:
            return row
    return None


EVENTS = [
    ev("2026-09-22T11:10:00.000Z", "created", "T-1"),
    ev("2026-09-22T11:25:00.000Z", "created", "T-2", "claude-session1"),
    ev("2026-09-22T11:25:00.500Z", "moved", "T-2", "claude-session1", to="done"),
    ev("2026-09-22T11:29:59.999Z", "created", "T-3"),                     # [11:20,11:30)
    ev("2026-09-22T11:30:00.000Z", "created", "T-4"),                     # [11:30,11:40)
    ev("2026-09-22T11:35:00.000Z", "moved", "T-99", to="done"),           # never created
    ev("2026-09-22T11:40:00.000Z", "created", "T-5"),
    ev("2026-09-22T11:40:00.020Z", "created", "T-6"),
    ev("2026-09-22T11:40:00.040Z", "created", "T-7"),
    ev("2026-09-22T11:50:00.000Z", "created", "T-8", "claude-session1"),
    ev("2026-09-22T11:50:30.000Z", "retracted", "T-8", "human"),
]


def direct_checks():
    print("== flow_series() shape and density ==")
    r = flow_series(EVENTS, now=NOW, bucket="10m", window="1h", channels=["hello"],
                    digest="DIGEST-X", tasks_sha256="SHA-X")
    check("series is dense: exactly window.buckets rows",
          len(r["series"]) == 6 and r["window"]["buckets"] == 6,
          f"{len(r['series'])} rows, window.buckets={r['window']['buckets']}")
    check("bucket width is stated once, in seconds",
          r["bucket"]["width_seconds"] == 600 and r["bucket"]["key"] == "start",
          json.dumps(r["bucket"]))
    check("bucket alignment is named as floor(ts,600s) in UTC",
          r["bucket"]["alignment"] == "floor(ts,600s) in UTC" and r["bucket"]["timezone"] == "UTC",
          json.dumps(r["bucket"]))
    from aimboard.fold import _epoch
    check("every series start is a multiple of the width from the epoch",
          all(_epoch(row["start"]) % 600 == 0 for row in r["series"]))
    check("the window is bounded by those starts",
          r["window"]["start"] == "2026-09-22T11:10:00Z" and r["window"]["end"] == "2026-09-22T12:10:00Z",
          json.dumps(r["window"]))
    check("window.data_start names the store's first event, not the window start",
          r["window"]["data_start"] == "2026-09-22T11:10:00.000Z", str(r["window"]["data_start"]))
    check("the width is never repeated on a row", all("width_seconds" not in row for row in r["series"]))

    print("== half-open [start, start+width) ==")
    b = flow_series([ev("2026-09-22T11:09:59.999Z", "created", "T-a"),
                     ev("2026-09-22T11:10:00.000Z", "created", "T-b"),
                     ev("2026-09-22T12:10:00.000Z", "created", "T-c")],
                    now=NOW, bucket="10m", window="1h")
    check("an event one millisecond before the window is not counted", b["totals"]["opened"] == 1,
          f"opened={b['totals']['opened']}")
    check("an event exactly on the lower bound is counted",
          row_at(b["series"], "2026-09-22T11:10:00Z")["opened"] == 1)
    check("an event exactly on the exclusive end is not counted", b["totals"]["opened"] == 1)

    print("== counts, actor breakdown, first/last within a bucket ==")
    check("totals.opened counts recorded created events", r["totals"]["opened"] == 8,
          str(r["totals"]))
    check("totals.done counts recorded moved->done only", r["totals"]["done"] == 1, str(r["totals"]))
    r20 = row_at(r["series"], "2026-09-22T11:20:00Z")
    check("a bucket reports who opened its work",
          r20["opened_by"] == {"claude-session1": 1, "codex": 1}, json.dumps(r20["opened_by"]))
    check("a bucket reports who closed its work", r20["done_by"] == {"claude-session1": 1})
    check("opened_first_ts/opened_last_ts span the bucket's opens",
          r20["opened_first_ts"] == "2026-09-22T11:25:00.000Z"
          and r20["opened_last_ts"] == "2026-09-22T11:29:59.999Z",
          f"{r20['opened_first_ts']} .. {r20['opened_last_ts']}")
    r40 = row_at(r["series"], "2026-09-22T11:40:00Z")
    check("a 40ms import-like burst is visible as a 40ms span",
          r40["opened"] == 3 and r40["opened_first_ts"] == "2026-09-22T11:40:00.000Z"
          and r40["opened_last_ts"] == "2026-09-22T11:40:00.040Z")
    check("a bucket with no done has null done timestamps and an empty done_by",
          r40["done_first_ts"] is None and r40["done_by"] == {})

    print("== the series is folded from raw events, not from fold_tasks ==")
    items, unknown = fold_tasks(EVENTS)
    r8 = row_at(r["series"], "2026-09-22T11:50:00Z")
    check("fold_tasks erases the retracted card", "T-8" not in items)
    check("...and drops the unplaceable event into `unknown`", unknown == 1, str(unknown))
    check("the flow series still publishes the retraction, per bucket",
          r8["retracted"] == 1, json.dumps(r8))
    check("the flow series still counts the retracted creation as an event",
          r8["opened"] == 1)
    check("the flow series publishes the unplaceable event instead of dropping it",
          row_at(r["series"], "2026-09-22T11:30:00Z")["unplaced"] == 1,
          json.dumps(row_at(r["series"], "2026-09-22T11:30:00Z")))
    check("an unplaceable done is not counted as done", r["totals"]["done"] == 1)
    check("sources.reconcile: opened - retracted == live recorded items",
          r["sources"]["store_recorded"] == 7 and r["sources"]["retracted_events"] == 1,
          json.dumps(r["sources"]))

    print("== idle gap, named ==")
    check("the longest silent window is named with both ends and a duration",
          r["idle_gap"] == {"from": "2026-09-22T11:10:00.000Z", "to": "2026-09-22T11:25:00.000Z",
                            "minutes": 15}, json.dumps(r["idle_gap"]))
    check("a window with one event has no idle gap to name",
          flow_series([EVENTS[0]], now=NOW, bucket="10m", window="1h")["idle_gap"] is None)

    print("== hours are null until estimate_hours exists ==")
    check("every hours field is null when no record carries estimate_hours",
          all(row["hours_opened"] is None and row["hours_done"] is None for row in r["series"])
          and r["totals"]["hours_opened"] is None and r["totals"]["hours_done"] is None)
    check("sources says why: 0 estimate_hours records, 0 from seed",
          r["sources"]["estimate_hours_records"] == 0
          and r["sources"]["estimate_hours_from_seed"] == 0, json.dumps(r["sources"]))
    full = flow_series([ev("2026-09-22T11:15:00.000Z", "created", "T-a", estimate_hours=2.5),
                        ev("2026-09-22T11:16:00.000Z", "created", "T-b", estimate_hours=1.5)],
                       now=NOW, bucket="10m", window="1h")
    check("when every counted task carries estimate_hours, the bucket sums them",
          row_at(full["series"], "2026-09-22T11:10:00Z")["hours_opened"] == 4.0
          and full["totals"]["hours_opened"] == 4.0,
          json.dumps(row_at(full["series"], "2026-09-22T11:10:00Z")))
    partial = flow_series([ev("2026-09-22T11:15:00.000Z", "created", "T-a", estimate_hours=2.5),
                           ev("2026-09-22T11:16:00.000Z", "created", "T-b")],
                          now=NOW, bucket="10m", window="1h")
    check("partial coverage is null, not a sum that understates the bucket",
          row_at(partial["series"], "2026-09-22T11:10:00Z")["hours_opened"] is None
          and partial["totals"]["hours_opened"] is None)
    seeded = flow_series([ev("2026-09-22T11:15:00.000Z", "created", "T-a")],
                         now=NOW, bucket="10m", window="1h",
                         seeds={"T-a": {"status": "ready", "estimate_hours": 2.0}})
    check("an estimate on the plan seed is used, and said to have come from the seed",
          row_at(seeded["series"], "2026-09-22T11:10:00Z")["hours_opened"] == 2.0
          and seeded["sources"]["estimate_hours_from_seed"] == 1, json.dumps(seeded["sources"]))
    check("estimate_pts is never converted into hours",
          "estimate_pts" not in json.dumps(r) and "estimate_pts" not in json.dumps(full))

    print("== authority and revision are named ==")
    check("sources names the authority behind each series",
          r["sources"]["opened_series"] == "store events"
          and r["sources"]["done_series"] == "store events", json.dumps(r["sources"]))
    check("sources counts the plan seeds that have no created event",
          "seed_only" in r["sources"] and "items_claiming_done" in r["sources"]
          and "done_from_seed" in r["sources"])
    check("revision carries the caller's digest, tasks hash and last event ts",
          r["revision"]["digest"] == "DIGEST-X" and r["revision"]["tasks_sha256"] == "SHA-X"
          and r["revision"]["store_last_event_ts"] == "2026-09-22T11:50:30.000Z",
          json.dumps(r["revision"]))
    check("the channels the answer covers are stated",
          r["channels"] == ["hello"], json.dumps(r["channels"]))
    check("generated_at is present", r["generated_at"].endswith("Z"))

    print("== parse_span ==")
    check("'10m' is 600s and '24h' is 86400s", parse_span("10m") == 600 and parse_span("24h") == 86400)
    check("a unitless number is not a span", parse_span("10") is None)
    check("junk is rejected rather than defaulted", parse_span("") is None and parse_span("10x") is None)
    try:
        flow_series([], now=NOW, bucket="10x", window="1h")
        check("flow_series refuses a bad bucket", False, "no ValueError")
    except ValueError:
        check("flow_series refuses a bad bucket", True)


def serve(root):
    proc = subprocess.Popen([sys.executable, "-u", str(BOARD), "serve", "--root", str(root),
                             "--port", "0", "--as", "human"],
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


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def http_checks():
    print("== GET /api/flow over HTTP, on an ephemeral port ==")
    root = Path(tempfile.mkdtemp(prefix="flow-api-"))
    write_json(root / "registry.json", {"agents": {
        "human": {"id": "human", "kind": "human"},
        "codex": {"id": "codex", "kind": "codex"}}})
    write_json(root / "channels" / "hello" / "manifest.json", {
        "id": "hello", "topic": "flow test", "leader": "human",
        "participants": ["codex"], "barrier": {"phase": "CLOSED"}})
    now = time.time()
    def ago(minutes):
        return datetime.fromtimestamp(now - minutes * 60, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    lines = [
        ev(ago(50), "created", "T-1"),
        ev(ago(30), "created", "T-2", "claude-session1"),
        ev(ago(29), "moved", "T-2", "claude-session1", to="done"),
        ev(ago(5), "created", "T-3"),
    ]
    (root / "channels" / "hello" / "tasks.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")

    url, proc = serve(root)
    try:
        check("the board serves on an ephemeral port, not 8777", url is not None)
        if not url:
            return
        def get(path):
            req = urllib.request.Request(url + path)
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.headers.get("Content-Type", ""), exc.read().decode()

        status, ctype, body = get("/api/flow?bucket=10m&window=1h")
        doc = json.loads(body)
        check("the query string reaches the handler: window=1h is 6 buckets",
              doc["window"]["buckets"] == 6 and doc["bucket"]["width_seconds"] == 600,
              json.dumps(doc["window"]))
        check("the default window is 24h, so a stripped query would have read 144",
              json.loads(get("/api/flow")[2])["window"]["buckets"] == 144)
        check("the flow answer is JSON, never the SPA", "json" in ctype, ctype)
        check("the series is dense over HTTP too", len(doc["series"]) == 6)
        check("the window covers events the fixture put in the last hour",
              doc["totals"]["opened"] == 3 and doc["totals"]["done"] == 1, json.dumps(doc["totals"]))
        check("window.data_start names the fixture's first event",
              doc["window"]["data_start"] == lines[0]["ts"], str(doc["window"]["data_start"]))
        check("revision.digest is fabric_digest(root), the same value /api/digest answers",
              doc["revision"]["digest"] == json.loads(get("/api/digest")[2])["digest"])
        check("revision.tasks_sha256 hashes the raw tasks.jsonl that was folded",
              doc["revision"]["tasks_sha256"] == subprocess.run(
                  ["sha256sum", str(root / "channels" / "hello" / "tasks.jsonl")],
                  capture_output=True, text=True).stdout.split()[0])
        check("hours are null over HTTP too, with the reason in sources",
              doc["totals"]["hours_opened"] is None
              and doc["sources"]["estimate_hours_records"] == 0)

        status, ctype, body = get("/api/nope")
        check("an unhandled API path is still a 404 carrying JSON, not the app",
              status == 404 and "json" in ctype, f"{status} {ctype}")
        listed = json.loads(body).get("endpoints", [])
        check("the 404 body now lists /api/flow among the real endpoints",
              "/api/flow" in listed, json.dumps(listed))

        status, _, body = get("/api/flow?bucket=10x")
        check("a bad bucket is a 400 that names what it accepts",
              status == 400 and "accepts" in json.loads(body), f"{status} {body[:120]}")
        status, _, body = get("/api/flow?window=1h&provenance=import")
        check("an unsupported provenance is refused, not silently answered",
              status == 400 and "provenance" in json.loads(body), f"{status} {body[:120]}")
        status, _, body = get("/api/flow?channel=nope")
        check("an unknown channel is a 404 that lists the real ones",
              status == 404 and json.loads(body).get("channels") == ["hello"], f"{status} {body[:160]}")
    finally:
        proc.terminate()
        proc.wait(timeout=20)


def main():
    direct_checks()
    http_checks()
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
