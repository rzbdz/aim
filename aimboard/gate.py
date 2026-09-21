"""Who may see what, and the channel whose phase decides it."""
from .const import DIVERGENCE


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


def conversation_view(state, viewer):
    """Who may read which conversation, in one place.

    The policy lived in the HTML view first, which meant a second consumer (the
    JSON API the new front-end reads) would have re-implemented it. Two
    implementations of an access rule is exactly the class of bug this project
    keeps finding, so the rule lives here and both consumers format its output.

    leader        every message between agents
    participant   mail they sent or received, and the messages the phase permits
    bystander     counts, not contents
    nobody        a peer's private reasoning, ever
    """
    kind = (state["registry"].get(viewer) or {}).get("kind", "")
    is_leader = kind == "human"
    withheld = 0
    channels, rooms_out, mail_out = [], [], []

    for ch in state["channels"]:
        gated = viewer in ch.get("participants", []) and ch.get("phase") in DIVERGENCE
        messages = []
        for m in ch["log"]:
            if gated and m.get("from") != viewer:
                withheld += 1
                continue
            messages.append({"from": m.get("from", ""), "ts": m.get("ts", ""),
                             "kind": m.get("kind", ""), "responds_to": m.get("responds_to", ""),
                             "body": m.get("body", ""), "hash": m.get("hash", "")})
        channels.append({"id": ch["id"], "phase": ch["phase"], "gated": gated,
                         "messages": messages,
                         "rule": ("you are a participant and the channel is sealed, so peer "
                                  "messages are absent" if gated else "everything in this phase")})
        visible, hidden = visible_rooms(ch, viewer)
        withheld += hidden
        for room in visible:
            rooms_out.append({
                "channel": ch["id"], "id": room["id"], "visibility": room["visibility"],
                "topic": room.get("topic", ""), "unread": room["unread"],
                "mentions": room["mentions"],
                "messages": [{"from": m.get("agent", ""), "ts": m.get("ts", ""),
                              "body": m.get("body", ""),
                              "mentions": m.get("mentions") or []} for m in room["messages"]]})

    for rec in state.get("conversation", []):
        sender, to = rec.get("from", ""), rec.get("to", "")
        if not is_leader and viewer not in (sender, to):
            withheld += 1
            continue
        mail_out.append({
            "from": sender, "to": to, "ts": rec.get("ts", ""),
            "subject": rec.get("subject", ""), "body": rec.get("body", ""),
            "msg_id": rec.get("_id", ""), "ack_required": bool(rec.get("ack_required")),
            "acked_at": rec.get("acked_at", ""), "claimed_at": rec.get("claimed_at", ""),
            "bytes": rec.get("bytes", 0),
            "state": ("acked" if rec.get("acked_at") else
                      "claimed" if rec.get("claimed_at") else "unread")})

    return {"viewer": viewer, "is_leader": is_leader, "channels": channels,
            "rooms": rooms_out, "mail": mail_out, "withheld": withheld}
