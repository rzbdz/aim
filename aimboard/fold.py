"""Board state is a fold over the log, never a file."""
import re
from datetime import datetime, timedelta, timezone

from .const import TERMINAL
from .const import PLAN_FIELDS
from .primitives import as_list, day_of


_SPAN_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def fold_tasks(events):
    """Board state is a fold over the event log. No board file exists."""
    items, unknown = {}, 0
    retracted = set()
    for ev in events:
        # The store froze as `event: "created"` + `task: "T-0001"`; note 05 section 3
        # wrote the other spelling. Both are accepted here rather than betting on
        # which one wins, because a renderer that silently reads zero events draws a
        # clean empty board and calls it "no work items yet".
        kind = str(ev.get("event") or "")
        kind = kind[5:] if kind.startswith("task.") else kind
        tid = ev.get("task") or ev.get("id")
        if not tid:
            continue
        if kind == "created":
            item = {"id": tid, "events": [], "comments": [], "visibility": "draft"}
            for field in PLAN_FIELDS:
                if field in ev:
                    item[field] = ev[field]
            item["status"] = item.get("status") or "backlog"
            item["blocked_by"] = as_list(item.get("blocked_by"))
            item["tags"] = as_list(item.get("tags"))
            item["created_at"] = ev.get("ts", "")
            items[tid] = item
            # A re-creation clears an earlier retraction: the id is live again.
            retracted.discard(tid)
        elif kind == "retracted":
            # A retraction is an append, not an edit: the record of the mistake
            # stays in the chain (so `aim verify` still covers it and a reader can
            # still see what happened) while the board stops drawing the card. This
            # is the mechanism for an accidental `created` -- hand-editing a
            # hash-chained file is the one repair this fabric must not offer.
            items.pop(tid, None)
            retracted.add(tid)
        elif tid in retracted:
            # Events that arrived after the retraction are not "unknown": the
            # creation *was* seen. Counting them as unknown would report a
            # deliberate retraction as a corrupt store, which is the same
            # false-alarm failure the retraction exists to avoid.
            continue
        elif tid in items:
            item = items[tid]
        else:
            unknown += 1        # an event for a task whose creation we never saw
            continue
        item["events"].append(ev)
        if kind == "moved":
            item["prev_status"] = item.get("status")
            item["status"] = ev.get("to", item.get("status"))
            if ev.get("reason"):
                item["move_reason"] = ev["reason"]
        elif kind == "assigned":
            item["owner"] = ev.get("owner", item.get("owner"))
        elif kind == "linked":
            item["blocked_by"] = sorted(set(item["blocked_by"]) | set(as_list(ev.get("blocked_by"))))
        elif kind == "published":
            item["visibility"] = "published"
        elif kind == "dropped":
            item["status"] = "dropped"
            item["drop_reason"] = ev.get("reason", "")
        elif kind == "commented":
            item["comments"].append({
                "author": ev.get("actor", ""), "ts": ev.get("ts", ""),
                "body": ev.get("body", ""), "visibility": ev.get("visibility", item["visibility"]),
            })
    return items, unknown


def merge_plan(seed, recorded):
    """The store overrides the seed field by field, and every card says which."""
    merged = {}
    for tid, task in seed.items():
        if tid in recorded:
            item = dict(task)
            item.update({k: v for k, v in recorded[tid].items() if k not in ("events", "comments")})
            item["events"] = recorded[tid]["events"]
            item["comments"] = recorded[tid].get("comments", [])
            item["provenance"] = "store + seed"
        else:
            item = dict(task)
            item["events"] = []
            item["comments"] = []
            item["provenance"] = "seed only (not yet in the store)"
        merged[tid] = item
    for tid, item in recorded.items():
        if tid not in merged:
            item = dict(item)
            item["provenance"] = "store only"
            merged[tid] = item
    return merged


def task_history(tasks):
    """Created-at and done-at per work item, from the events themselves.

    Seed items have no history, and are counted as such rather than dated from
    today: a burndown drawn from dates that were guessed is worse than no
    burndown, because it looks like a measurement.
    """
    hist = {}
    for tid, task in tasks.items():
        created = done = None
        for ev in task.get("events") or []:
            kind = str(ev.get("event") or "")
            kind = kind[5:] if kind.startswith("task.") else kind
            if kind == "created" and not created:
                created = ev.get("ts")
            if kind == "moved" and ev.get("to") == "done" and not done:
                done = ev.get("ts")
        hist[tid] = {"created": created, "done": done, "task": task}
    return hist


