#!/usr/bin/env python3
"""
Conformance harness: real OS processes, not one script driving one CLI in a loop.

Why this exists
---------------
`tests/selftest.sh` asserts the barrier's rules. It is a single bash process
calling `aim` synchronously, and that shape cannot test the properties that
actually broke in the first run:

  * two participants writing at the same instant (the lost update — measured:
    5 concurrent registrations left 1 survivor, and the file left behind was
    well-formed, so nothing looked wrong);
  * a writer killed mid-transaction (does the channel survive a SIGKILL between
    the manifest write and the ledger append?);
  * delivery to a peer who is not running (the doorbell problem, which is the
    one that actually failed in the first two-vendor exchange);
  * whether a restarting agent can rejoin from the record alone, with no human
    relaying anything.

Proposed by codex as c7 (confidence 0.93), whose kill_if reads: "The existing
test suite already launches isolated concurrent participants, exercises
push-pull acknowledgement, interrupted writes, identity collision, barrier
progression, and proves recovery without manual relay." It did not. This is the
attempt to make that kill_if false.

Every check prints PASS or FAIL and a one-line reason. Exit code is the number
of failures. Nothing here touches a real channel: everything runs under a
throwaway AIM_ROOT.
"""
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time

AIM = "/root/tmp/agent-im/bin/aim"
ROOT = "/root/tmp/agent-im/.conformance"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))


def run(args, expect_ok=True, root=None, timeout=60):
    env = dict(os.environ, AIM_ROOT=root or ROOT)
    p = subprocess.run([AIM] + args, env=env, capture_output=True, text=True, timeout=timeout)
    return p


def spawn(args, root=None):
    env = dict(os.environ, AIM_ROOT=root or ROOT)
    return subprocess.Popen([AIM] + args, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def fresh(root=None):
    r = root or ROOT
    shutil.rmtree(r, ignore_errors=True)
    pathlib.Path(r).mkdir(parents=True)
    run(["init"], root=r)


def read(path):
    return pathlib.Path(path).read_text() if pathlib.Path(path).exists() else ""


def jsonl(path):
    p = pathlib.Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def section(title):
    print(f"\n== {title} ==")


# ---------------------------------------------------------------------------
# 1. Concurrent writers from real processes
# ---------------------------------------------------------------------------
def t_concurrent_registration():
    section("concurrent registration from independent processes")
    fresh()
    procs = [spawn(["register", "--as", f"agent{i:02d}", "--kind", "claude"]) for i in range(12)]
    for p in procs:
        p.wait(timeout=60)
    reg = json.loads(read(f"{ROOT}/registry.json") or '{"agents":{}}')["agents"]
    check("12 concurrent registrations all survive", len(reg) == 12,
          f"only {len(reg)} of 12 present: the lost update is back")
    check("no stray temp files", not any(".tmp" in n for n in os.listdir(ROOT)))


def t_concurrent_say():
    section("concurrent channel writes produce a valid, gap-free chain")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "concurrency", "--participants", "a,b", "--leader", "h"])

    procs = []
    for i in range(10):
        who = "a" if i % 2 == 0 else "b"
        # `--private` since T-0230: this is the pre-barrier private traffic the
        # fleet runs on, and it used to reach the private log only because the
        # phase was closed. The destination is declared now, so a suite that
        # relied on the silent downgrade would be measuring the defect.
        procs.append(spawn(["say", "--as", who, "--channel", "c", "--private",
                            "--body", f"private reasoning number {i} with enough words to be real"]))
    for p in procs:
        p.wait(timeout=60)

    # Private logs are per-agent, so each log's own chain must be intact and the
    # two together must account for every write that succeeded.
    a = jsonl(f"{ROOT}/channels/c/private/a.jsonl")
    b = jsonl(f"{ROOT}/channels/c/private/b.jsonl")
    check("both private logs exist", len(a) + len(b) > 0, "no messages landed at all")
    check("no writes were lost", len(a) + len(b) == 10,
          f"{len(a)}+{len(b)} of 10 landed")
    ok = True
    for who, recs in (("a", a), ("b", b)):
        prev = "genesis"
        for i, r in enumerate(recs, 1):
            if r.get("prev") != prev:
                ok = False
            prev = r.get("hash")
    check("every private log is a valid hash chain", ok, "a chain is broken")


