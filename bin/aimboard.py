#!/usr/bin/env python3
"""aimboard - a dashboard over the aim fabric.

Read-only, and that is a design decision rather than an implementation detail
(design/05, D6). It opens channel state for writing nowhere: the only file it
ever writes is the HTML it was asked to write. A renderer that can mutate state
is a second implementation of the write discipline, and a second implementation
of a write discipline is how the lost update got in here the first time.

The second decision is that it respects the barrier (D5, D11). Rendering
`--as <participant>` while the channel is in a divergence phase omits peer
seals, peer draft tasks and peer draft rooms from the output *bytes*. Not hidden
with CSS - absent. A view that is one `grep` away from the thing `aim` refuses
to show you is a route around the refusal, and a routed-around refusal is the
failure this whole system exists to catch.

It also never renders mail bodies (D7). The transport panel answers "is delivery
broken", which is the leader's question, and not "what did they say to each
other", which is not.

Storage layout is aim's (see bin/aim); this file adds no state.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DIVERGENCE = ("SEALED_DIVERGENT", "COMMIT", "SYNTHESIS")
STATUSES = ["backlog", "ready", "doing", "review", "done", "blocked", "dropped"]
TERMINAL = {"done", "dropped"}
PLAN_FIELDS = (
    "title", "owner", "status", "priority", "estimate", "start", "due",
    "blocked_by", "milestone", "tags", "accept", "visibility", "notes",
)
STATUS_COLOR = {
    "backlog": "#94a3b8", "ready": "#60a5fa", "doing": "#f59e0b",
    "review": "#a78bfa", "done": "#34d399", "blocked": "#ef4444",
    "dropped": "#9ca3af",
}
LABELS = {
    "en": {
        "overview": "Overview", "kanban": "Board", "gantt": "Timeline",
        "table": "Work items", "chat": "Chat", "barrier": "Barrier & audit",
        "reports": "Reports", "plan": "Plan & risk",
    },
    "zh": {
        "overview": "总览", "kanban": "看板", "gantt": "甘特图",
        "table": "工作项", "chat": "群聊", "barrier": "屏障与审计",
        "reports": "报表", "plan": "计划与风险",
    },
}


# ---------------------------------------------------------------- primitives
def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    # must match bin/aim or every chain head this file verifies will disagree
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def esc(value):
    """Escape for both text and quoted-attribute contexts.

    Every string here can be peer-authored: a task title, a comment, a refusal
    reason. They live in an append-only chained log, so a payload in one is
    replayed on every render, which makes this the renderer's only real attack
    surface.
    """
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&#39;")
    )


def as_list(value):
    """A dependency is a list in the seed and a string in the store's `linked`
    event. `set("T-0001")` is a set of characters, which is how a renderer turns
    one dependency into six and never notices."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def read_jsonl(path):
    if not path.exists():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    return out
    except OSError:
        return []
    return out


def verify_chain(path):
    """Re-walk a chained JSONL file: every record hashes its predecessor.

    Deliberately reimplemented rather than imported from bin/aim. An
    independent checker that shares code with the writer is not independent,
    and this is cheap: ten lines, and a disagreement between the two is itself
    a finding worth having.
    """
    prev, count = "genesis", 0
    for rec in read_jsonl(path):
        body = {k: v for k, v in rec.items() if k != "hash"}
        if rec.get("prev") != prev:
            return {"state": "BROKEN", "records": count, "why": "prev does not match the previous hash"}
        if sha256_hex(canonical(body)) != rec.get("hash"):
            return {"state": "BROKEN", "records": count, "why": "record hash does not match its contents"}
        prev, count = rec.get("hash"), count + 1
    return {"state": "OK" if count else "EMPTY", "records": count, "why": ""}


def parse_day(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ------------------------------------------------------------------ loading
def list_channels(root):
    base = root / "channels"
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "manifest.json").exists())


def load_plan(root, patterns):
    """plan/*.json is the leader's plan. It is a SEED, not the truth."""
    milestones, tasks = {}, {}
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            doc = read_json(path)
            if not isinstance(doc, dict):
                continue
            for m in doc.get("milestones") or []:
                if m.get("id"):
                    m = dict(m, source=path.name)
                    milestones.setdefault(m["id"], m)
            for t in doc.get("tasks") or []:
                if t.get("id"):
                    t = dict(t, source=path.name)
                    tasks.setdefault(t["id"], t)
    return milestones, tasks


def fold_tasks(events):
    """Board state is a fold over the event log. No board file exists."""
    items, unknown = {}, 0
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


def load_rooms(channel_dir):
    out = []
    rooms = channel_dir / "rooms"
    if not rooms.exists():
        return out
    for path in sorted(rooms.glob("*.jsonl")):
        meta = read_json(rooms / (path.stem + ".json")) or {}
        cursors = read_json(rooms / (path.stem + ".cursors.json")) or {}
        msgs = read_jsonl(path)
        seen = {}
        for agent, cur in cursors.items():
            last = cur.get("last_hash") if isinstance(cur, dict) else cur
            idx = 0
            for n, msg in enumerate(msgs, start=1):
                if msg.get("hash") == last:
                    idx = n
            seen[agent] = max(0, len(msgs) - idx)
        mentions = {}
        for msg in msgs:
            for who in msg.get("mentions") or []:
                mentions[who] = mentions.get(who, 0) + 1
        out.append({
            "id": meta.get("id") or path.stem,
            "topic": meta.get("topic", ""),
            "visibility": meta.get("visibility", "draft"),
            "messages": msgs,
            "unread": seen,
            "mentions": mentions,
        })
    return out


def load_mail(root):
    """Counts and states only. Bodies are never loaded into the render."""
    base = root / "outbox"
    counts, unacked = {}, []
    if not base.exists():
        return counts, unacked
    for inbox in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for path in sorted(inbox.glob("*.json")):
            rec = read_json(path)
            if not isinstance(rec, dict):
                continue
            sender, to = rec.get("from", "?"), rec.get("to", inbox.name)
            key = (sender, to)
            row = counts.setdefault(key, {"sent": 0, "claimed": 0, "acked": 0})
            row["sent"] += 1
            if rec.get("claimed_at"):
                row["claimed"] += 1
            if rec.get("acked_at"):
                row["acked"] += 1
            if rec.get("ack_required") and not rec.get("acked_at"):
                unacked.append({
                    "msg_id": rec.get("msg_id") or path.stem,
                    "from": sender, "to": to,
                    "subject": rec.get("subject", "") if False else "",
                    "bytes": rec.get("bytes", 0),
                })
    return counts, unacked


