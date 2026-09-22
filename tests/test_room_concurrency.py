"""T-0026: 12 concurrent room writers, one order, no lost message.

The card is one sentence and every clause in it names a different failure, so the
file pins four things separately rather than one "it worked":

    concurrent     12 *OS processes*, not 12 threads calling one function. A
                   thread test measures the GIL, not `bin/aim`'s flock; the
                   failure the card names is a lost append, and an append is
                   only lost when two processes race the same file.
    one order      every record's `prev` equals the previous record's `hash`,
                   so the log is one chain and not two interleaved ones.
    no lost        exactly 12 records, and the 12 bodies are the 12 bodies that
    message        were written -- a count alone is passed by any log that lost
                   one and duplicated another, which is what a lock-free
                   `seq = len(...) + 1` race produces.
    recoverable    replaying the chain in file order recomputes every hash.
                   That is the difference between an order that is *present* in
                   the bytes and an order a reader can reconstruct from nothing
                   but the file -- the second is the claim `aim verify` makes.

What would make it red, said here so the negative control is a measurement and
not a hope. Read the writer first: `cmd_room_say` (bin/aim:2797-2804) takes
`seq = len(read_jsonl(...)) + 1` *inside* `with Lock(channel_dir(ch) / ".lock")`
and appends inside the same block, on the comment's own reasoning that two
writers both computing `len+1` would make the second one's message "the one that
never happened". Move either line out of the `with` and the id check goes red
(measured: 2 of 5 runs, two writers claim `r0004` and `r0005` is never
allocated). Replace the `append_chained` call (bin/aim:425) with a plain
`open(path, "a")` and the count stays 12 and every chain check goes red -- which
is exactly the "well-formed and one fact short" shape the count-only check would
have missed.

One thing the card does not say and the code does: the room must be *published*
before 12 peers may write to it. `_load_room_or_die` (bin/aim:2624) refuses a
draft room to a non-author whenever the channel is in a divergence phase, and a
fresh channel is born in SEALED_DIVERGENT (measured: all 12 `room say` calls
exit 2 with "REFUSED: room 'r' in ch is a draft" when the publish step is
skipped). So the fixture publishes the room first -- one recorded act, which is
the deliberate-open design/06 §2 specifies. The refusal is the barrier working,
not a bug, and it is a *setup* step here rather than a check: T-0198/T-0219's
files own the gate's behaviour.

Run: python3 tests/test_room_concurrency.py     (exit code 1 if any check failed)
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"

WRITERS = 12

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def norm(text):
    return re.sub(r"\s+", " ", text.replace("\\n", " ")).strip()


def canonical(obj):
    """bin/aim:166-168, copied rather than imported: the digest only means
    something if it is over the same bytes the writer hashed, and importing
    `bin/aim` to get two pure functions would drag an argparse tree and an
    `AIM_ROOT` read (bin/aim:35) into this process. `sort_keys` and the compact
    separators are the whole content of the rule -- change either in bin/aim and
    every hash below stops matching, which is the intended failure: this file
    would then be asserting a chain the tool no longer produces."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data):
    """bin/aim:170-172."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    env = dict(os.environ, AIM_ROOT=str(root))

    def run(*argv):
        return subprocess.run([sys.executable, str(AIM), *argv], capture_output=True,
                              text=True, env=env, timeout=120)

    run("init")
    writers = [f"w{i:02d}" for i in range(WRITERS)]
    for w in writers:
        run("register", "--as", w, "--kind", "codex")
    run("register", "--as", "leader", "--kind", "human")
    out = run("new-channel", "--id", "ch", "--topic", "room concurrency",
              "--participants", ",".join(writers), "--leader", "leader")
    check("the channel is in a divergence phase (or the draft gate is not what is in play)",
          "SEALED_DIVERGENT" in out.stdout, out.stdout + out.stderr)

    run("room", "new", "--as", writers[0], "--channel", "ch", "--id", "r",
        "--topic", "12 concurrent writers")
    pub = run("room", "publish", "--as", writers[0], "--channel", "ch", "--id", "r",
              "--reason", "T-0026: a room 12 processes may write to")
    # Whitespace-collapsed, the way test_room_gate reads tool output: the fact
    # asserted is that the *room the gate consults* is open, and the sentence
    # wrapped around that fact is not part of the assertion.
    check("the room is published, so the draft gate is not what the 12 writers hit",
          "published" in norm(pub.stdout), pub.stdout + pub.stderr)

    # 12 real processes, started back to back and not waited on one at a time.
    # `--body` is a sentence, never a bare `/<something>`, because a single-token
    # body that names a readable file is refused by the T-0224 path guard
    # (bin/aim:867) -- a refusal that would look like a concurrency failure.
    bodies = [f"writer {w} appends body W{w} to the room" for w in writers]
    procs = [subprocess.Popen(
        [sys.executable, str(AIM), "room", "say", "--as", w, "--channel", "ch",
         "--id", "r", "--body", body],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        for w, body in zip(writers, bodies)]
    # `communicate()` and take its return value: `Popen.stderr` is a stream, not
    # a string, and reading it directly is what the first version of this file
    # got wrong -- the detail expression raised AttributeError precisely in the
    # failing case, so a broken fabric reported a crash inside the test instead
    # of a FAIL. Each writer prints one short line, so draining the pipes in
    # order cannot deadlock the writers still running.
    drained = [p.communicate(timeout=120) for p in procs]
    rcs = [p.returncode for p in procs]
    errs = [(err or "") for _out, err in drained]
    check(f"all {WRITERS} concurrent writers exit 0",
          all(rc == 0 for rc in rcs),
          f"return codes {rcs}; first failure: " + next(
              (norm(e)[-160:] for e, rc in zip(errs, rcs) if rc), ""))

    log = root / "channels" / "ch" / "rooms" / "r.jsonl"
    recs = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]

    # The card's failure, stated as a line count. `>= 1` would pass on a fabric
    # that lost 11, so the assertion is the exact number.
    check(f"the room log holds exactly {WRITERS} records (a lost append is a missing line)",
          len(recs) == WRITERS, f"{len(recs)} of {WRITERS} landed")

    seen = sorted(r.get("body") for r in recs)
    check("the records are the 12 distinct bodies that were written (no duplicate passed for one)",
          seen == sorted(bodies),
          f"wrote {len(set(bodies))} distinct bodies, read back {len(seen)} records, "
          f"{len(set(seen))} distinct")

    # The lock's second witness. `seq` is allocated in the same critical section
    # as the append, so the ids must be r0001..r0012 exactly once each; a
    # released-before-append race gives two records the same id and leaves one
    # number unallocated even when all 12 lines survive.
    want_ids = [f"r{i:04d}" for i in range(1, WRITERS + 1)]
    got_ids = [r.get("id") for r in recs]
    check("the ids are r0001..r0012 with no gap and no duplicate (seq was allocated inside the append's lock)",
          sorted(got_ids) == want_ids, f"ids {sorted(got_ids)}")

    # `.get("hash")` rather than `["hash"]` on the expected side, on purpose: a
    # log written by a bared `open(path, "a")` carries no hash field at all, and
    # a KeyError here would report a crash in the test where the finding is
    # "every record's prev points at nothing".
    broken_prev = [(i, r.get("id"), r.get("prev"), recs[i - 2].get("hash"))
                   for i, r in enumerate(recs, 1)
                   if r.get("prev") != (recs[i - 2].get("hash") if i > 1 else "genesis")]
    check("every record chains onto the one before it, so the file is one order and not two interleaved",
          not broken_prev,
          f"{len(broken_prev)} break(s): " + "; ".join(
              f"{rid} prev={str(prev)[:12]} expected {str(exp)[:12]}"
              for _, rid, prev, exp in broken_prev[:3]))

    bad_hash = [(r.get("id"), r.get("hash")) for r in recs
                if sha256_hex(canonical({k: v for k, v in r.items() if k != "hash"}))
                != r.get("hash")]
    check("every record's hash is the hash of its own content (append_chained, bin/aim:454)",
          not bad_hash, f"{len(bad_hash)} record(s) mismatch: {bad_hash[:3]}")

    # Replay, not re-read: `prev` is carried forward as the *recomputed* digest,
    # so a file whose hashes were all rewritten consistently still fails here.
    # Carrying `r["hash"]` instead would make this check duplicate the one above
    # and measure nothing about recoverability.
    prev, replay_ok, replay_at = "genesis", True, ""
    for r in recs:
        want = sha256_hex(canonical({k: v for k, v in r.items() if k != "hash"}))
        if r.get("prev") != prev:
            replay_ok, replay_at = False, f"{r.get('id')} links to {str(r.get('prev'))[:12]}"
            break
        prev = want
    check("replaying the chain in file order reproduces every link (the order is recoverable, not merely present)",
          replay_ok, replay_at)

    # The tool's own walk over the same file, as an independent witness: my
    # recomputation and `aim verify` share no code, and a disagreement between
    # them is the interesting result.
    v = run("verify", "--channel", "ch")
    check("aim verify agrees the room chain is sound", v.returncode == 0,
          f"rc={v.returncode} {norm(v.stdout + v.stderr)[-200:]}")

print(f"\n{passed}/{passed + failed} checks passed")
print("The count is exact and the bodies are the set that was written on purpose: a test")
print("that asserted '>= 1 record' would pass on a room that lost eleven, which is the")
print("failure T-0026 names. The lock in bin/aim:2797 and the chain in bin/aim:425 are")
print("two mechanisms, and the checks above fail separately when either one is removed.")
sys.exit(1 if failed else 0)