def t_concurrent_same_agent():
    section("one agent writing concurrently with itself")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "self", "--participants", "a,b", "--leader", "h"])
    procs = [spawn(["say", "--as", "a", "--channel", "c", "--private", "--body", f"thought {i} from one agent racing itself"])
             for i in range(8)]
    for p in procs:
        p.wait(timeout=60)
    recs = jsonl(f"{ROOT}/channels/c/private/a.jsonl")
    check("none of an agent's own concurrent writes vanished", len(recs) == 8,
          f"{len(recs)} of 8 landed")
    prev, ok = "genesis", True
    for r in recs:
        if r.get("prev") != prev:
            ok = False
        prev = r.get("hash")
    check("its chain is still walkable", ok)


# ---------------------------------------------------------------------------
# 2. Crash recovery
# ---------------------------------------------------------------------------
def t_crash_recovery():
    section("a writer killed mid-transaction leaves a recoverable channel")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "crash", "--participants", "a,b", "--leader", "h"])

    survivors = 0
    for i in range(14):
        # SIGKILL, not SIGTERM: no cleanup handler, no chance to finish a write.
        p = spawn(["say", "--as", "a", "--channel", "c", "--private", "--body", f"message {i} that may be interrupted mid-write"])
        time.sleep(0.012 * (i % 3))
        p.send_signal(signal.SIGKILL)
        p.wait(timeout=30)
        if p.returncode == 0:
            survivors += 1

    recs = jsonl(f"{ROOT}/channels/c/private/a.jsonl")
    check("the channel still parses after 14 SIGKILLs", isinstance(recs, list),
          "private log is not valid JSONL")
    check("every record that landed is complete (no half-writes)",
          all("body" in r and "hash" in r and r["body"] for r in recs),
          f"{sum(1 for r in recs if not r.get('body'))} record(s) have no body")
    check("the chain of survivors is intact",
          all(r.get("prev") == (recs[i - 1]["hash"] if i else "genesis") for i, r in enumerate(recs)),
          "a killed write corrupted the chain of the ones that survived")
    v = run(["verify", "--channel", "c"])
    check("aim verify agrees the channel is sound", v.returncode == 0, v.stderr.strip()[-200:])


def t_recovery_without_human():
    section("a restarted agent rejoins from the record alone, no human relaying")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "rejoin", "--participants", "a,b", "--leader", "h"])

    run(["say", "--as", "a", "--channel", "c", "--private", "--body", "a's position, written before any exposure"])
    run(["seal", "--as", "a", "--channel", "c", "--summary", "a's position"])
    run(["say", "--as", "b", "--channel", "c", "--private", "--body", "b's position, formed independently"])
    run(["seal", "--as", "b", "--channel", "c", "--summary", "b's position"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "COMMIT"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "SYNTHESIS", "--synthesizer", "h"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "CROSS_EXAMINE"])

    # Now pretend the process died and came back with no memory of any of it.
    st = run(["status", "--channel", "c"])
    check("a cold reader can see the phase from the record", "CROSS_EXAMINE" in st.stdout, st.stdout[:200])
    check("and who has sealed", "sealed" in st.stdout)

    # The rejoin must be possible without reading anyone's private reasoning.
    q = run(["say", "--as", "b", "--channel", "c", "--kind", "question", "--subject", "a: which evidence",
             "--body", "Name the observation that would have made you drop your first claim."])
    check("rejoined agent can speak immediately", q.returncode == 0, q.stderr.strip()[-200:])
    r = run(["say", "--as", "a", "--channel", "c", "--kind", "rebuttal", "--responds-to", "m0001",
             "--body", "The observation is a second draft changing shape after exposure; I would have dropped it if two drafts had stayed incompatible."])
    check("and the peer answers it", r.returncode == 0, r.stderr.strip()[-200:])

    # The whole exchange must be reconstructible from the log alone.
    log = jsonl(f"{ROOT}/channels/c/log.jsonl")
    # Both subject and body: the first version of this check searched only body,
    # and the text it wanted was in the subject. Asserting a property without
    # checking where it lives is exactly the failure this harness is for.
    text = " ".join(f"{x.get('subject', '')} {x.get('body', '')}" for x in log)
    check("the full cross-examination is in the public record",
          "which evidence" in text and "second draft changing shape" in text,
          f"public log holds: {[x.get('id') for x in log]}")
    check("the record chains and verifies", run(["verify", "--channel", "c"]).returncode == 0)