def drift(seed, recorded):
    """Where the plan and the store disagree. A plan is a promise."""
    out = []
    for tid, task in sorted(seed.items()):
        if tid not in recorded:
            out.append({"id": tid, "field": "status", "plan": task.get("status"), "store": None})
            continue
        for field in ("status", "owner", "due"):
            a, b = task.get(field), recorded[tid].get(field)
            if a and b and a != b:
                out.append({"id": tid, "field": field, "plan": a, "store": b})
    return out


def report_data(tasks, milestones, as_of, days=14):
    """Burndown, throughput and cycle time, folded from the events.

    Every number here comes from a recorded transition or it does not appear.
    Seed items have no history, so they are counted separately and named - a
    chart drawn partly from dates somebody guessed looks like a measurement and
    is not one.
    """
    hist = task_history(tasks)
    dated = {t: h for t, h in hist.items() if h["created"]}
    done = {t: h for t, h in dated.items() if h["done"]}
    cycles = []
    for h in done.values():
        a, b = day_of(h["created"]), day_of(h["done"])
        if a and b:
            cycles.append((b - a).days)
    window = [as_of - timedelta(days=n) for n in range(days - 1, -1, -1)]
    series, throughput = [], {}
    for h in done.values():
        d = day_of(h["done"])
        if d is None:
            continue
        d = d.isoformat()
        throughput[d] = throughput.get(d, 0) + 1
    for d in window:
        key = d.isoformat()
        series.append({"date": key,
                       "remaining": sum(1 for h in dated.values()
                                        if day_of(h["created"]) <= d
                                        and not (h["done"] and day_of(h["done"]) <= d)),
                       "done": throughput.get(key, 0)})
    def unmet_dependency(task):
        """A block is an unmet edge, not the existence of one.

        Carrying a `blocked_by` is not the same as being blocked: a dependency
        whose target is already terminal is met, and a row that carries one is
        not blocked in any reading. Terminal work is excluded outright -- a
        finished item cannot be blocked, whatever edge it carries.
        """
        if task.get("status") in TERMINAL:
            return False
        for dep in task.get("blocked_by") or []:
            if (tasks.get(dep) or {}).get("status") not in TERMINAL:
                return True
        return False

    blocked = [{"id": tid, "title": h["task"].get("title", ""),
                "status": h["task"].get("status", ""), "owner": h["task"].get("owner", ""),
                "blocked_by": h["task"].get("blocked_by") or []}
               for tid, h in hist.items() if unmet_dependency(h["task"])]
    by_milestone = {}
    for mid, m in milestones.items():
        items = [t for t in tasks.values() if t.get("milestone") == mid]
        by_milestone[mid] = {"name": m.get("name", ""), "due": m.get("due", ""),
                             "accept": m.get("accept", ""), "total": len(items),
                             "done": sum(1 for t in items if t.get("status") in TERMINAL)}
    return {"series": series, "throughput": sorted(throughput.items(), key=lambda kv: str(kv[0])),
            "cycle_days": sorted(cycles),
            "median_cycle": (sorted(cycles)[len(cycles) // 2] if cycles else None),
            "recorded": len(dated), "with_history": len(done), "seed_only": len(tasks) - len(dated),
            "blocked": sorted(blocked, key=lambda b: b["id"]), "milestones": by_milestone}


def parse_span(text):
    """'10m' -> 600. None when it is not a span.

    One parser for `bucket` and `window` both. Two slightly different regexes
    is how a request is accepted as a bucket and rejected as a window, or the
    reverse, and the caller never learns which one was reading it.
    """
    m = re.fullmatch(r"(\d+)\s*([smhd])", str(text or "").strip().lower())
    if not m:
        return None
    return int(m.group(1)) * _SPAN_UNITS[m.group(2)]


def _epoch(ts):
    """An ISO-8601 timestamp to seconds since the epoch, or None."""
    if not ts:
        return None
    try:
        # Python 3.10's fromisoformat does not accept the trailing Z the store
        # writes, and a parser that silently returns None for every record is
        # how a chart of an empty store looks exactly like a chart of no work.
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flip(kind):
    kind = str(kind or "")
    return kind[5:] if kind.startswith("task.") else kind


def flow_series(events, now=None, bucket="10m", window="12h", channels=(),
                digest="", tasks_sha256="", seeds=None, provenance="recorded"):
    """The `GET /api/flow` answer: a dense opened/done series, folded from RAW events.

    `events` is the raw `channels/<ch>/tasks.jsonl` list, not `fold_tasks`
    output. `fold_tasks` drops a record whose `created` it never saw and erases
    a retracted card, so a series folded through it could publish neither
    `unplaced` nor `retracted` -- and then a consumer could not reconcile the
    chart against the board it is charting. The counts here are *event* counts;
    the board is a fold of *items*; publishing both is the point.

    Decisions the contract leaves open, named here because each is a place where
    a silent default gets read as a measurement:

      * `opened` counts recorded `created` events, including one later retracted;
        `retracted` publishes the retraction events per bucket, so the board's
        number is `opened - retracted`. The contract's sample agrees: totals 71
        opened against `sources.store_recorded` 70, the extra one being T-0001.
      * `done` counts recorded `moved ... to: done` events only. `dropped` is
        terminal but is not "done", and a plan seed with `status: done` has no
        event at all: it appears in `sources.done_from_seed` and never in the
        series. That is what "which authority produced the number" means here.
      * `unplaced` counts events whose task's `created` was never seen before
        them (fold_tasks' `unknown`), so a store with a broken chain still draws
        a series that says how much of it could not be placed.
      * `opened_inferred` is 0: nothing in this fold is dated by inference. The
        field exists so a later "date the seed from the plan" change cannot slip
        into `opened` without the number moving.
      * `hours_opened`/`hours_done` come from `estimate_hours` and from nothing
        else; `estimate_pts` is not converted. They are `null` while no record
        carries the field (`sources.estimate_hours_records == 0` today) and also
        `null` for a bucket where only some counted tasks carry it, because a
        partial sum presented as the bucket's hours is a substitute value.
      * The window ends at the exclusive end of the bucket containing `now`, so
        every `series[].start` is a multiple of the width and the current,
        partial bucket is included: a chart that omits the bucket happening now
        looks stalled in the middle of a burst.
    """
    width = parse_span(bucket)
    span = parse_span(window)
    if not width:
        raise ValueError("bucket must be an integer and a unit: 30s, 10m, 1h, 1d")
    if not span:
        raise ValueError("window must be an integer and a unit: 30m, 12h, 24h, 7d")
    seeds = seeds or {}
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_epoch = now.timestamp()
    end = int(now_epoch) // width * width + width
    rows_n = max(1, -(-span // width))
    start = end - rows_n * width

    rows, index = [], {}
    for k in range(rows_n):
        st = start + k * width
        row = {"start": _iso(st), "opened": 0, "opened_by": {}, "opened_inferred": 0,
               "opened_first_ts": None, "opened_last_ts": None,
               "done": 0, "done_by": {}, "done_first_ts": None, "done_last_ts": None,
               "hours_opened": None, "hours_done": None, "unplaced": 0, "retracted": 0}
        index[st] = row
        rows.append(row)
    # Private per-bucket piles, stripped before the answer is returned: keeping
    # them off the row means the public shape cannot drift by accident.
    acc = {start + k * width: {"o": [], "d": [], "open_ids": [], "done_ids": []}
           for k in range(rows_n)}

    live, retracted_ids, status, done_ids = set(), set(), {}, set()
    est_created, est_seed = {}, {}
    unplaced_all, retracted_all = 0, 0
    data_start = last_ts = None
    data_start_e = last_e = None
    stamps = {}          # epoch -> the ts string, for the idle gap's endpoints

    for ev in events:
        ts = str(ev.get("ts") or "")
        e = _epoch(ts)
        if e is not None:
            if data_start_e is None or e < data_start_e:
                data_start_e, data_start = e, ts
            if last_e is None or e > last_e:
                last_e, last_ts = e, ts
        kind = _flip(ev.get("event"))
        tid = ev.get("task") or ev.get("id")
        actor = str(ev.get("actor") or "")

        if kind == "created":
            live.add(tid)
            retracted_ids.discard(tid)
            status[tid] = ev.get("status") or "backlog"
            if "estimate_hours" in ev:
                est_created[tid] = ev.get("estimate_hours")
        elif kind == "retracted":
            live.discard(tid)
            retracted_ids.add(tid)
            status.pop(tid, None)
            retracted_all += 1
        elif tid in retracted_ids or tid in live:
            if kind == "moved":
                status[tid] = ev.get("to", status.get(tid))
                if ev.get("to") == "done":
                    done_ids.add(tid)
            elif kind == "dropped":
                status[tid] = "dropped"
        else:
            # An event for a task whose creation the fold never saw. It is not
            # silence and it is not a create; it is counted and skipped, the
            # same way fold_tasks skips it, so the two counts agree.
            unplaced_all += 1
            if e is not None and int(e) // width * width in index:
                index[int(e) // width * width]["unplaced"] += 1
            continue

        if e is None:
            continue
        st = int(e) // width * width
        if st not in index:
            continue
        stamps[e] = ts
        if kind == "created":
            row = index[st]
            row["opened"] += 1
            row["opened_by"][actor] = row["opened_by"].get(actor, 0) + 1
            acc[st]["o"].append((e, ts))
            acc[st]["open_ids"].append(tid)
        elif kind == "retracted":
            index[st]["retracted"] += 1
        elif kind == "moved" and ev.get("to") == "done":
            row = index[st]
            row["done"] += 1
            row["done_by"][actor] = row["done_by"].get(actor, 0) + 1
            acc[st]["d"].append((e, ts))
            acc[st]["done_ids"].append(tid)

    est = dict(est_created)
    for tid, task in seeds.items():
        value = task.get("estimate_hours") if isinstance(task, dict) else None
        if tid not in est and isinstance(value, (int, float)) and not isinstance(value, bool):
            est[tid] = value
            est_seed[tid] = value

    def hours(ids):
        if not est:
            return None              # no record carries estimate_hours: unknowable
        values = [est.get(i) for i in ids]
        if any(v is None for v in values):
            return None              # partial coverage: a sum would understate
        return sum(values)

    for st, pile in acc.items():
        row = index[st]
        if pile["o"]:
            row["opened_first_ts"] = min(pile["o"])[1]
            row["opened_last_ts"] = max(pile["o"])[1]
        if pile["d"]:
            row["done_first_ts"] = min(pile["d"])[1]
            row["done_last_ts"] = max(pile["d"])[1]
        row["hours_opened"] = hours(pile["open_ids"])
        row["hours_done"] = hours(pile["done_ids"])
        row["opened_by"] = dict(sorted(row["opened_by"].items()))
        row["done_by"] = dict(sorted(row["done_by"].items()))

    times = sorted(stamps)
    idle = None
    if len(times) >= 2:
        gap, a, b = max((b - a, a, b) for a, b in zip(times, times[1:]))
        if gap > 0:
            idle = {"from": stamps[a], "to": stamps[b], "minutes": int(round(gap / 60.0))}

    merged = {}
    for tid in set(status) | set(seeds):
        merged[tid] = (status.get(tid)
                       or (seeds.get(tid) or {}).get("status") or "backlog")
    claiming_done = [t for t, v in merged.items() if v == "done"]
    sources = {
        # Which authority produced each number. The done series is recorded
        # events only, which is exactly why it reads 3 while 45 items claim
        # `status: done`: the other 42 are inherited from plan seeds.
        "opened_series": "store events",
        "done_series": "store events",
        "provenance": provenance,
        "store_recorded": len(live),
        "seed_only": len([i for i in seeds if i not in live]),
        "items_claiming_done": len(claiming_done),
        "done_from_seed": len([t for t in claiming_done if t not in done_ids]),
        "retracted_events": retracted_all,
        "unplaced_events": unplaced_all,
        # 0 today. It is the reason every hours field is null; a consumer that
        # sees null can tell "no estimate exists" from "the estimates are 0".
        "estimate_hours_records": len(est),
        "estimate_hours_from_seed": len(est_seed),
    }

    return {
        "generated_at": datetime.fromtimestamp(now_epoch, timezone.utc)
                                .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "revision": {"digest": digest, "tasks_sha256": tasks_sha256,
                     "store_last_event_ts": last_ts},
        "channels": list(channels),
        "bucket": {"width_seconds": width, "key": "start",
                   "alignment": f"floor(ts,{width}s) in UTC", "timezone": "UTC"},
        "window": {"requested": window, "start": _iso(start), "end": _iso(end),
                   "buckets": rows_n, "data_start": data_start},
        "series": rows,
        "totals": {"opened": sum(r["opened"] for r in rows),
                   "done": sum(r["done"] for r in rows),
                   "hours_opened": hours([i for st in acc for i in acc[st]["open_ids"]]),
                   "hours_done": hours([i for st in acc for i in acc[st]["done_ids"]])},
        "idle_gap": idle,
        "sources": sources,
    }
