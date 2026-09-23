"""Reading the fabric. Every loader here is read-only."""
import hashlib
from datetime import date

from .fold import fold_tasks, merge_plan
from .primitives import read_json, read_jsonl, verify_chain


# A channel's manifest records what it was *declared* to be: a topic, a leader,
# participants, the phase its barrier opened in. The store records what actually
# happened after that. Until now the board only ever showed the declaration, so
# `dev` (a real topic, two participants, and then nothing for two days) and
# `hello` (named after a transport test, and holding every live task) rendered as
# the same kind of object. That is T-0216: the channel named for the development
# work is empty and the work is in the channel named after a test.
#
# `kind` separates a real project from a throwaway probe (T-0232 measured two
# abandoned `s2-scratch*` channels in one flat namespace). It is read from the
# manifest when a writer records one -- the field T-0232 asks for -- and
# otherwise derived from the only signal the store carries today, the topic the
# channel was opened with. That fallback is a heuristic, and the test says so.
#
# The liveness rule is derived, not maintained: `empty` if nothing was ever
# recorded, `dormant` if the last thing recorded is at least
# `DORMANT_AFTER_DAYS` behind the date the board is drawn for, `active`
# otherwise. `idle_days` is exposed so a caller with a real milestone calendar
# can apply its own threshold instead of this default. Nothing here is a second
# list a human has to keep true.
DORMANT_AFTER_DAYS = 2


def _day(ts):
    """The date part of an ISO timestamp, or None if it is not one."""
    if not isinstance(ts, str) or len(ts) < 10:
        return None
    try:
        return date.fromisoformat(ts[:10])
    except ValueError:
        return None


def _latest(*groups):
    """The newest `ts` across records pulled from the store, or ""."""
    stamps = [r["ts"] for group in groups for r in group
              if isinstance(r, dict) and isinstance(r.get("ts"), str)]
    return max(stamps) if stamps else ""


def channel_kind(manifest):
    """project | scratch -- declared if the manifest says so, derived otherwise."""
    declared = manifest.get("kind")
    if declared:
        return declared
    topic = (manifest.get("topic") or "").strip().lower()
    return "scratch" if topic.startswith("scratch") else "project"


def channel_lifecycle(manifest, traffic, last_activity, as_of,
                      dormant_after_days=DORMANT_AFTER_DAYS):
    """Classify one channel from its declaration plus what the store recorded.

    `traffic` counts the records that mean *an actor did something here*, broken
    out by source so the classification can be audited rather than trusted. A
    channel with zero traffic is `empty` however healthy its manifest looks; that
    is the fact `aim status --channel dev` could not previously state.
    """
    total = sum(traffic.values())
    last = last_activity or manifest.get("created_at") or ""
    idle = None
    if as_of is not None:
        day = _day(last)
        if day is not None:
            idle = (as_of - day).days
    if total == 0:
        state = "empty"
    elif idle is not None and idle >= dormant_after_days:
        state = "dormant"
    else:
        state = "active"
    return {
        "state": state,
        "created_at": manifest.get("created_at", ""),
        "kind": channel_kind(manifest),
        "traffic": dict(traffic),
        "last_activity": last,
        "idle_days": idle,
    }


def fabric_digest(root):
    """A cheap fingerprint of everything the renderer reads.

    The dashboard should tell you that the record changed, not reload itself:
    a page that refreshes under your hands loses your scroll position, your open
    tab and your place in a long message. This digest is collected from file
    metadata, so checking it is far cheaper than rendering the board.
    """
    h = hashlib.sha256()
    for part in ("registry.json", "channels", "outbox", "plan"):
        base = root / part
        paths = [base] if base.is_file() else sorted(base.rglob("*")) if base.exists() else []
        for path in paths:
            if not path.is_file():
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            h.update(f"{path.relative_to(root)}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


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
            # T-0249: the metadata half of the room gate. `gate.room_authors`
            # decides a room is readable by the agent who *opened* it, and the
            # opener is recorded on `rooms/<room>.json` (`author`/`created_by`,
            # `bin/aim:3022`) -- so a loader that forwards only the log hands the
            # gate half the evidence and the author of an empty room, or of a room
            # whose opener did not write the first message, is locked out of their
            # own draft. Forwarded, and the gate still fail-closes on a room whose
            # log names an opener its metadata does not.
            "author": meta.get("author") or meta.get("created_by", ""),
            "created_by": meta.get("created_by", ""),
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


def load_fabric(root, plans, as_of, dormant_after_days=DORMANT_AFTER_DAYS):
    registry = (read_json(root / "registry.json", {"agents": {}}) or {}).get("agents", {})
    channels = []
    for name in list_channels(root):
        cdir = root / "channels" / name
        manifest = read_json(cdir / "manifest.json", {}) or {}
        ledger = read_jsonl(cdir / "ledger.jsonl")
        task_events = read_jsonl(cdir / "tasks.jsonl")
        log = read_jsonl(cdir / "log.jsonl")
        friction = read_jsonl(cdir / "friction.jsonl")
        rooms = load_rooms(cdir)
        phase = (manifest.get("barrier") or {}).get("phase", "UNKNOWN")
        seals = {}
        for path in sorted((cdir / "seals").glob("*.json")) if (cdir / "seals").exists() else []:
            seal = read_json(path, {}) or {}
            seals[path.stem] = seal
        recorded, unknown = fold_tasks(task_events)
        for item in recorded.values():
            item["channel"] = name
        room_messages = [m for room in rooms for m in room["messages"]]
        # One fact, computed here where the fold already has every source open:
        # whether this channel is alive, and whether it is a real project. The
        # serialisers must not each re-derive it, or they become two answers to
        # one question (the mistake `unplaced_events` below records having made).
        lifecycle = channel_lifecycle(
            manifest,
            {
                "messages": len(log),
                "ledger": len(ledger),
                "tasks": len(task_events),
                "rooms": len(room_messages),
                "friction": len(friction),
                "seals": len(seals),
            },
            _latest(log, ledger, task_events, friction, room_messages, seals.values()),
            as_of,
            dormant_after_days,
        )
        channels.append({
            "id": name,
            "manifest": manifest,
            **lifecycle,
            "phase": phase,
            "round": (manifest.get("barrier") or {}).get("round", 0),
            "history": (manifest.get("barrier") or {}).get("history", []),
            "participants": manifest.get("participants", []),
            "leader": manifest.get("leader", ""),
            "seals": seals,
            "ledger": ledger,
            "refusals": [r for r in ledger if r.get("event") == "refusal"],
            "concessions": [r for r in ledger if r.get("event") == "concession"],
            "log": log,
            "tasks_recorded": recorded,
            "tasks_unknown_events": unknown,
            "rooms": rooms,
            "friction": friction,
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
        # One fact, computed where the fold happens, read by every serialiser:
        # the two payload builders below (api.payload for the dashboard,
        # exporters.json_payload for foreign tools) must not each derive it, or
        # they become two answers to one question.
        "unplaced_events": sum(c.get("tasks_unknown_events", 0) for c in channels),
        "channels": channels,
        "milestones": milestones,
        "seed_tasks": seed_tasks,
        "tasks": tasks,
        "mail": {f"{a} -> {b}": v for (a, b), v in sorted(mail.items())},
        "conversation": load_conversation(root),
        "unacked": unacked,
        "plan_glob": plans,
    }
