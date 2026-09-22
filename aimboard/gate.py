"""Who may see what, and the channel whose phase decides it."""
from .const import DIVERGENCE, TERMINAL


def walled_off(state, channel, viewer):
    """Is this viewer shut out of the channel's un-published material?

    There are two ways to be shut out, and for a long time this file implemented
    one of them:

      * the **barrier**: you are a participant and the channel is in a divergence
        phase, so you may not read a peer's drafts or claims yet;
      * being a **stranger**: you are a registered agent and not a participant of
        the channel that governs the record. `aim` refuses that caller outright -
        `aim task list` returns rc=2 and records the refusal, `aim seal` says "not
        a participant" - so a renderer that serves them the bytes is the route
        around a refusal, which is the failure this project exists to catch.

    T-0041 measured the second case: every gate branch tested membership of
    `participants`, so for a registered non-participant all three of them took the
    else. The leader is exempt from both, because the leader is the audience and
    not a participant.
    """
    if (state.get("registry", {}).get(viewer) or {}).get("kind") == "human":
        return False
    if viewer not in channel.get("participants", []):
        return True
    return channel.get("phase") in DIVERGENCE


def may_see_peer_secrets(state, channel, viewer):
    """A sealed channel's claims, and a stranger's, are both out of reach."""
    return not walled_off(state, channel, viewer)


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
        draft = (task.get("visibility") or "draft") == "draft"
        if (draft and walled_off(state, channel, viewer)
                and viewer not in (task.get("owner"), task.get("created_by"))):
            hidden += 1
            continue
        out[tid] = task
    return out, hidden


def stuck_tasks(state, tasks):
    """The cards a human said are stuck, which is not the same fact as `blocked`.

    `reports.blocked` is an *edge* statement: a card is in it because a
    dependency is unmet, so a card whose only `blocked_by` is done leaves the
    list the moment the edge closes -- and T-0041 is exactly that card (status
    blocked, its only blocked_by T-0040 done). It is not waiting on a peer; it is
    waiting on a person, and before this function it appeared in no list at all.
    Both facts are published, in two fields, because one field carrying both is
    how a reader stops being able to tell which one they are looking at.

    Rows are the dependency half of a `blocked` row and nothing else: the
    estimate and claim columns `fold.report_data` fills in need `declared_hours`
    and `claim_offer`, which live in that module.

    The rule is one sentence -- status is blocked and no edge is unmet -- and
    this is the second place it is spelled, which is one too many. The first is
    the nested `unmet_dependency` inside `fold.report_data` (fold.py:294); the
    change that retires this copy is named in the round's report.
    """
    out = []
    for tid, task in tasks.items():
        if task.get("status") != "blocked":
            continue
        if any((tasks.get(dep) or {}).get("status") not in TERMINAL
               for dep in (task.get("blocked_by") or [])):
            continue
        out.append({"id": tid, "title": task.get("title", ""),
                    "status": task.get("status", ""), "owner": task.get("owner", ""),
                    "blocked_by": task.get("blocked_by") or []})
    return out


def room_authors(room):
    """Who wrote a room, out of the evidence the room actually carries.

    `design/06` §2 says a draft room's messages are readable "by their author",
    so the gate needs an author, and a room reaches it in one shape:
    `fabric.load_rooms` reads `rooms/<room>.json` but forwards only
    id/topic/visibility/messages/unread/mentions, so an `author` key in that
    metadata is dropped before this file sees it. What does arrive is `agent` on
    each message, the same field `conversation_view` prints from.

    The gate is room-level while authorship is per message, so the fail-closed
    choice is made here: a viewer is the author only if they wrote *every*
    attributed message. A hand-written room with two authors therefore exempts
    neither, rather than opening one author's text to the other. A room with no
    attributed messages falls back to declared metadata, for a loader that
    forwards it.
    """
    attributed = {m.get("agent") for m in room.get("messages") or [] if m.get("agent")}
    if attributed:
        return attributed if len(attributed) == 1 else set()
    return {room.get(k) for k in ("author", "created_by", "owner")} - {None}


def visible_rooms(state, channel, viewer):
    out, hidden = [], 0
    for room in channel.get("rooms", []):
        draft = room["visibility"] != "published"
        if (draft and walled_off(state, channel, viewer)
                and viewer not in room_authors(room)):
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
        gated = walled_off(state, ch, viewer)
        messages = []
        for m in ch["log"]:
            if gated and m.get("from") != viewer:
                withheld += 1
                continue
            messages.append({"from": m.get("from", ""), "ts": m.get("ts", ""),
                             "kind": m.get("kind", ""), "responds_to": m.get("responds_to", ""),
                             "subject": m.get("subject", ""), "phase": m.get("phase", ""),
                             "body": m.get("body", ""), "hash": m.get("hash", "")})
        channels.append({"id": ch["id"], "phase": ch["phase"], "gated": gated,
                         "messages": messages,
                         "rule": ("the channel is sealed to you, so peer messages are absent"
                                  if gated else "everything in this phase")})
        visible, hidden = visible_rooms(state, ch, viewer)
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
    mail_out.sort(key=lambda rec: rec.get("ts", ""))

    return {"viewer": viewer, "is_leader": is_leader, "channels": channels,
            "rooms": rooms_out, "mail": mail_out, "withheld": withheld}
