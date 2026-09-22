"""For a foreign tool: CSV, iCal, JSON.

Who may see what is decided in `aimboard/gate.py` and nowhere else. Two of the
three writers below format a `tasks` mapping they are *given*, and the caller is
the one that gated it -- `aimboard/cli.py:92` runs `gate.visible_tasks` and passes
the result to `export_csv`/`export_ical`, so a task the viewer may not open never
reaches them. The third, `json_payload`, needs more than the viewer's task set, so
it calls the same two functions itself: `aimboard/api.py:375` is that same payload
for the dashboard, and its two gate calls are `api.py:377-378`. A rule derived a
third time here would be the bug class `gate.conversation_view` was written to end
(gate.py:145).
"""
import re
from datetime import datetime, timedelta, timezone
from .gate import gate_channel, visible_tasks
from .primitives import parse_day


def export_csv(tasks):
    # `estimate_hours` and not `estimate`: the column is called an estimate
    # without saying what it is one *of*, and until T-0212 there were three
    # spellings of the field and therefore three possible numbers in this cell
    # (`fold.ESTIMATE_MIGRATION`, fold.py:48). `estimate_hours` is the one the
    # fold publishes on every row (fold.py:255); it is `None` where the record
    # carries no estimate, which is a different fact from 0 and is left empty
    # here rather than written as a number nobody recorded.
    #
    # On the tree this was written on that is every row: the 87 seeds still carry
    # points and the fold does not convert them, so the column is empty until the
    # T-0212 migration runs. It is left empty on purpose. Renaming the column back
    # would publish a unitless number under a name a reader has no way to resolve,
    # and summing points into `estimate_hours` here would make `1 pt = 1 h` true
    # with no recorded decision behind it -- which is the one thing the migration
    # note forbids (fold.py:56, `not_a_conversion`).
    cols = ["id", "status", "owner", "priority", "estimate_hours", "start", "due",
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


def _fold_content_line(line, limit=75):
    """RFC 5545 section 3.1: a content line is at most `limit` octets, and a
    continuation begins with a single space that counts toward its own limit.

    The fold points are chosen between characters, never inside one: a
    3-byte character that does not fit on the current line starts the next one,
    so unfolding cannot produce a different string than the one folded. The
    octet count is what the spec limits, which is why this measures bytes and
    not `len()`.
    """
    out, cur = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        if cur and len(cur) + len(enc) > limit:
            out.append(cur.decode("utf-8"))
            cur = b" "          # the continuation marker, and part of the budget
        cur += enc
    out.append(cur.decode("utf-8"))
    return out


def _ical_date(value):
    d = parse_day(value)
    return d.strftime("%Y%m%d") if d else None


def _ical_text(value):
    """RFC 5545 section 3.3.11: TEXT escapes `\\`, `;` and `,`, and newlines are
    escaped as `\\n` rather than dropped.

    Measured with a parser that is not ours (icalendar 7.3.0, which `tests/
    test_export_extra.py` uses when it is installed): 108 SUMMARY and DESCRIPTION
    values on the live root carried a comma or a semicolon -- `M2 Group chat:
    rooms, cursors, mentions`, `design/05, design/06 ... committed` -- and an
    unescaped `,` separates values in a TEXT property, so the property reads back
    as a *list* rather than the string the writer wrote. The bare LF this also
    fixes was the same defect from the other side: a value's line break is
    content, and the space this file used to substitute was silently editing the
    record.
    """
    value = str(value or "")
    value = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return re.sub(r"\r\n|\r|\n", "\\n", value)


def _ical_stamp(generated_at):
    """RFC 5545 section 3.3.5: a UTC DATE-TIME is `YYYYMMDDTHHMMSSZ`.

    The previous spelling glued the first 15 digits of the stamp together and
    appended `Z`, which is the shape `now_iso()` produces minus the separators --
    `202609220943415Z` -- and no parser accepts it: icalendar 7.3.0 read the
    property back as `vBroken`, and a `vBroken` in a required property is the
    "opens in one app, refuses in another" half of this card's acceptance
    sentence. Parsing the stamp instead of stripping it also means an offset
    (`+02:00`) is converted rather than transcribed as if it were UTC, which is
    the same class of mistake as a bare date in a calendar.

    A stamp this cannot read is dropped rather than written: an absent DTSTAMP is
    a fact a consumer can see the source of, and a malformed one is a lie about
    the same fact.
    """
    try:
        moment = datetime.fromisoformat(str(generated_at or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def export_ical(tasks, milestones, generated_at):
    """All-day VEVENTs only. No VTIMEZONE, so a date cannot drift by rendering it.

    A VEVENT needs a date, so an undated item cannot be one -- and on the tree
    this was written on 70 of 177 visible items have no `start` and no `due`.
    Dropping them without a word is the failure `tests/test_export.py:21` names:
    "a file that is valid and silently missing 40% of the board is worse than a
    broken one, because nothing complains". So the count is published on the
    VCALENDAR, where RFC 5545 section 3.8.8.2 allows a DESCRIPTION and every
    parser that reads the events also reads the calendar around them. Checked
    with icalendar 7.3.0: a VCALENDAR DESCRIPTION parses and reads back intact.
    """
    stamp_line = [f"DTSTAMP:{stamp}"] if (stamp := _ical_stamp(generated_at)) else []
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//aim//aimboard//EN",
           "CALSCALE:GREGORIAN", "X-WR-CALNAME:aim board"]
    undated = 0
    for mid, m in sorted(milestones.items()):
        if not _ical_date(m.get("due")):
            undated += 1
            continue
        due, name = parse_day(m["due"]), m.get("name", "")
        out += ["BEGIN:VEVENT", f"UID:{_ical_text(mid)}@aim", *stamp_line,
                f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
                f"SUMMARY:{_ical_text(f'{mid} {name}'.rstrip())}",
                f"DESCRIPTION:{_ical_text(m.get('accept', ''))}",
                "END:VEVENT"]
    for tid, t in sorted(tasks.items()):
        start_d, due_d = parse_day(t.get("start")), parse_day(t.get("due"))
        if not (start_d or due_d):
            undated += 1
            continue
        start_d = start_d or due_d
        end_d = (due_d or start_d) + timedelta(days=1)   # DTEND is exclusive
        status, title = t.get("status", ""), t.get("title", "")
        blockers = ", ".join(t.get("blocked_by") or []) or "-"
        parts = [f"status: {status}", f"owner: {t.get('owner', '')}",
                 f"blocked by: {blockers}"]
        # The unit travels with the number or the number is not written: `4` in a
        # calendar app is four *what*? This is the one export surface with no
        # column header to carry the unit, and a bare number here is the defect
        # T-0212 filed against three panes (`fold.ESTIMATE_MIGRATION`, fold.py:48).
        if t.get("estimate_hours") is not None:
            parts.append(f"estimate: {t['estimate_hours']}h")
        parts.append(f"acceptance: {t.get('accept', '')}")
        out += ["BEGIN:VEVENT", f"UID:{_ical_text(tid)}@aim", *stamp_line,
                f"DTSTART;VALUE=DATE:{start_d.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end_d.strftime('%Y%m%d')}",
                f"SUMMARY:{_ical_text(f'[{status}] {tid} {title}'.rstrip())}",
                f"DESCRIPTION:{_ical_text('; '.join(parts))}",
                "END:VEVENT"]
    if undated:
        out.insert(5, "DESCRIPTION:" + _ical_text(
            f"{undated} item(s) on the board carry no date and are not events in "
            f"this file; read them from the CSV or the JSON export"))
    out.append("END:VCALENDAR")
    folded = [part for line in out for part in _fold_content_line(line)]
    return "\r\n".join(folded) + "\r\n"


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
