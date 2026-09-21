"""Hashing, escaping, JSON and JSONL IO, chain verification, dates."""
import hashlib
import json
from datetime import date, datetime, timezone


def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    # must match bin/aim or every chain head this file verifies will disagree
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def esc(value):
    """Escape for both text and quoted-attribute contexts.

    Every string here can be peer-authored: a task title, a comment, a refusal
    reason. They live in an append-only chained log, so a payload in one is
    replayed on every render, which makes this the renderer's only real attack
    surface.
    """
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&#39;")
    )


def as_list(value):
    """A dependency is a list in the seed and a string in the store's `linked`
    event. `set("T-0001")` is a set of characters, which is how a renderer turns
    one dependency into six and never notices."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def read_jsonl(path):
    if not path.exists():
        return []
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    return out
    except OSError:
        return []
    return out


def verify_chain(path):
    """Re-walk a chained JSONL file: every record hashes its predecessor.

    Deliberately reimplemented rather than imported from bin/aim. An
    independent checker that shares code with the writer is not independent,
    and this is cheap: ten lines, and a disagreement between the two is itself
    a finding worth having.
    """
    prev, count = "genesis", 0
    for rec in read_jsonl(path):
        body = {k: v for k, v in rec.items() if k != "hash"}
        if rec.get("prev") != prev:
            return {"state": "BROKEN", "records": count, "why": "prev does not match the previous hash"}
        if sha256_hex(canonical(body)) != rec.get("hash"):
            return {"state": "BROKEN", "records": count, "why": "record hash does not match its contents"}
        prev, count = rec.get("hash"), count + 1
    return {"state": "OK" if count else "EMPTY", "records": count, "why": ""}


def parse_day(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def day_of(ts):
    if not ts:
        return None
    try:
        return date.fromisoformat(str(ts)[:10])
    except ValueError:
        return None
