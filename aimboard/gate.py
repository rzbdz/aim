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


def room_author_from_metadata(meta, op_agent=""):
    """Who opened a room. The one place this is decided, for the CLI and the board.

    A room is an *object* opened by one agent, not a transcript that belongs to
    everyone who ever spoke in it, and the record says so: `aim room new` writes
    `author` and `created_by` into `rooms/<room>.json`, and a room's log begins
    with the message its opener wrote. Two facts decide, and one shape refuses:

      * `op_agent` -- the first attributed voice in the room's log, and
      * the creator recorded in the room's metadata (`author`, else `created_by`),

    agree -> that agent opened the room. A room whose log names an opener its
    metadata does not is a hand-merged contradiction, and that case returns `""`:
    nobody may read the room rather than one of the two being picked. That arm is
    about *provenance*, not about a second voice -- a room with two voices has one
    opener and is the room the design describes.

    T-0249 is why this function exists. The rule used to be "a viewer is the
    author only if they wrote *every* attributed message", so a second voice --
    the act `design/06` §2 says a room is *for* -- made the room unreadable by
    the author who opened it, permanently: `_room_author` returned `""`, the CLI's
    read and publish gates were both `who != author`, and no caller could satisfy
    them again. The room's own creation message promised "a draft room: readable
    by you and the leader", and after the second voice neither the author nor the
    leader could read it. `bin/aim`'s `_room_author` imports *this* function now
    rather than keeping a second copy, so one question has one rule.
    """
    creator = meta.get("author") or meta.get("created_by") or meta.get("owner") or ""
    op = op_agent or meta.get("opened_by") or ""
    if op and creator and op != creator:
        return ""
    return op or creator


def room_authors(room):
    """The room's author set, as the renderer's gate spells it.

    A single-valued rule wearing a set's name, kept a set because the call site
    reads as membership. `room_author_from_metadata` decides; this function's
    only job is to hand it the opener evidence the *loader* forwards:
    `fabric.load_rooms` copies `author` off `rooms/<room>.json` (T-0249 -- it used
    to forward only id/topic/visibility/messages/unread/mentions, so the metadata
    half of the rule could never fire on the board) and every message carries
    `agent`, the same field `conversation_view` prints from.

    An earlier version of this docstring called the old union fail-closed and the
    two-author case deliberate. It was neither: it was the gate reading
    `design/06` §2's "readable by their author" as an *exclusive* claim about a
    room's whole transcript, which makes the one room the design describes -- two
    voices, one of them the opener -- unreadable to both.
    """
    op = next((m.get("agent") for m in room.get("messages") or [] if m.get("agent")), "")
    author = room_author_from_metadata(room, op)
    return {author} if author else set()


def visible_rooms(state, channel, viewer):
    """A draft room is withheld from a walled-off viewer who is not its author.

    The author is `room_author_from_metadata`'s verdict -- the agent who opened
    the room -- and never the set of everyone who spoke in it (T-0249). A room
    with two voices is the case `design/06` §2 describes, so it must not be the
    case that closes the room.
    """
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
