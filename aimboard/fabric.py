"""Reading the fabric. Every loader here is read-only."""
import hashlib
from .fold import fold_tasks, merge_plan
from .primitives import read_json, read_jsonl, verify_chain


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
