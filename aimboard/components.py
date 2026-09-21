"""The two things a card is made of, escaped on the way in."""
from .const import TERMINAL
from .primitives import esc, parse_day


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


def message_html(head, body, meta="", state_chip=""):
    return f'''<article class="msg">
  <header><b>{esc(head)}</b> <span class="dim">{esc(meta)}</span>{state_chip}</header>
  <pre>{esc(body)}</pre>
</article>'''
