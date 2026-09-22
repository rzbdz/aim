"""Board state is a fold over the log, never a file."""
from datetime import timedelta

from .const import TERMINAL
from .const import PLAN_FIELDS
from .primitives import as_list, day_of


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
    blocked = [{"id": tid, "title": h["task"].get("title", ""),
                "status": h["task"].get("status", ""), "owner": h["task"].get("owner", ""),
                "blocked_by": h["task"].get("blocked_by") or []}
               for tid, h in hist.items()
               if (h["task"].get("blocked_by") or h["task"].get("status") == "blocked")]
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