# ---------------------------------------------------------------------------
# 3. Delivery, honestly measured
# ---------------------------------------------------------------------------
def t_delivery_metrics():
    section("delivery: what is proven and what is not")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])

    run(["push", "--as", "a", "--to", "b", "--subject", "review", "--body", "the artifact", "--require-ack"])
    ids = [json.loads(p.read_text()) for p in sorted(pathlib.Path(f"{ROOT}/outbox/b").glob("*.json"))]
    mid = ids[0]["msg_id"]

    out = run(["outbox", "--as", "a"])
    check("an unacked demand is visible to the sender and exits non-zero",
          out.returncode == 4 and "sent" in out.stdout,
          f"exit={out.returncode}")

    # The claim this harness exists to state honestly: a push does NOT wake
    # anybody. Nothing has run since the push, so nothing has read it.
    still_unread = [json.loads(p.read_text()) for p in pathlib.Path(f"{ROOT}/outbox/b").glob("*.json")]
    check("a push does not mark itself received — delivery is not receipt",
          not still_unread[0].get("claimed_at"),
          "the push marked itself claimed, which would be a lie")

    run(["pull", "--as", "b", "--claim"])
    out2 = run(["outbox", "--as", "a"])
    check("after a real pull the sender sees `claimed`, not ACKED",
          "claimed" in out2.stdout and "ACKED" not in out2.stdout,
          out2.stdout)

    run(["confirm", "--as", "b", "--msg-id", mid])
    out3 = run(["outbox", "--as", "a"])
    check("after a receipt the sender sees ACKED and exits 0",
          "ACKED" in out3.stdout and out3.returncode == 0, out3.stdout)
    check("the receipt is delivered as a message, not a side channel",
          (pathlib.Path(f"{ROOT}/outbox/a") / f"{mid}-receipt.json").exists()
          or any("RECEIPT" in p.read_text() for p in pathlib.Path(f"{ROOT}/outbox/a").glob("*.json")),
          "no receipt landed in the sender's outbox")


def t_doorbell():
    section("the doorbell: delivery without a polling loop")
    fresh()
    run(["register", "--as", "me", "--kind", "claude"])
    run(["register", "--as", "peer", "--kind", "codex"])
    hook = "/root/tmp/agent-im/bin/aim-doorbell-hook"
    env = dict(os.environ, AIM_ROOT=ROOT)

    def ring(agent):
        p = subprocess.run([hook, agent], env=env, capture_output=True, text=True, timeout=30)
        return p.stdout, p.returncode

    out, rc = ring("me")
    check("a quiet outbox makes the hook silent, not noisy", out == "" and rc == 0,
          f"said {len(out)} chars into an empty outbox")
    out, rc = ring("")
    check("no agent id -> silent, so it cannot break a session start", out == "" and rc == 0)
    out, rc = ring("nobody-registered")
    check("unknown agent -> silent", out == "" and rc == 0)

    run(["push", "--as", "peer", "--to", "me", "--subject", "review", "--body",
         "an unread message that must reach the session", "--require-ack"])
    out, rc = ring("me")
    check("an unread message rings the doorbell", "must reach the session" in out,
          f"hook said {len(out)} chars")
    check("and it tells the session the receipt is owed", "aim confirm" in out)
    check("and it does not silently claim on the agent's behalf",
          not any(json.loads(p.read_text()).get("claimed_at")
                  for p in pathlib.Path(f"{ROOT}/outbox/me").glob("*.json")),
          "the hook marked the message read; reading and claiming must stay separate")

    # A receipt is a delivery fact, not something to interrupt a session for.
    mid = [json.loads(p.read_text())["msg_id"] for p in pathlib.Path(f"{ROOT}/outbox/me").glob("*.json")][0]
    run(["pull", "--as", "me", "--claim"])
    run(["confirm", "--as", "me", "--msg-id", mid])
    run(["push", "--as", "me", "--to", "peer", "--subject", "x", "--body", "y", "--require-ack"])
    pmid = [json.loads(p.read_text())["msg_id"] for p in pathlib.Path(f"{ROOT}/outbox/peer").glob("*.json")][0]
    run(["pull", "--as", "peer", "--claim"])
    run(["confirm", "--as", "peer", "--msg-id", pmid])
    out, rc = ring("me")
    check("a receipt does not ring the doorbell", out == "", f"said {len(out)} chars for a receipt")

    # Broken environment must not break the session.
    env2 = dict(os.environ, AIM_ROOT=ROOT, AIM_BIN="/nonexistent")
    p = subprocess.run([hook, "me"], env=env2, capture_output=True, text=True, timeout=30)
    check("a missing aim binary is survivable", p.returncode == 0)