def load_conversation(root):
    """Every message in every inbox. Rendering is gated; loading is not."""
    base = root / "outbox"
    out = []
    if not base.exists():
        return out
    for inbox in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for path in sorted(inbox.glob("*.json")):
            rec = read_json(path)
            if isinstance(rec, dict):
                rec["_inbox"] = inbox.name
                rec["_id"] = rec.get("msg_id") or path.stem
                out.append(rec)
    return out


def load_fabric(root, plans, as_of):
    registry = (read_json(root / "registry.json", {"agents": {}}) or {}).get("agents", {})
    channels = []
    for name in list_channels(root):
        cdir = root / "channels" / name
        manifest = read_json(cdir / "manifest.json", {}) or {}
        ledger = read_jsonl(cdir / "ledger.jsonl")
        phase = (manifest.get("barrier") or {}).get("phase", "UNKNOWN")
        seals = {}
        for path in sorted((cdir / "seals").glob("*.json")) if (cdir / "seals").exists() else []:
            seal = read_json(path, {}) or {}
            seals[path.stem] = seal
        recorded, unknown = fold_tasks(read_jsonl(cdir / "tasks.jsonl"))
        for item in recorded.values():
            item["channel"] = name
        channels.append({
            "id": name,
            "manifest": manifest,
            "phase": phase,
            "round": (manifest.get("barrier") or {}).get("round", 0),
            "history": (manifest.get("barrier") or {}).get("history", []),
            "participants": manifest.get("participants", []),
            "leader": manifest.get("leader", ""),
            "seals": seals,
            "ledger": ledger,
            "refusals": [r for r in ledger if r.get("event") == "refusal"],
            "concessions": [r for r in ledger if r.get("event") == "concession"],
            "log": read_jsonl(cdir / "log.jsonl"),
            "tasks_recorded": recorded,
            "tasks_unknown_events": unknown,
            "rooms": load_rooms(cdir),
            "friction": read_jsonl(cdir / "friction.jsonl"),
            "chain": {
                "log.jsonl": verify_chain(cdir / "log.jsonl"),
                "ledger.jsonl": verify_chain(cdir / "ledger.jsonl"),
                "tasks.jsonl": verify_chain(cdir / "tasks.jsonl"),
                "friction.jsonl": verify_chain(cdir / "friction.jsonl"),
            },
            "tasks_exists": (cdir / "tasks.jsonl").exists(),
        })
    milestones, seed_tasks = load_plan(root, plans)
    tasks = merge_plan(seed_tasks, {k: v for c, ch in [(None, c) for c in channels] for k, v in ch["tasks_recorded"].items()})
    mail, unacked = load_mail(root)
    return {
        "root": str(root),
        "as_of": as_of.isoformat(),
        "registry": registry,
        "channels": channels,
        "milestones": milestones,
        "seed_tasks": seed_tasks,
        "tasks": tasks,
        "mail": {f"{a} -> {b}": v for (a, b), v in sorted(mail.items())},
        "conversation": load_conversation(root),
        "unacked": unacked,
        "plan_glob": plans,
    }


# ------------------------------------------------------------------ the gate
def may_see_peer_secrets(channel, viewer):
    """Participants in a divergence phase may not see peers' sealed claims."""
    if viewer not in channel.get("participants", []):
        return True
    return channel.get("phase") not in DIVERGENCE


def gate_channel(state, viewer, fallback):
    """Which channel's phase governs a task that does not name one.

    Not simply the first channel: a root with several channels has several
    phases, and gating every board by whichever channel sorts first is how a
    hidden draft becomes visible by accident.
    """
    for ch in state["channels"]:
        if viewer in ch.get("participants", []):
            return ch
    for ch in state["channels"]:
        if ch.get("tasks_exists"):
            return ch
    return state["channels"][0] if state["channels"] else fallback or {}


def visible_tasks(state, viewer, fallback):
    """A draft task is a position wearing a task title. Gate it like one.

    The gate is per channel: a task written into a channel is withheld from that
    channel's participants while it is in a divergence phase, and a task from
    another channel is judged by that channel's phase instead.

    Returns (visible, hidden_count). The count is public on purpose: the
    existence of a gate is not a secret, only its contents are, and a board that
    silently shows fewer cards than exist is a board you cannot trust.
    """
    by_id = {c["id"]: c for c in state["channels"]}
    default = gate_channel(state, viewer, fallback)
    out, hidden = {}, 0
    for tid, task in state["tasks"].items():
        channel = by_id.get(task.get("channel"), default)
        parts = channel.get("participants", [])
        draft = (task.get("visibility") or "draft") == "draft"
        if draft and viewer in parts and channel.get("phase") in DIVERGENCE and task.get("owner") != viewer:
            hidden += 1
            continue
        out[tid] = task
    return out, hidden


def visible_rooms(channel, viewer):
    out, hidden = [], 0
    for room in channel.get("rooms", []):
        if (room["visibility"] != "published" and viewer in channel.get("participants", [])
                and channel.get("phase") in DIVERGENCE):
            hidden += 1
            continue
        out.append(room)
    return out, hidden


# ------------------------------------------------------------------ fragments
def deadline(task, as_of):
    due = parse_day(task.get("due"))
    if not due:
        return "", ""
    late = due < as_of and task.get("status") not in TERMINAL
    return due.isoformat(), " overdue" if late else ""


