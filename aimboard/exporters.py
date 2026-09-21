"""For a foreign tool: CSV, iCal, JSON."""
from datetime import timedelta
from .gate import gate_channel, visible_tasks
from .primitives import parse_day


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


def json_payload(state, viewer, risks, generated_at):
    ctx = gate_channel(state, viewer, {})
    tasks, hidden = visible_tasks(state, viewer, ctx)
    return {
        "generated_at": generated_at,
        "as_of": state["as_of"],
        "root": state["root"],
        "viewer": viewer,
        "withheld_tasks": hidden,
        # an event the fold could not place: dropped from the board, so it has to
        # be visible somewhere or the board is quietly wrong
        "unplaced_events": state.get("unplaced_events", 0),
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