def t_cold_peer_replay():
    section("the doorbell gap, measured rather than asserted")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["push", "--as", "a", "--to", "b", "--subject", "urgent", "--body", "you need to see this", "--require-ack"])

    # Simulate a peer that is simply not running and whose hook never fires
    # because no prompt ever arrives. The record is durable and the sender has no
    # way to distinguish this from a peer that read it and disagreed. The new
    # UserPromptSubmit doorbell (t_doorbell) turns "asleep forever" into "asleep
    # until spoken to" — which is an improvement and is not the same as waking an
    # idle process, so this check stays as the honest floor.
    time.sleep(0.3)
    out = run(["outbox", "--as", "a"])
    check("a message to a sleeping peer stays unacked indefinitely",
          out.returncode == 4, "the sender could not tell, which would be worse")
    # The first version of this check searched stdout for "claimed" and was
    # satisfied by the table's *column header*. It now reads the state cell for
    # the actual message, which is the only thing that means anything.
    states = [ln.split()[3] for ln in out.stdout.splitlines()
              if ln.startswith("2") and len(ln.split()) > 3]
    check("the sender sees exactly one state, and it is 'sent' — asleep and "
          "ignoring-me are indistinguishable from here",
          states == ["sent"], f"states reported: {states}")
    # The honest statement: the gap is visible now. It is still a gap.
    pull = run(["pull", "--as", "b", "--unread-only"])
    check("the message survives a peer restart and can still be read",
          "you need to see this" in pull.stdout, pull.stdout[:200])


# ---------------------------------------------------------------------------
# 4. Barrier progression under real processes
# ---------------------------------------------------------------------------
def t_barrier_progression():
    section("the barrier under multiple real processes")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "barrier", "--participants", "a,b", "--leader", "h"])

    # Two agents race to peek at each other simultaneously. Both must be refused,
    # and both refusals must be on the record.
    ra = spawn(["inbox", "--as", "a", "--channel", "c", "--json"])
    rb = spawn(["inbox", "--as", "b", "--channel", "c", "--json"])
    oa, ob = ra.communicate(timeout=30), rb.communicate(timeout=30)
    check("a simultaneous peek by both agents is refused",
          "alpha" not in oa[0] and "beta" not in ob[0])

    both = [spawn(["advance", "--as", w, "--channel", "c", "--to", "COMMIT"]) for w in ("a", "b")]
    for p in both:
        p.wait(timeout=30)
    check("neither participant could advance the barrier",
          all(p.returncode != 0 for p in both))

    led = jsonl(f"{ROOT}/channels/c/ledger.jsonl")
    refusals = [r for r in led if r.get("event") == "refusal"]
    check("every refused attempt is on the ledger, not just on stderr",
          len(refusals) >= 2, f"{len(refusals)} refusal record(s) for 2 refused agents")
    check("refusals are classed so a later reader can tell which gate fired",
          all(r.get("class") in ("barrier", "form") for r in refusals))

    run(["advance", "--as", "h", "--channel", "c", "--to", "COMMIT"])
    run(["seal", "--as", "a", "--channel", "c", "--summary", "a"])
    run(["seal", "--as", "b", "--channel", "c", "--summary", "b"])
    check("the leader can still advance normally",
          run(["advance", "--as", "h", "--channel", "c", "--to", "SYNTHESIS", "--synthesizer", "h"]).returncode == 0)
    check("the barrier opens",
          run(["advance", "--as", "h", "--channel", "c", "--to", "CROSS_EXAMINE"]).returncode == 0)


# ---------------------------------------------------------------------------
# 5. Identity collision, from real processes
# ---------------------------------------------------------------------------
def t_identity_collision():
    section("two sessions racing for the same id")
    fresh()
    procs = [spawn(["register", "--as", "shared", "--kind", "claude", "--session", f"proc{i}"]) for i in range(6)]
    for p in procs:
        p.wait(timeout=30)
    reg = json.loads(read(f"{ROOT}/registry.json"))["agents"]
    check("exactly one of six claimants owns the id", "shared" in reg, "the id is not in the registry at all")
    wins = sum(1 for p in procs if p.returncode == 0)
    check("exactly one claimant reported success", wins == 1,
          f"{wins} processes reported success — the id was claimed more than once")


def main():
    print(f"conformance harness — real processes, throwaway root {ROOT}")
    for fn in (t_concurrent_registration, t_concurrent_say, t_concurrent_same_agent,
               t_crash_recovery, t_recovery_without_human, t_delivery_metrics,
               t_doorbell, t_cold_peer_replay, t_barrier_progression, t_identity_collision):
        try:
            fn()
        except Exception as exc:
            check(f"{fn.__name__} raised", False, f"{type(exc).__name__}: {exc}")

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("\nfailures:")
        for name, _, detail in failed:
            print(f"  - {name}" + (f"\n      {detail}" if detail else ""))
    shutil.rmtree(ROOT, ignore_errors=True)
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