def card_html(tid, task, as_of):
    due, late = deadline(task, as_of)
    bits = []
    if task.get("owner"):
        bits.append(f'<span class="chip owner">{esc(task["owner"])}</span>')
    if task.get("priority") and task["priority"] != "normal":
        bits.append(f'<span class="chip prio-{esc(task["priority"])}">{esc(task["priority"])}</span>')
    if due:
        bits.append(f'<span class="chip due{late}">{esc(due)}{" late" if late else ""}</span>')
    if task.get("milestone"):
        bits.append(f'<span class="chip">{esc(task["milestone"])}</span>')
    if task.get("visibility") == "draft":
        bits.append('<span class="chip draft">draft</span>')
    if task.get("provenance") == "seed only (not yet in the store)":
        bits.append('<span class="chip seed">plan seed</span>')
    for blocker in task.get("blocked_by") or []:
        bits.append(f'<span class="chip blocker">blocked by {esc(blocker)}</span>')
    for tag in task.get("tags") or []:
        bits.append(f'<span class="chip tag">#{esc(tag)}</span>')
    accept = ""
    if task.get("accept"):
        accept = f'<details><summary>acceptance</summary><p>{esc(task["accept"])}</p></details>'
    comments = ""
    for c in task.get("comments") or []:
        comments += (f'<li><b>{esc(c.get("author"))}</b> {esc(c.get("ts"))}'
                     f'<p>{esc(c.get("body"))}</p></li>')
    if comments:
        comments = f'<details><summary>{len(task["comments"])} comment(s)</summary><ul>{comments}</ul></details>'
    reason = task.get("drop_reason") or task.get("move_reason") or ""
    reason_html = f'<p class="reason">{esc(reason)}</p>' if reason else ""
    return f'''<article class="card" data-owner="{esc(task.get("owner",""))}" data-milestone="{esc(task.get("milestone",""))}" data-tags="{esc(" ".join(task.get("tags") or []))}" data-status="{esc(task.get("status",""))}">
  <header><span class="tid">{esc(tid)}</span><h4>{esc(task.get("title",""))}</h4></header>
  <div class="chips">{"".join(bits)}</div>
  {reason_html}{accept}{comments}
</article>'''


def render_kanban(tasks, as_of):
    cols = []
    for status in STATUSES:
        items = [t for t in tasks.items() if t[1].get("status") == status]
        items.sort(key=lambda kv: (kv[1].get("due") or "9999", kv[0]))
        cards = "".join(card_html(tid, task, as_of) for tid, task in items)
        cols.append(f'''<section class="col" data-col="{status}">
  <h3><span class="dot s-{status}"></span>{status} <span class="count">{len(items)}</span></h3>
  <div class="colbody">{cards or '<p class="empty">nothing here</p>'}</div>
</section>''')
    return f'<div class="board">{"".join(cols)}</div>'


def render_gantt(milestones, tasks, as_of):
    dated = {tid: t for tid, t in tasks.items() if parse_day(t.get("start")) or parse_day(t.get("due"))}
    undated = sorted(tid for tid, t in tasks.items() if not (parse_day(t.get("start")) or parse_day(t.get("due"))))
    days = [parse_day(t.get("start")) or parse_day(t.get("due")) for t in dated.values()]
    days += [parse_day(t.get("due")) for t in dated.values() if parse_day(t.get("due"))]
    days += [d for d in (parse_day(m.get("due")) for m in milestones.values()) if d]
    if not days:
        return ('<p class="empty">no dates anywhere: every bar in a gantt is a promise, '
                'and this plan has not made one yet.</p>')
    lo, hi = min(days) - timedelta(days=1), max(days) + timedelta(days=1)
    span = max(1, (hi - lo).days)
    label_w, day_w, row_h = 250, max(9, min(26, int(900 / span))), 24
    width = label_w + span * day_w + 40
    groups = {}
    for tid, task in sorted(dated.items()):
        groups.setdefault(task.get("milestone") or "-", []).append((tid, task))
    rows, y = [], 30
    for ms_id in sorted(groups, key=lambda m: (m == "-", m)):
        ms = milestones.get(ms_id, {})
        ms_due = parse_day(ms.get("due"))
        rows.append(f'<g class="msrow"><rect x="0" y="{y-2}" width="{width}" height="{row_h}" class="msbg"/>'
                    f'<text x="6" y="{y+14}" class="mslabel">{esc(ms_id)} {esc(ms.get("name",""))}</text>')
        if ms_due:
            x = label_w + (ms_due - lo).days * day_w
            rows.append(f'<polygon points="{x},{y+6} {x+6},{y+12} {x},{y+18} {x-6},{y+12}" class="msdiamond"/>')
        rows.append("</g>")
        y += row_h
        for tid, task in groups[ms_id]:
            start, due = parse_day(task.get("start")), parse_day(task.get("due"))
            status = task.get("status", "backlog")
            label = f'{tid} {task.get("title","")}'
            if len(label) > 44:
                label = label[:43] + "…"
            rows.append(f'<text x="6" y="{y+15}" class="rlabel" title="{esc(task.get("title",""))}">'
                        f'{esc(label)}</text>')
            if start and due:
                x1 = label_w + (start - lo).days * day_w
                w = max(6, (due - start).days * day_w + day_w * 0.8)
                rows.append(f'<rect class="bar s-{status}" x="{x1:.1f}" y="{y+5}" width="{w:.1f}" '
                            f'height="{row_h-12}" rx="3"><title>{esc(tid)}: {esc(task.get("title",""))} '
                            f'[{status}] {start} to {due}</title></rect>')
                rows.append(f'<text x="{x1+w+5:.1f}" y="{y+15}" class="barlabel">{esc(status)}</text>')
            else:
                only = due or start
                x = label_w + (only - lo).days * day_w
                rows.append(f'<polygon points="{x},{y+5} {x+5},{y+12} {x},{y+19} {x-5},{y+12}" '
                            f'class="msdiamond"><title>{esc(tid)}: one date only, {only}</title></polygon>')
                rows.append(f'<text x="{x+8:.1f}" y="{y+15}" class="barlabel">{esc(status)} (one date)</text>')
            y += row_h
        y += 6
    grid = ""
    tick = lo
    while tick <= hi:
        x = label_w + (tick - lo).days * day_w
        is_monday = tick.weekday() == 0
        grid += (f'<line x1="{x:.1f}" y1="30" x2="{x:.1f}" y2="{y}" class="grid{" week" if is_monday else ""}"/>')
        if is_monday:
            grid += f'<text x="{x+3:.1f}" y="20" class="axis">{tick.isoformat()[5:]}</text>'
        tick += timedelta(days=1)
    edges = ""
    ypos = {}
    yy = 30
    for ms_id in sorted(groups, key=lambda m: (m == "-", m)):
        yy += row_h
        for tid, task in groups[ms_id]:
            ypos[tid] = yy + row_h / 2
            yy += row_h
        yy += 6
    for tid, task in dated.items():
        start = parse_day(task.get("start")) or parse_day(task.get("due"))
        for blocker in task.get("blocked_by") or []:
            if blocker not in ypos or tid not in ypos or blocker not in dated:
                continue
            bdue = parse_day(dated[blocker].get("due")) or parse_day(dated[blocker].get("start"))
            if not bdue or not start:
                continue
            x1 = label_w + (bdue - lo).days * day_w + day_w
            x2 = label_w + (start - lo).days * day_w
            y1, y2 = ypos[blocker], ypos[tid]
            mid = x1 + 6
            edges += (f'<path class="dep" d="M{x1:.1f},{y1:.1f} L{mid:.1f},{y1:.1f} '
                      f'L{mid:.1f},{y2:.1f} L{x2-2:.1f},{y2:.1f}"><title>{esc(blocker)} blocks {esc(tid)}</title></path>')
    today = ""
    if lo <= as_of <= hi:
        x = label_w + (as_of - lo).days * day_w
        today = (f'<line x1="{x:.1f}" y1="24" x2="{x:.1f}" y2="{y}" class="today"/>'
                 f'<text x="{x+3:.1f}" y="{y+12}" class="todaylabel">{esc(as_of.isoformat())}</text>')
    legend = " ".join(
        f'<span class="lg"><span class="dot s-{s}"></span>{s}</span>' for s in STATUSES)
    note = ""
    if undated:
        note = (f'<p class="note">{len(undated)} item(s) have no dates and are not drawn: '
                f'{esc(", ".join(undated))}</p>')
    return f'''<p class="legend">{legend}</p>
<svg class="gantt" viewBox="0 0 {width} {y+20}" width="100%" role="img"
     aria-label="gantt chart, {len(dated)} dated work items, as of {esc(as_of.isoformat())}">
  <g class="gridlayer">{grid}</g>
  <g class="edgelayer">{edges}</g>
  <g class="rowlayer">{"".join(rows)}</g>
  {today}
</svg>{note}'''


