"""The wire shape the front-end reads.

One payload, assembled once, with every access rule applied before anything is
serialised. The browser is not trusted to hide what it was sent - a client-side
filter is a suggestion, and this project has a word for suggestions that are
enforced somewhere else.
"""
from datetime import datetime, timezone

from .const import STATUSES, TERMINAL
from .fold import drift, report_data, task_history, fold_tasks, merge_plan
from .gate import (conversation_view, gate_channel, may_see_peer_secrets,
                   visible_tasks)


def channel_payload(state, ch, viewer):
    secrets = may_see_peer_secrets(state, ch, viewer)
    sealed = []
    for who in ch.get("participants", []):
        seal = ch["seals"].get(who)
        if not seal:
            sealed.append({"agent": who, "sealed": False})
            continue
        entry = {"agent": who, "sealed": True,
                 "digest": (seal.get("digest") or seal.get("private_log_sha256") or ""),
                 "claims_count": len(seal.get("claims") or []),
                 "ts": seal.get("ts", "")}
        # your own seal is yours; a peer's is withheld while the channel is sealed
        if secrets or who == viewer:
            entry["claims"] = [{"id": c.get("id", ""), "claim": c.get("claim", ""),
                                "confidence": c.get("confidence", ""),
                                "kill_if": c.get("kill_if", "")}
                               for c in (seal.get("claims") or [])]
        else:
            entry["withheld"] = True
        sealed.append(entry)
    return {
        "id": ch["id"], "topic": ch["manifest"].get("topic", ""), "phase": ch["phase"],
        "round": ch["round"], "leader": ch["leader"], "synthesizer": ch["manifest"].get("synthesizer", ""),
        "participants": ch["participants"], "history": ch["history"],
        "sealed": sealed, "chain": ch["chain"], "tasks_recorded": len(ch["tasks_recorded"]),
        "tasks_store_exists": ch["tasks_exists"],
        "refusals": [{"ts": r.get("ts", ""), "agent": r.get("agent", ""),
                      "action": r.get("action", ""), "class": r.get("class", ""),
                      "phase": r.get("phase", ""), "reason": r.get("reason", "")}
                     for r in ch["refusals"]],
        "concessions": len(ch["concessions"]),
        "friction": ch.get("friction", []),
    }


def payload(state, viewer, register, generated_at=None, as_of=None, digest=None):
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    channel = gate_channel(state, viewer, {})
    tasks, hidden = visible_tasks(state, viewer, channel)
    as_of_date = as_of or state["as_of"]
    return {
        "generated_at": generated_at,
        # the fingerprint the front-end polls, so the page can say "the record
        # moved" without reloading itself under the reader's hands
        "digest": digest or "",
        "as_of": as_of_date,
        # the state machine is the server's, not the browser's: a front-end that
        # hard-codes the status list is a second copy of the contract, and this
        # project has measured what a second copy costs (design/05, T-0086)
        "statuses": STATUSES,
        "terminal": sorted(TERMINAL),
        "root": state["root"],
        "viewer": viewer,
        "viewer_kind": (state["registry"].get(viewer) or {}).get("kind", ""),
        "phase": channel.get("phase", "-"),
        "withheld_tasks": hidden,
        "channels": [channel_payload(state, ch, viewer) for ch in state["channels"]],
        "tasks": tasks,
        "milestones": state["milestones"],
        "reports": report_data(tasks, state["milestones"],
                               datetime.fromisoformat(as_of_date).date()),
        "conversation": conversation_view(state, viewer),
        "mail": state["mail"],
        "unacked": state["unacked"],
        "drift": drift(state["seed_tasks"], (state["channels"][0]["tasks_recorded"]
                                             if state["channels"] else {})),
        "register": register or {},
        "agents": {k: {"kind": v.get("kind", ""), "model": v.get("model", "")}
                   for k, v in state["registry"].items()},
    }
