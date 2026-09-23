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


def read_seal_claims(seal):
    """The claims a seal file can actually be read as: a list of objects, or [].

    T-0247, the surviving-record half. `aim seal` used to store whatever the
    `--claims` file parsed to, so a tree can hold a seal whose `claims` is a
    string, a number or a list of strings, and every reader that treats claims
    as a list of objects died on it -- `/api/state` answered 500 with `'str'
    object has no attribute 'get'` for the leader and for any viewer who may see
    the seal, and the same iteration in the HTML audit pane and in
    `aimboard.views.audit` raised the same way. `bin/aim` refuses that payload
    now, which stops new ones; a seal already on disk is a record, and the
    reader has to survive records it did not write.

    Two rules make that survival honest rather than a guess, and both are why
    this is one function rather than an `isinstance` at each reader:

      * **Nothing here invents a shape.** An element that is not an object is
        dropped, not coerced. `str(c)` would render a string as a claim body
        nobody wrote, and a `{"claim": str(c)}` cast would publish it as one --
        that is the hidden-bad-record failure this project keeps paying for, so
        the unreadable element is *absent* rather than plausible. The reader
        that must not 500 is served a shorter list, and `aim verify` is where
        the seal's damage is reported (`check_sealed_prefix` and the digest
        check both already report a malformed seal rather than dying on it).
        Keeping the two jobs apart is the point: the board serves what it can
        read, the verifier judges what it was given.
      * **`[]` is the answer for a seal that holds nothing readable**, which is
        the same answer a seal with `"claims": []` gives. That keeps the two
        page readers agreeing by construction: `/api/state`'s `claims_count` and
        the HTML audit pane's `len(claims)` both count *this* function's return
        value, so a pane cannot print "(3 claims)" beside two rendered rows --
        the composed-number failure this project's own memory has a row for.

    Deliberately not a cast to the four keys `/api/state` publishes, and
    deliberately not a filter on them either: a claim's extra fields are the
    writer's, and a reader that keeps the object whole leaves the next field
    (a `method`, say) available to whoever renders it.

    Measured after the reader was written (T-0247; hand-built seals under a
    throwaway root, `alpha`'s payload the bare string and `beta`'s a mixed list
    of one object, `"junk"`, `5`, and one more object):

        /api/state      viewer=leader, alpha, beta  ->  claims_count [0, 2]
        render_barrier  viewer=alpha                ->  "0 claim(s)", "2 claim(s)"
        aim tension     ->  rc=0, two rows printed, no TypeError

    The count of 2 is the count of *readable* claims, which is the claim this
    function makes and the reason it drops rather than coerces.
    """
    claims = seal.get("claims") if isinstance(seal, dict) else None
    if not isinstance(claims, list):
        return []
    return [c for c in claims if isinstance(c, dict)]


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