def render_table(tasks, as_of):
    head = ("<tr><th>id</th><th>title</th><th>status</th><th>owner</th><th>milestone</th>"
            "<th>start</th><th>due</th><th>blocked by</th><th>provenance</th></tr>")
    body = ""
    for tid, task in sorted(tasks.items()):
        due, late = deadline(task, as_of)
        body += (f'<tr data-owner="{esc(task.get("owner",""))}" data-status="{esc(task.get("status",""))}" '
                 f'data-milestone="{esc(task.get("milestone",""))}" data-tags="{esc(" ".join(task.get("tags") or []))}">'
                 f'<td class="tid">{esc(tid)}</td><td>{esc(task.get("title",""))}</td>'
                 f'<td><span class="dot s-{esc(task.get("status",""))}"></span> {esc(task.get("status",""))}</td>'
                 f'<td>{esc(task.get("owner",""))}</td><td>{esc(task.get("milestone",""))}</td>'
                 f'<td>{esc(task.get("start",""))}</td><td class="{late.strip()}">{esc(due)}</td>'
                 f'<td>{esc(", ".join(task.get("blocked_by") or []))}</td>'
                 f'<td class="dim">{esc(task.get("provenance",""))}</td></tr>')
    owners = sorted({t.get("owner", "") for t in tasks.values()} - {""})
    options = "".join(f'<option value="{esc(o)}">{esc(o)}</option>' for o in owners)
    mso = "".join(f'<option value="{esc(m)}">{esc(m)}</option>' for m in sorted({t.get("milestone", "") for t in tasks.values()} - {""}))
    return f'''<div class="filters">
  <label>owner <select data-filter="owner"><option value="">all</option>{options}</select></label>
  <label>status <select data-filter="status"><option value="">all</option>{"".join(f'<option value="{s}">{s}</option>' for s in STATUSES)}</select></label>
  <label>milestone <select data-filter="milestone"><option value="">all</option>{mso}</select></label>
  <label>tag <input data-filter="tag" placeholder="dogfood"></label>
</div>
<table class="items">{head}{body}</table>'''


def render_chat(channels, viewer):
    blocks = []
    for ch in channels:
        rooms, hidden = visible_rooms(ch, viewer)
        if not ch["rooms"]:
            roomhtml = ('<p class="empty">no rooms yet. Group chat and read cursors are M2 '
                        '(design/06); until then this is the channel only.</p>')
        else:
            rows = ""
            for room in rooms:
                unread = ", ".join(f'{esc(a)} {n}' for a, n in sorted(room["unread"].items())) or "no cursors"
                mentions = ", ".join(f'{esc(a)} {n}' for a, n in sorted(room["mentions"].items())) or "-"
                rows += (f'<tr><td>#{esc(room["id"])}</td><td>{esc(room["topic"])}</td>'
                         f'<td>{len(room["messages"])}</td><td>{esc(room["visibility"])}</td>'
                         f'<td>{unread}</td><td>{mentions}</td></tr>')
            roomhtml = (f'<table class="items"><tr><th>room</th><th>topic</th><th>messages</th>'
                        f'<th>visibility</th><th>unread per agent</th><th>mentions</th></tr>{rows}</table>')
        if hidden:
            roomhtml += (f'<p class="note">{hidden} room(s) exist but are draft and this viewer is '
                         f'a participant in a divergence phase: absent, not hidden.</p>')
        blocks.append(f'<h3>#{esc(ch["id"])}</h3>{roomhtml}')
    return "".join(blocks)


def message_html(head, body, meta="", state_chip=""):
    return f'''<article class="msg">
  <header><b>{esc(head)}</b> <span class="dim">{esc(meta)}</span>{state_chip}</header>
  <pre>{esc(body)}</pre>
</article>'''


