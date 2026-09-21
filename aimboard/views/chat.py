"""A view. Registering one is the whole extension point."""
from ..components import message_html
from ..const import DIVERGENCE
from ..gate import visible_rooms
from ..primitives import esc


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
    return f'''<p class="note">Counts and states only. The messages themselves are in the conversation
above, for the people in them; this panel answers the other question, which is whether
anything is stuck.</p>
<table class="items"><tr><th>from to</th><th>sent</th><th>claimed</th><th>acked</th><th></th></tr>{rows}</table>
{unacked}'''


def build(page):
    """Page(state, channels, viewer)"""
    rooms = (render_chat(page.channels, page.viewer) if any(ch.get("rooms") for ch in page.channels)
             else '<p class="note">No rooms yet, so group chat is not running: everything here is '
                  'one-to-one mail and the channel record. Rooms and read cursors are design/06, M2.</p>')
    return (render_conversation(page.state, page.viewer) + rooms
            + '<h3>transport</h3>' + render_transport(page.state))


def plugin(ctx):
    ctx.register_view("chat", "Chat", "群聊", build, order=50)