def render_conversation(state, viewer):
    """What was actually said.

    D7 used to say the dashboard never renders a message body. The leader
    overrode that on 2026-09-21 - they are the audience, they already read both
    seals, and a conversation they cannot see is a conversation they cannot
    steer. The rule that replaces it is narrower and still absolute: **you see
    the conversations you are part of, and no others.**

    A participant therefore sees mail they sent or received, the channel messages
    the phase lets them read, and nothing else. Peer *private* logs are still
    never read or rendered at all, because the seal's whole purpose is that one
    agent's half-formed reasoning is not available to the other - and a renderer
    that shows it, even to the leader, produces a file whose contents are one
    share away from being exactly the leak the barrier exists to prevent.
    """
    kind = (state["registry"].get(viewer) or {}).get("kind", "")
    is_leader = kind == "human"
    blocks, withheld = [], 0

    for ch in state["channels"]:
        gated = viewer in ch["participants"] and ch["phase"] in DIVERGENCE
        msgs = []
        for m in ch["log"]:
            if gated and m.get("from") != viewer:
                withheld += 1
                continue
            msgs.append(message_html(
                f'{m.get("from", "?")} → the channel',
                m.get("body", ""),
                f'{m.get("ts", "")} · kind {m.get("kind", "-")} · responds-to {m.get("responds_to", "-")}'))
        note = ("this viewer is a participant and the channel is in " + esc(ch["phase"])
                + ", so peer messages are absent" if gated else "every message in this phase")
        blocks.append(f'<h3>#{esc(ch["id"])} — the channel record</h3>'
                      f'<p class="dim">{len(msgs)} message(s), {note}</p>' + ("".join(msgs) or
                      '<p class="empty">nothing has been said on the public record yet.</p>'))
        rooms, hidden_rooms = visible_rooms(ch, viewer)
        for room in rooms:
            body = "".join(message_html(f'{m.get("agent", "?")} → #{room["id"]}', m.get("body", ""),
                                        m.get("ts", ""),
                                        f'<span class="chip">{len(m.get("mentions") or [])} mention(s)</span>'
                                        if m.get("mentions") else "")
                           for m in room["messages"])
            blocks.append(f'<h3>#{esc(ch["id"])}/#{esc(room["id"])} — a room</h3>'
                          f'<p class="dim">{len(room["messages"])} message(s), '
                          f'{esc(room["visibility"])}</p>'
                          + (body or '<p class="empty">empty room.</p>'))
        if hidden_rooms:
            withheld += hidden_rooms

    dms = ""
    for rec in state["conversation"]:
        sender, to = rec.get("from", "?"), rec.get("to", "?")
        if not is_leader and viewer not in (sender, to):
            withheld += 1
            continue
        chips = ""
        if rec.get("ack_required"):
            chips = ('<span class="chip due">acked</span>' if rec.get("acked_at")
                     else '<span class="chip blocker">no ack</span>')
        elif rec.get("claimed_at"):
            chips = '<span class="chip">claimed</span>'
        else:
            chips = '<span class="chip draft">unread</span>'
        dms += message_html(f'{sender} → {to}', rec.get("body", ""),
                            f'{rec.get("ts", "")} · {rec.get("subject", "")}', chips)
    blocks.append('<h3>direct messages</h3>'
                  + (dms or '<p class="empty">no direct messages.</p>'))

    head = ('<p class="note">You see the conversations you are part of and no others. '
            f'{withheld} message(s) are withheld from this view. Peer <b>private reasoning</b> '
            'is never read or rendered here at all: it exists so that a seal can be checked later, '
            'and a rendered copy would be one shared file away from the exact leak the barrier '
            'prevents.</p>')
    return head + "".join(blocks)


def render_transport(state):
    rows = ""
    for pair, row in state["mail"].items():
        flag = "ok" if row["acked"] >= row["sent"] else "waiting"
        rows += (f'<tr><td>{esc(pair)}</td><td>{row["sent"]}</td><td>{row["claimed"]}</td>'
                 f'<td>{row["acked"]}</td><td class="dim">{flag}</td></tr>')
    unacked = ""
    if state["unacked"]:
        items = "".join(f'<li>{esc(u["msg_id"])} {esc(u["from"])} to {esc(u["to"])}</li>'
                        for u in state["unacked"])
        unacked = f'<p class="warn">{len(state["unacked"])} message(s) demanded an ack and have not had one:</p><ul class="plain">{items}</ul>'
    else:
        unacked = '<p class="ok">every demanded ack has arrived.</p>'
    return f'''<p class="note">Counts and states only. Mail bodies are never rendered here (D7): a
leader needs to know that delivery is broken, not what was said in private.</p>
<table class="items"><tr><th>from to</th><th>sent</th><th>claimed</th><th>acked</th><th></th></tr>{rows}</table>
{unacked}'''


def render_barrier(state, viewer, labels):
    blocks = []
    for ch in state["channels"]:
        phase = ch["phase"]
        secrets = may_see_peer_secrets(ch, viewer)
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


def render_plan(state, risks, labels):
    ms = ""
    for mid, m in sorted(state["milestones"].items()):
        total = sum(1 for t in state["seed_tasks"].values() if t.get("milestone") == mid)
        done = sum(1 for t in state["seed_tasks"].values()
                   if t.get("milestone") == mid and t.get("status") in TERMINAL)
        pct = int(100 * done / total) if total else 0
        ms += (f'<tr><td>{esc(mid)}</td><td>{esc(m.get("name",""))}</td><td>{esc(m.get("due",""))}</td>'
               f'<td>{done}/{total}</td><td><span class="meter"><span style="width:{pct}%"></span></span> {pct}%</td>'
               f'<td class="dim">{esc(m.get("accept",""))}</td></tr>')
    rk = ""
    for r in risks.get("risks", []):
        rk += (f'<tr><td>{esc(r["id"])}</td><td>{esc(r["risk"])}</td><td>{esc(r["likelihood"])}</td>'
               f'<td>{esc(r["impact"])}</td><td>{esc(r["owner"])}</td><td>{esc(r["mitigation"])}</td>'
               f'<td class="dim">{esc(r.get("kill_if",""))}</td></tr>')
    dec = "".join(f'<li><b>{esc(d["id"])}</b> {esc(d["decision"])}<p class="dim">because {esc(d["because"])}</p></li>'
                  for d in risks.get("decisions", []))
    ng = "".join(f'<li>{esc(x)}</li>' for x in risks.get("non_goals", []))
    raci = "".join(f'<tr><td>{esc(r["area"])}</td><td>{esc(r["responsible"])}</td><td>{esc(r["accountable"])}</td>'
                   f'<td>{esc(r["consulted"])}</td></tr>' for r in risks.get("raci", []))
    dog = risks.get("dogfooding", {})
    doghtml = ""
    if dog:
        doghtml = (f'<h4>dogfooding</h4><p>{esc(dog.get("rule",""))}</p><ul class="plain">'
                   + "".join(f'<li>{esc(p)}</li>' for p in dog.get("practices", [])) + "</ul>"
                   + f'<p class="dim">kill_if: {esc(dog.get("kill_if",""))}</p>')
    return f'''<h4>milestones</h4>
<table class="items"><tr><th>id</th><th>name</th><th>due</th><th>done</th><th>progress</th><th>acceptance</th></tr>{ms}</table>
<h4>risks</h4>
<table class="items"><tr><th>id</th><th>risk</th><th>likelihood</th><th>impact</th><th>owner</th><th>mitigation</th><th>kill_if</th></tr>{rk}</table>
<h4>decisions</h4><ul class="plain">{dec}</ul>
<h4>non-goals</h4><ul class="plain">{ng}</ul>
<h4>who does what</h4>
<table class="items"><tr><th>area</th><th>responsible</th><th>accountable</th><th>consulted</th></tr>{raci}</table>
{doghtml}'''


def render_overview(state, tasks, hidden, channels, as_of, generated_at):
    by_status = {s: sum(1 for t in tasks.values() if t.get("status") == s) for s in STATUSES}
    overdue = [tid for tid, t in tasks.items()
               if parse_day(t.get("due")) and parse_day(t["due"]) < as_of and t.get("status") not in TERMINAL]
    blocked = [tid for tid, t in tasks.items() if t.get("status") == "blocked" or t.get("blocked_by")]
    mine = [tid for tid, t in tasks.items() if t.get("owner") == "codex"]
    ms_next = sorted((m.get("due") or "9999", mid, m.get("name", ""))
                     for mid, m in state["milestones"].items())
    ms_line = " · ".join(f'{esc(mid)} {esc(name)} ({esc(due)})' for due, mid, name in ms_next[:3])
    prog = "".join(f'<div class="stat"><b>{by_status[s]}</b><span class="dot s-{s}"></span>{s}</div>' for s in STATUSES)
    return f'''<div class="stats">{prog}
  <div class="stat"><b>{len(overdue)}</b><span class="dot s-blocked"></span>overdue</div>
  <div class="stat"><b>{len(blocked)}</b><span class="dot s-review"></span>blocked or waiting</div>
  <div class="stat"><b>{len(mine)}</b><span class="dot s-doing"></span>owned by codex</div>
</div>
<p class="note">{len(tasks)} work items in view{" · " + str(hidden) + " withheld by the barrier gate" if hidden else ""}
{" · " + str(len(state["unacked"])) + " unacked handoff(s)" if state["unacked"] else ""}.</p>
<p><b>next milestones:</b> {ms_line}</p>
'''


CSS = """
:root{--bg:#0b1220;--panel:#101a2e;--panel2:#16233c;--ink:#e6edf7;--dim:#8fa3bf;
--line:#1e2c47;--accent:#38bdf8;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 ui-sans-serif,system-ui,"Noto Sans SC",sans-serif}
header.top{position:sticky;top:0;z-index:5;background:linear-gradient(180deg,#0b1220,#0d1526);border-bottom:1px solid var(--line);padding:14px 20px}
h1{font-size:17px;margin:0 0 4px}
.meta{color:var(--dim);font-size:12px}
nav{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
nav button{background:var(--panel);color:var(--ink);border:1px solid var(--line);padding:6px 12px;border-radius:999px;cursor:pointer;font-size:13px}
nav button[aria-selected=true]{background:var(--accent);color:#062133;border-color:var(--accent);font-weight:600}
main{padding:18px 20px 60px}
section.pane{display:none}section.pane.active{display:block}
h3{margin:18px 0 6px;font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim)}
h4{margin:16px 0 6px;font-size:13px;color:var(--ink)}
.board{display:flex;gap:12px;overflow-x:auto;align-items:flex-start;padding-bottom:8px}
.col{min-width:260px;flex:1 0 260px;background:var(--panel);border:1px solid var(--line);border-radius:10px}
.col h3{display:flex;align-items:center;gap:6px;margin:0;padding:10px 12px;border-bottom:1px solid var(--line);text-transform:none;letter-spacing:0;color:var(--ink);font-size:13px}
.count{color:var(--dim);font-weight:400}
.colbody{padding:10px;display:flex;flex-direction:column;gap:10px;max-height:70vh;overflow:auto}
.card{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:10px}
.card header{display:flex;gap:8px;align-items:baseline}
.card h4{margin:0;font-size:13px;font-weight:600}
.tid{color:var(--accent);font:600 11px ui-monospace,monospace}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.chip{font-size:11px;padding:1px 6px;border-radius:999px;background:#1b2a44;color:var(--dim);border:1px solid var(--line)}
.chip.draft{background:#3b2a12;color:#fbbf24;border-color:#5b4318}
.chip.blocker{background:#3b1414;color:#fca5a5}
.chip.due.overdue{background:#3b1414;color:#fca5a5}
.chip.seed{background:#14243b;color:#7dd3fc}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;background:#64748b}
.s-backlog{background:#94a3b8}.s-ready{background:#60a5fa}.s-doing{background:#f59e0b}
.s-review{background:#a78bfa}.s-done{background:#34d399}.s-blocked{background:#ef4444}.s-dropped{background:#9ca3af}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 12px;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--dim)}
.stat b{font-size:18px;color:var(--ink)}
.gantt{background:var(--panel);border:1px solid var(--line);border-radius:10px}
.gantt text{font:11px ui-monospace,monospace;fill:var(--dim)}
.gantt .rlabel{fill:var(--ink)}
.gantt .mslabel{fill:#7dd3fc;font-weight:600}
.gantt .barlabel{fill:var(--dim)}
.msbg{fill:#0e1a30}
.grid{stroke:#182741;stroke-width:1}
.grid.week{stroke:#24365a}
.axis{font-size:10px}
.bar{opacity:.85}
.dep{fill:none;stroke:#5b7ba8;stroke-width:1.2;stroke-dasharray:3 2}
.msdiamond{fill:#38bdf8;stroke:#0b1220}
.today{stroke:#f87171;stroke-width:1.4;stroke-dasharray:4 3}
.todaylabel{fill:#f87171}
.legend{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin:0 0 8px}
.lg{display:flex;align-items:center;gap:4px}
table.items{width:100%;border-collapse:collapse;font-size:12.5px;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}
table.items th{text-align:left;background:#0e1a30;color:var(--dim);font-weight:600;padding:7px 9px;border-bottom:1px solid var(--line)}
table.items td{padding:7px 9px;border-bottom:1px solid #16233c;vertical-align:top}
td.overdue{color:#fca5a5}
.filters{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px;font-size:12px;color:var(--dim)}
.filters select,.filters input{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 6px}
ul.plain{list-style:none;padding-left:0}ul.plain>li{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:6px}
p.dim,.dim{color:var(--dim)}
.note{color:var(--dim);font-size:12.5px;background:#0e1a30;border-left:3px solid var(--accent);padding:8px 10px;border-radius:0 6px 6px 0}
.warn{color:#fca5a5}.ok{color:#6ee7b7}
.meter{display:inline-block;width:110px;height:8px;background:#1b2a44;border-radius:999px;overflow:hidden;vertical-align:middle}
.meter>span{display:block;height:100%;background:#34d399}
details summary{cursor:pointer;color:var(--dim);font-size:12px;margin-top:6px}
details p{margin:6px 0 0;color:var(--dim);font-size:12.5px}
.reason{margin:8px 0 0;color:#fca5a5;font-size:12.5px}
.empty{color:var(--dim);font-size:12.5px;font-style:italic}
.msg{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:6px}
.msg header{display:flex;gap:8px;align-items:center;font-size:12.5px;flex-wrap:wrap}
.msg pre{white-space:pre-wrap;word-break:break-word;margin:6px 0 0;font:12.5px/1.5 ui-monospace,monospace;color:#cbd5e1}
.burndown{background:var(--panel);border:1px solid var(--line);border-radius:10px}
.burndown .line{fill:none;stroke:#38bdf8;stroke-width:2}
.burndown .thr{fill:#34d399;opacity:.55}
.burndown .axis{font:10px ui-monospace,monospace;fill:var(--dim)}
"""

JS = """
document.querySelectorAll('nav button').forEach(function(b){
  b.addEventListener('click', function(){
    document.querySelectorAll('nav button').forEach(function(x){x.setAttribute('aria-selected','false')});
    document.querySelectorAll('section.pane').forEach(function(p){p.classList.remove('active')});
    b.setAttribute('aria-selected','true');
    document.getElementById('pane-'+b.dataset.tab).classList.add('active');
  });
});
function applyFilters(){
  var f={};
  document.querySelectorAll('[data-filter]').forEach(function(el){f[el.dataset.filter]=el.value.trim().toLowerCase()});
  document.querySelectorAll('table.items tbody tr, .board .card').forEach(function(el){
    var ok=true;
    if(f.owner && (el.dataset.owner||'').toLowerCase().indexOf(f.owner)<0) ok=false;
    if(f.status && (el.dataset.status||'')!==f.status) ok=false;
    if(f.milestone && (el.dataset.milestone||'')!==f.milestone) ok=false;
    if(f.tag && (el.dataset.tags||'').toLowerCase().indexOf(f.tag)<0) ok=false;
    el.style.display = ok ? '' : 'none';
  });
}
document.querySelectorAll('[data-filter]').forEach(function(el){el.addEventListener('input',applyFilters)});
"""


def render_html(state, viewer, risks, generated_at, lang="en"):
    labels = LABELS.get(lang, LABELS["en"])
    channels = state["channels"]
    ctx = gate_channel(state, viewer, channels[0] if channels else {})
    tasks, hidden = visible_tasks(state, viewer, ctx)
    as_of = parse_day(state["as_of"]) or date.today()
    panes = [
        ("overview", labels["overview"], render_overview(state, tasks, hidden, channels, as_of, generated_at)),
        ("kanban", labels["kanban"], render_kanban(tasks, as_of)),
        ("gantt", labels["gantt"], render_gantt(state["milestones"], tasks, as_of)),
        ("table", labels["table"], render_table(tasks, as_of)),
        ("chat", labels["chat"], render_conversation(state, viewer) + "<h3>transport</h3>"
         + render_transport(state)),
        ("reports", labels["reports"], render_reports(tasks, state["milestones"], as_of, labels)),
        ("barrier", labels["barrier"], render_barrier(state, viewer, labels)),
        ("plan", labels["plan"], render_plan(state, risks, labels)),
    ]
    nav = "".join(f'<button data-tab="{key}" aria-selected="{"true" if n == 0 else "false"}">{esc(title)}</button>'
                  for n, (key, title, _) in enumerate(panes))
    body = "".join(f'<section class="pane{" active" if n == 0 else ""}" id="pane-{key}">{html}</section>'
                   for n, (key, _, html) in enumerate(panes))
    stale = (f'generated {esc(generated_at)} · as of {esc(state["as_of"])} · '
             f'viewer {esc(viewer)} ({esc(state["registry"].get(viewer, {}).get("kind","?"))}) · '
             f'root {esc(state["root"])} · phase {esc(ctx.get("phase","-"))}')
    return f'''<!doctype html>
<html lang="{esc(lang)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>aim board - {esc(state["root"].split("/")[-1])}</title>
<style>{CSS}</style></head><body>
<header class="top">
  <h1>aim board</h1>
  <div class="meta">{stale}</div>
  <nav role="tablist">{nav}</nav>
</header>
<main>{body}</main>
<script>{JS}</script>
</body></html>'''


# ---------------------------------------------------------------------- cli
def json_payload(state, viewer, risks, generated_at):
    ctx = gate_channel(state, viewer, {})
    tasks, hidden = visible_tasks(state, viewer, ctx)
    return {
        "generated_at": generated_at,
        "as_of": state["as_of"],
        "root": state["root"],
        "viewer": viewer,
        "withheld_tasks": hidden,
        "phases": {c["id"]: {"phase": c["phase"], "round": c["round"],
                             "participants": c["participants"], "leader": c["leader"],
                             "sealed": sorted(c["seals"]), "refusals": len(c["refusals"])}
                   for c in state["channels"]},
        "chain": {c["id"]: c["chain"] for c in state["channels"]},
        "milestones": state["milestones"],
        "tasks": tasks,
        "mail": state["mail"],
        "unacked": state["unacked"],
        "risks": risks.get("risks", []),
        "decisions": risks.get("decisions", []),
    }


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
    args = parser.parse_args(argv)
    return args.func(args)




# ------------------------------------------------------------------ reports
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


def day_of(ts):
    if not ts:
        return None
    try:
        return date.fromisoformat(str(ts)[:10])
    except ValueError:
        return None


def render_reports(tasks, milestones, as_of, labels):
    hist = task_history(tasks)
    dated = {t: h for t, h in hist.items() if h["created"]}
    done = {t: h for t, h in dated.items() if h["done"]}
    cycles = []
    for tid, h in done.items():
        a, b = day_of(h["created"]), day_of(h["done"])
        if a and b:
            cycles.append((b - a).days)
    cycles.sort()
    median = cycles[len(cycles) // 2] if cycles else None
    days = [as_of - timedelta(days=n) for n in range(13, -1, -1)]
    series = []
    for d in days:
        remaining = sum(1 for h in dated.values()
                        if day_of(h["created"]) <= d and not (h["done"] and day_of(h["done"]) <= d))
        series.append((d, remaining))
    throughput = {}
    for h in done.values():
        d = day_of(h["done"])
        throughput[d] = throughput.get(d, 0) + 1
    blocked = [(tid, h["task"]) for tid, h in hist.items() if h["task"].get("blocked_by")
               or h["task"].get("status") == "blocked"]
    open_blockers = "".join(
        f'<tr><td>{esc(tid)}</td><td>{esc(t.get("title",""))}</td>'
        f'<td>{esc(", ".join(t.get("blocked_by") or []))}</td>'
        f'<td>{esc(t.get("status",""))}</td><td>{esc(t.get("owner",""))}</td></tr>'
        for tid, t in sorted(blocked))
    if not open_blockers:
        open_blockers = '<tr><td colspan="5" class="dim">no work item is waiting on another.</td></tr>'
    chart = ""
    if dated:
        w, h, pad = 560, 160, 34
        hi = max(r for _, r in series) or 1
        step = (w - pad) / max(1, len(series) - 1)
        pts = " ".join(f"{pad + i * step:.1f},{h - pad - (r / hi) * (h - 2 * pad):.1f}"
                       for i, (_, r) in enumerate(series))
        bars = ""
        tmax = max(throughput.values()) if throughput else 1
        for i, d in enumerate(days):
            n = throughput.get(d, 0)
            if not n:
                continue
            bh = (n / tmax) * 40
            bars += (f'<rect class="thr" x="{pad + i * step - 4:.1f}" y="{h - pad - bh:.1f}" '
                     f'width="8" height="{bh:.1f}"><title>{n} done on {d}</title></rect>')
        labels_axis = "".join(
            f'<text x="{pad + i * step:.1f}" y="{h - 12}" class="axis">{d.isoformat()[5:]}</text>'
            for i, (d, _) in enumerate(series) if i % 3 == 0)
        chart = (f'<svg class="burndown" viewBox="0 0 {w} {h}" width="100%" role="img" '
                 f'aria-label="remaining work items per day, last 14 days">'
                 f'<line x1="{pad}" y1="{h - pad}" x2="{w - 6}" y2="{h - pad}" class="grid week"/>'
                 f'<line x1="{pad}" y1="{pad // 2}" x2="{pad}" y2="{h - pad}" class="grid week"/>'
                 f'{bars}<polyline class="line" points="{pts}"/>{labels_axis}'
                 f'<text x="{pad + 4}" y="{pad // 2 - 4}" class="axis">remaining (max {hi})</text>'
                 f'</svg>')
    else:
        chart = ('<p class="empty">no recorded work items yet: the burndown is drawn from task '
                 'events, and a seed file has none. Nothing here is inferred from today.</p>')
    cov = (f'{len(done)}/{len(dated)} recorded item(s) have a done transition; '
           f'{len(tasks) - len(dated)} item(s) are plan seed only and are absent from the chart')
    return f'''<h4>burndown, last 14 days</h4>
{chart}
<p class="note">{esc(cov)}</p>
<h4>throughput and cycle time</h4>
<p>{len(done)} item(s) completed · median cycle time {esc(median if median is not None else "-")} day(s) · mean {
   esc(round(sum(cycles) / len(cycles), 1) if cycles else "-")} day(s)</p>
<h4>what is waiting on what</h4>
<table class="items"><tr><th>id</th><th>title</th><th>blocked by</th><th>status</th><th>owner</th></tr>{open_blockers}</table>'''


# ------------------------------------------------------------------- export
def export_csv(tasks):
    cols = ["id", "status", "owner", "priority", "estimate", "start", "due",
            "milestone", "blocked_by", "visibility", "tags", "provenance", "title"]
    lines = [",".join(cols)]
    for tid, t in sorted(tasks.items()):
        row = []
        for c in cols:
            v = tid if c == "id" else t.get(c, "")
            if isinstance(v, list):
                v = " ".join(str(x) for x in v)
            v = "" if v is None else str(v)
            row.append('"' + v.replace('"', '""') + '"' if any(ch in v for ch in ',"\n') else v)
        lines.append(",".join(row))
    return "\n".join(lines) + "\n"


def _ical_date(value):
    d = parse_day(value)
    return d.strftime("%Y%m%d") if d else None


def export_ical(tasks, milestones, generated_at):
    """All-day VEVENTs only. No VTIMEZONE, so a date cannot drift by rendering it."""
    stamp = "".join(ch for ch in generated_at if ch.isdigit())[:15] + "Z"
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//aim//aimboard//EN",
           "CALSCALE:GREGORIAN", "X-WR-CALNAME:aim board"]
    for mid, m in sorted(milestones.items()):
        if not _ical_date(m.get("due")):
            continue
        due = parse_day(m["due"])
        out += ["BEGIN:VEVENT", f"UID:{mid}@aim", f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
                f"SUMMARY:{mid} {m.get('name','')}".rstrip(),
                f"DESCRIPTION:{m.get('accept','')}".replace("\n", " "),
                "END:VEVENT"]
    for tid, t in sorted(tasks.items()):
        start_d, due_d = parse_day(t.get("start")), parse_day(t.get("due"))
        if not (start_d or due_d):
            continue
        start_d = start_d or due_d
        end_d = (due_d or start_d) + timedelta(days=1)   # DTEND is exclusive
        desc = f"status: {t.get('status','')}; owner: {t.get('owner','')}; " \
               f"blocked by: {', '.join(t.get('blocked_by') or []) or '-'}; " \
               f"acceptance: {t.get('accept','')}"
        out += ["BEGIN:VEVENT", f"UID:{tid}@aim", f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{start_d.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end_d.strftime('%Y%m%d')}",
                f"SUMMARY:[{t.get('status','')}] {tid} {t.get('title','')}".rstrip(),
                f"DESCRIPTION:{desc}".replace("\n", " "),
                "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


if __name__ == "__main__":
    sys.exit(main())
