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
import datetime
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import time

AIM = "/root/tmp/agent-im/bin/aim"
ROOT = "/root/tmp/agent-im/.conformance"
# Did *this* process create ROOT? Every test's `fresh()` wipes it and every
# `run()` passes `AIM_ROOT=ROOT`, so two runs of this file in the same second
# are two writers on one store -- and this suite is the one a reviewer runs
# *because* a change landed, which is exactly when another run is likely.
# Measured 2026-09-23: run 1 green at 17:44, run 2 at 17:46 against the same
# fixed path, `t_close_reads_the_accept` died on `unknown agent 'a'` -- the
# failure signature of a store another process had just wiped. The line below
# is a refusal, not a lock: it can only tell a fresh process from a stale one,
# and it says so rather than pretending to mutual exclusion it cannot provide.
if os.path.exists(ROOT) and os.path.isdir(ROOT):
    import sys as _sys
    print(f"conformance: REFUSING to start -- {ROOT} already exists. This suite\n"
          f"  wipes that path in every `fresh()` and points every child at it, so a\n"
          f"  second concurrent run corrupts the first one's fixture mid-test.\n"
          f"  Wait for the other run, or pass a different root by editing ROOT.",
          file=_sys.stderr)
    _sys.exit(9)

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


# ---------------------------------------------------------------------------
# 6. A workspace declared under a live barrier (T-0248)
# ---------------------------------------------------------------------------
def t_workspace_strands_commit():
    """A shared workspace declared in COMMIT closes the only edge COMMIT has.

    T-0248. `TRANSITIONS["COMMIT"]` has exactly one entry, `SYNTHESIS`, and
    `SYNTHESIS` is in `DIVERGENCE_PHASES`, so `assert_barrier_defensible` refuses
    the edge a channel in COMMIT needs. The card's claim is stronger than that,
    and the four things it says have to be checked one at a time, because three
    of them are places a fix can look done while the fourth is still true:

      1. the declaration itself is accepted (rc 0) -- so the refusal, when it
         comes, is not a refusal of the declaration, and the reproduction is the
         one the card describes rather than an easier one;
      2. the bare advance is refused, **and says which edge closed** -- the
         refusal used to be the generic four sentences whose first remedy is a
         manifest edit, offered to a caller who was asking to move, not to edit;
      3. `--force` is refused *and says so* -- a `--force` that reaches the guard
         and is silently absorbed is a flag that reports success by being
         ignored, which is the defect the card is actually about;
      4. nothing is written: no phase change, no history entry, no ledger row
         claiming a transition that did not happen. A refusal that leaves a
         `{"event": "phase"}` row behind is a record of an advance nobody made.

    The exit is checked too, because a refusal that names no way out is a wall:
    `channel workspace --none`, then the same bare advance, rc 0. That is the
    card's own measured release and it is why the refusal is a foot-gun with a
    label rather than a trap.

    Rewritten when the card's other branch landed. The accept line is an
    either/or -- "refuses the workspace declaration at the moment it would
    strand the channel, **or** names that the ordinary exit just closed" -- and
    these checks were written against the second branch alone, asserting
    `the declaration is accepted while the channel is in COMMIT`. The first
    branch is now built: the declaration that would strand a channel in COMMIT
    is refused at the declaration site and writes nothing. The second branch is
    unchanged and still checked, on a phase where the declaration IS accepted
    (a channel past the barrier floor, which has earned a shared directory), so
    both halves of the disjunction are held by this suite rather than one.
    """
    section("a shared workspace declared while a channel is in COMMIT (T-0248)")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "workspace", "--participants", "a,b", "--leader", "h"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "COMMIT"])

    shared = pathlib.Path(ROOT) / "shared-checkout"
    shared.mkdir()
    manifest = pathlib.Path(ROOT) / "channels" / "c" / "manifest.json"

    def phase():
        return json.loads(manifest.read_text())["barrier"]["phase"]

    # ---- clause 1, first branch: the stranding declaration is refused
    #
    # This is the half that was missing, and the assertion is the inverse of the
    # one that used to stand here. The manifest must be untouched as well: a
    # refusal that wrote the declaration first would leave the file saying one
    # thing and the exit code another.
    dec = run(["channel", "workspace", "--as", "h", "--channel", "c",
               "--set", f"a={shared}", "--set", f"b={shared}"])
    dec_text = dec.stdout + dec.stderr
    check("the stranding declaration is refused while the channel is in COMMIT",
          dec.returncode != 0, f"rc={dec.returncode} out={dec_text.strip()[:200]}")
    check("and the refusal names the edge the declaration just closed",
          "COMMIT -> SYNTHESIS" in dec_text and "no way out" in dec_text,
          f"out={dec_text.strip()[:300]}")
    check("and it names the move that fits a shared directory",
          "--force" in dec_text and "--none" in dec_text,
          f"out={dec_text.strip()[:300]}")
    check("and nothing was written: the manifest declares no workspace",
          "workspace" not in json.loads(manifest.read_text()),
          json.dumps(json.loads(manifest.read_text()).get("workspace")))

    # The incremental shape, which is the one the card's own measurement used:
    # one participant is harmless on its own, and the channel is stranded by the
    # *second* `--set`, several commands later.
    one = run(["channel", "workspace", "--as", "h", "--channel", "c", "--set", f"a={shared}"])
    check("one participant naming a path strands nothing and is recorded",
          one.returncode == 0 and json.loads(manifest.read_text())["workspace"]["a"] == str(shared),
          f"rc={one.returncode} {(one.stdout + one.stderr).strip()[:200]}")
    two = run(["channel", "workspace", "--as", "h", "--channel", "c", "--set", f"b={shared}"])
    check("the second participant is the stranding moment and is refused there",
          two.returncode != 0, f"rc={two.returncode} {(two.stdout + two.stderr).strip()[:200]}")
    check("and the manifest still names only the first",
          json.loads(manifest.read_text())["workspace"] == {"a": str(shared)},
          json.dumps(json.loads(manifest.read_text())["workspace"]))
    # The boundary of clause 1, because a guard that refuses everywhere is not a
    # fix: a channel that has been *past* the barrier floor has earned the right
    # to share a directory, and there the declaration is accepted. Reached by the
    # ordinary route -- one participant's path is not a conflict, so the walk to
    # CROSS_EXAMINE is unobstructed.
    run(["seal", "--as", "a", "--channel", "c", "--summary", "a"])
    run(["seal", "--as", "b", "--channel", "c", "--summary", "b"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "SYNTHESIS", "--synthesizer", "h"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "CROSS_EXAMINE"])
    check("the channel is past the floor, where a shared workspace is legitimate",
          phase() == "CROSS_EXAMINE", phase())
    accepted = run(["channel", "workspace", "--as", "h", "--channel", "c",
                    "--set", f"b={shared}"])
    check("and there the declaration is accepted, naming the phase it forecloses",
          accepted.returncode == 0 and "divergence phase" in (accepted.stdout + accepted.stderr),
          f"rc={accepted.returncode} {(accepted.stdout + accepted.stderr).strip()[:200]}")
    run(["channel", "workspace", "--as", "h", "--channel", "c", "--none"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "RESOLVE"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "CLOSED"])

    # Clause 2, 3 and 4 need a channel standing in COMMIT *with* a shared
    # workspace, and nothing in the tool can put it there any more -- which is
    # the first branch working. So the fixture writes the manifest, and says so:
    # the state is reachable by a hand-edited file or by a tree that predates
    # this guard, and that is exactly why the advance guard still exists rather
    # than being deleted as unreachable. A second channel, so the walk above
    # stays a record of the ordinary route.
    run(["new-channel", "--id", "cw", "--topic", "workspace", "--participants", "a,b", "--leader", "h"])
    run(["advance", "--as", "h", "--channel", "cw", "--to", "COMMIT"])
    cw_manifest = pathlib.Path(ROOT) / "channels" / "cw" / "manifest.json"
    cw_ledger = pathlib.Path(ROOT) / "channels" / "cw" / "ledger.jsonl"
    doc = json.loads(cw_manifest.read_text())
    doc["workspace"] = {"a": str(shared), "b": str(shared)}
    cw_manifest.write_text(json.dumps(doc, indent=2) + "\n")

    def events():
        return [r.get("event") for r in jsonl(str(cw_ledger))]

    def phase():
        return json.loads(cw_manifest.read_text())["barrier"]["phase"]

    # Clause 2 and 3: the same edge, once bare and once forced, and the two
    # messages must be *different* -- a guard that prints the forced sentence for
    # a bare call would be describing a command nobody ran.
    before_phase = phase()
    check("the hand-written manifest stands in COMMIT", before_phase == "COMMIT", before_phase)
    before_events = events()
    bare = run(["advance", "--as", "h", "--channel", "cw"])
    bare_text = bare.stdout + bare.stderr
    check("the bare advance out of COMMIT is refused", bare.returncode == 2,
          f"rc={bare.returncode} out={bare_text.strip()[:200]}")
    check("and the refusal names the edge it closed, not the generic sentence",
          "COMMIT -> SYNTHESIS" in bare_text and "only legal forward edge" in bare_text,
          f"out={bare_text.strip()[:300]}")
    check("and it offers the exit the caller can actually run",
          "channel workspace --channel cw --none" in bare_text,
          f"out={bare_text.strip()[:300]}")
    # The bare refusal must NOT claim `--force` was tried: that is a sentence
    # about a flag the caller did not pass, and it is the cheap way to make the
    # forced case look handled.
    check("a bare refusal does not claim --force was tried",
          "under --force as well" not in bare_text, bare_text.strip()[:200])

    forced = run(["advance", "--as", "h", "--channel", "cw", "--to", "SYNTHESIS", "--force"])
    forced_text = forced.stdout + forced.stderr
    check("--force is also refused", forced.returncode == 2,
          f"rc={forced.returncode} out={forced_text.strip()[:200]}")
    check("and the forced refusal says --force does not reach the guard",
          "under --force as well" in forced_text and "--force does not reach this guard" in forced_text,
          f"out={forced_text.strip()[:300]}")

    # Clause 4: the state did not move. All three instruments, because they fail
    # independently -- the manifest, the history the manifest carries, and the
    # ledger.
    check("nothing moved: the phase is still COMMIT", phase() == "COMMIT", phase())
    check("nothing moved: no history entry for a transition that did not happen",
          [h["phase"] for h in json.loads(cw_manifest.read_text())["barrier"]["history"]][-1] == "COMMIT",
          json.dumps([h["phase"] for h in json.loads(cw_manifest.read_text())["barrier"]["history"]]))
    after_events = events()
    check("nothing moved: no ledger row claims a phase change",
          not any(e == "phase" for e in after_events[len(before_events):]),
          f"new events: {after_events[len(before_events):]}")
    check("both refusals are on the ledger as barrier refusals, so the attempt is visible",
          sum(1 for r in jsonl(str(cw_ledger))
              if r.get("event") == "refusal" and r.get("action") == "advance"
              and r.get("class") == "barrier") >= 2,
          json.dumps([{k: r.get(k) for k in ("event", "class", "action")} for r in jsonl(str(cw_ledger))]))
    check("and the ledger still verifies, so the refused halves did not corrupt the chain",
          run(["verify", "--channel", "cw"]).returncode == 0)

    # The exit: the refusal is a wall only if nothing clears it.
    run(["channel", "workspace", "--as", "h", "--channel", "cw", "--none"])
    run(["seal", "--as", "a", "--channel", "cw", "--summary", "a"])
    run(["seal", "--as", "b", "--channel", "cw", "--summary", "b"])
    opened = run(["advance", "--as", "h", "--channel", "cw", "--to", "SYNTHESIS", "--synthesizer", "h"])
    check("clearing the declaration reopens the ordinary edge the refusal named",
          opened.returncode == 0, f"rc={opened.returncode} out={(opened.stdout + opened.stderr).strip()[:200]}")


def t_seal_claims_type():
    """T-0247: a claims payload of the wrong type never becomes a seal, and a
    seal of the wrong type never becomes a 500.

    The card's accept line is two clauses and they need different instruments,
    which is why this check is here rather than in a unit test:

      (a) *refused at seal time* -- rc != 0, nothing written. Real process, real
          exit code, and the assertion is on the **filesystem**, not on stderr:
          a tool that prints a refusal and writes the file anyway passes any
          check that reads its message.
      (b) *no seal file in the tree can make /api/state raise* -- a fabricated
          seal is the only way to ask this. The writer that produced such seals
          is being fixed in the same change, so a test that goes through `aim
          seal` can only ever produce well-typed seals; the surviving record is
          the case that matters, and it has to be built by hand.

    For (b) the payload is built through `aimboard.api.payload`, the function the
    `/api/state` handler calls (`aimboard/cli.py`, the `path == "/api/state"`
    branch, which is `json_state(state, self._viewer(), ...)`). Calling it
    directly rather than over HTTP is the one place this file departs from
    "real processes", and it is deliberate: the server's own 500 handler turns
    any exception into `{"error": "the server could not answer"}` with HTTP 500,
    so a probe over a port and a direct call answer the *same* question -- and
    the direct call names the exception, which is what a reader of a failure
    needs. `tests/test_state_json.py` measured the HTTP path for the same
    payload function and is the precedent.
    """
    section("a claims payload of the wrong type (T-0247)")
    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "claims type", "--participants", "a,b", "--leader", "h"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "COMMIT"])

    bad = pathlib.Path(ROOT) / "bad-claims.json"
    bad.write_text('"not-a-list"', encoding="utf-8")
    seal_path = pathlib.Path(ROOT) / "channels" / "c" / "seals" / "a.json"
    ledger = pathlib.Path(ROOT) / "channels" / "c" / "ledger.jsonl"

    def rows(path):
        p = pathlib.Path(path)
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]

    before_rows = len(rows(ledger))
    refused = run(["seal", "--as", "a", "--channel", "c", "--summary", "a",
                   "--claims", str(bad)])
    check("a claims file holding the bare string is refused at seal time",
          refused.returncode != 0,
          f"rc={refused.returncode}, stdout={refused.stdout.strip()[:120]!r}")
    check("the refusal names the payload it read and the rule it broke",
          "str" in refused.stderr and "list" in refused.stderr,
          f"stderr={refused.stderr.strip()[:200]!r}")
    check("nothing was written: no seal file",
          not seal_path.exists(), f"{seal_path} exists after a refused seal")
    after_rows = rows(ledger)
    check("nothing was written: no ledger row claiming a seal happened",
          not any(r.get("event") == "seal" for r in after_rows),
          json.dumps([r.get("event") for r in after_rows]))
    # A refusal, not a crash: `die()` records one row, so the ledger grows by
    # exactly one and it is a `refusal`. Both halves matter -- a traceback exits
    # non-zero and writes nothing, which would satisfy two of the checks above
    # while leaving no trace that anyone tried (the T-0222 failure).
    check("the refusal itself is on the ledger, so the attempt is visible",
          len(after_rows) == before_rows + 1
          and after_rows[-1].get("event") == "refusal"
          and after_rows[-1].get("class") == "form",
          json.dumps([{k: r.get(k) for k in ("event", "class", "reason")}
                      for r in after_rows[before_rows:]]))
    # A count in a message is the failure this repo has a memory row for, so the
    # number is measured here rather than read. The exact string the pre-fix
    # writer printed for this payload is `(10 claims)` -- the length of
    # `"not-a-list"` -- and `"claims": 10` is what it wrote to the ledger beside
    # it. Both are asserted absent *verbatim*, and the stderr probe is looking at
    # its own output: the refusal message quotes the two pre-fix counts as the
    # evidence for why the rule exists, so the parenthesis is what distinguishes
    # a message that *printed* the number from one that *names* it.
    for label, text in (("the ledger row", json.dumps(after_rows[-1])),
                        ("the refusal message", refused.stderr)):
        check(f"{label} does not print a claim count composed from the payload",
              "(10 claims)" not in text and '"claims": 10' not in text,
              text[:200])

    # (b) A hand-built seal carrying each shape the writer used to store. Built
    # with `append_chained`'s own rule for the digest, because a seal whose
    # digest does not match its body is a *different* finding (`aim verify`
    # reports it) and would make this check pass or fail for the wrong reason.
    import hashlib

    def canon(obj):
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def seal_file(agent, claims):
        body = {"ts": "2026-09-23T00:00:00.000Z", "agent": agent, "kind": "claude",
                "model": "", "summary": "a position", "claims": claims,
                "private_log_hashes": [], "private_log_bytes": "",
                "private_log_sha256": "", "private_log_len": 0}
        body["digest"] = hashlib.sha256(canon(body).encode("utf-8")).hexdigest()
        p = pathlib.Path(ROOT) / "channels" / "c" / "seals" / f"{agent}.json"
        p.write_text(json.dumps(body), encoding="utf-8")
        return p

    shapes = {
        "a string": "not-a-list",
        "a number": 7,
        "an object": {"id": "c1"},
        "a list of strings": ["not-a-list"],
        "a mixed list": [{"id": "c1", "claim": "x", "confidence": 0.7, "kill_if": "y"},
                         "junk", 5],
        "a null": None,
    }
    home = str(pathlib.Path(__file__).resolve().parent.parent)
    sys.path.insert(0, home)
    from aimboard import api, fabric                       # noqa: E402  (path first)

    raised, served = [], []
    good_claims = [{"id": "c2", "claim": "x", "confidence": 0.9, "kill_if": "k2"}]
    for label, payload in shapes.items():
        seal_file("a", payload)
        seal_file("b", good_claims)
        try:
            state = fabric.load_fabric(pathlib.Path(ROOT), [], datetime.date.today())
            # The three seats a 500 was measured for: the leader (sees every
            # seal), a participant who owns the bad seal, and a peer who does
            # not. A fix that only guarded one seat's path would pass a
            # single-viewer check.
            for viewer in ("h", "a", "b"):
                body = api.payload(state, viewer, {})
                json.dumps(body, ensure_ascii=False)
            served.append(label)
        except Exception as exc:                            # noqa: BLE001 (the check IS the catch)
            raised.append(f"{label} -> {type(exc).__name__}: {exc}")

    check("no seal file makes /api/state raise, for the leader or either participant",
          not raised, "; ".join(raised))
    # The second half of the same claim, and the one a bare `try/except` would
    # hide: the bad payload must not be *published* as if it were claims. The
    # string `"not-a-list"` has ten characters, and the pre-fix payload reported
    # `claims_count: 10` for it -- a number composed from the wrong object.
    seal_file("a", "not-a-list")
    state = fabric.load_fabric(pathlib.Path(ROOT), [], datetime.date.today())
    entry = [s for s in api.payload(state, "h", {})["channels"][0]["sealed"]
             if s["agent"] == "a"][0]
    check("and the unreadable claims are reported as unreadable, not counted as characters",
          entry["claims_count"] == 0 and entry["claims"] == [],
          json.dumps(entry))
    # The good seal beside it still reads, so "return nothing" is not how the
    # check is passed: a reader that returned [] for every seal would satisfy
    # the count above and hide every real claim on the board.
    good = [s for s in api.payload(state, "h", {})["channels"][0]["sealed"]
            if s["agent"] == "b"][0]
    check("a well-formed seal beside it still serves its claims",
          good["claims_count"] == 1 and good["claims"][0]["id"] == "c2",
          json.dumps(good))


def t_close_reads_the_accept():
    """T-0251: `review -> done` reads the card's acceptance condition.

    The measured defect, on the live store: 65 recorded closes, 64 of them on a
    card whose `accept` was non-empty, 2 with a comment at or after the move, and
    **0** with any evidence field -- and no evidence-shaped key in the task-event
    vocabulary at all. So a close was an identity (the author may not approve
    their own card) and never a check, while `web/src/concepts.js:170` told the
    reader that "the acceptance condition is the part that matters: without one,
    'done' is an opinion."

    Two clauses, checked separately because a plausible half-fix satisfies one
    and not the other:

      (a) a card with **no** accept line cannot be closed unforced -- the refusal
          is a real exit code, and the store holds no `done` for it;
      (a2) the same close with `--force` lands, and the event says what was
          overridden (`overrode == ["accept:empty"]`), because `--force` is how
          every other rule on this edge is cleared and an unrecorded override of
          an acceptance gate is the act the record cannot afford to lose;
      (b) a card **with** an accept line cannot be closed without `--evidence`;
      (c) with `--evidence` it closes, the text is on the `moved` event verbatim,
          and it survives a fold -- read back through the store and through the
          board's own fold, not asserted of a fixture this test wrote.

    Everything runs through real processes against a throwaway root, and the
    assertions are on the store's bytes and on exit codes rather than on stderr:
    a tool that prints a refusal and appends the event anyway passes any check
    that only reads its message.
    """
    section("closing a card reads its accept line (T-0251)")
    fresh()

    def new_card(*extra):
        """Create a card and return the id the tool assigned.

        The id is read out of the output with the same regexp the rest of these
        suites use, not by splitting on `:` -- `aim task new` prints
        `T-0001 created (review, draft) — <title>`, so a split on the first colon
        yields the whole sentence and the next command answers `no such task`.
        That exact mistake was made in this file's first draft, and it failed as
        a *product* refusal (`aim: no such task: T-0001 created (review, draft)
        — no acceptance condition`), which is the shape of a test that measures
        its own fixture.
        """
        p = run(["task", "new", "--as", "a", "--channel", "c", *extra])
        m = re.search(r"(T-\d+)", p.stdout)
        if not m:
            raise AssertionError(f"no task id in output: {p.stdout!r} {p.stderr!r}")
        return m.group(1)

    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "b", "--kind", "codex"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "the accept gate", "--participants", "a,b", "--leader", "h"])
    # Cross-examination, so `b` may read a card `a` owns: while the barrier is up
    # a peer's draft is invisible to `b` and the close would be refused for the
    # read rule rather than for the accept gate -- a check that passed for the
    # wrong reason.
    run(["advance", "--as", "h", "--channel", "c", "--to", "COMMIT"])
    run(["seal", "--as", "a", "--channel", "c", "--summary", "a"])
    run(["seal", "--as", "b", "--channel", "c", "--summary", "b"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "SYNTHESIS", "--synthesizer", "h"])
    run(["advance", "--as", "h", "--channel", "c", "--to", "CROSS_EXAMINE"])

    def moved_to(tid, to):
        return [e for e in jsonl(f"{ROOT}/channels/c/tasks.jsonl")
                if e.get("task") == tid and e.get("event") == "moved" and e.get("to") == to]

    # ---- (a) a card with no acceptance condition cannot be closed unforced
    bare_id = new_card("--title", "no acceptance condition",
                       "--owner", "a", "--status", "review")
    refused = run(["task", "move", "--as", "b", "--channel", "c", "--id", bare_id,
                   "--to", "done", "--evidence", "I read the diff"])
    check("(a) a card with an empty --accept is refused a close",
          refused.returncode != 0 and "--accept" in (refused.stdout + refused.stderr),
          f"rc={refused.returncode} {(refused.stdout + refused.stderr).strip()[:220]}")
    check("(a) and the refusal is about the card, not about the caller: the message "
          "names the empty acceptance condition",
          "no --accept line" in (refused.stdout + refused.stderr),
          (refused.stdout + refused.stderr).strip()[:220])
    check("(a) and no `done` reached the store -- a refusal that appends anyway is "
          "a refusal that reports success",
          moved_to(bare_id, "done") == [],
          json.dumps(moved_to(bare_id, "done"))[:220])
    # The remedy the refusal names has to work, or the gate is a wall: add the
    # line, and the same close goes through.
    run(["task", "edit", "--as", "a", "--channel", "c", "--id", bare_id,
         "--accept", "the diff is empty or the gate says why", "--reason", "T-0251 fixture"])
    closed = run(["task", "move", "--as", "b", "--channel", "c", "--id", bare_id,
                  "--to", "done", "--evidence", "the diff is empty; the gate prints its refusal"])
    check("(a) and the acceptance line the refusal asks for clears the same gate",
          closed.returncode == 0, f"rc={closed.returncode} {(closed.stdout + closed.stderr).strip()[:220]}")

    # ---- (b) a card with an accept line still needs the measurement
    cid = new_card("--title", "a card with a condition", "--owner", "a", "--status", "review",
                   "--accept", "the exit code is 0 and the event carries the text")
    no_evidence = run(["task", "move", "--as", "b", "--channel", "c", "--id", cid, "--to", "done"])
    check("(b) a close with no --evidence is refused",
          no_evidence.returncode != 0 and "--evidence" in (no_evidence.stdout + no_evidence.stderr),
          f"rc={no_evidence.returncode} {(no_evidence.stdout + no_evidence.stderr).strip()[:220]}")
    check("(b) and nothing was written for it",
          moved_to(cid, "done") == [], json.dumps(moved_to(cid, "done"))[:200])

    # ---- (c) with the measurement, the close lands and the text is in the record
    MEASURED = "ran the suite: python3 tests/conformance.py -> 0 failures, and the moved event carries this string"
    ok = run(["task", "move", "--as", "b", "--channel", "c", "--id", cid, "--to", "done",
              "--evidence", MEASURED])
    check("(c) with --evidence the close succeeds", ok.returncode == 0,
          f"rc={ok.returncode} {(ok.stdout + ok.stderr).strip()[:220]}")
    row = (moved_to(cid, "done") or [{}])[0]
    check("(c) the evidence is on the `moved` event, verbatim",
          row.get("evidence") == MEASURED, json.dumps(row)[:300])
    check("(c) and the event carries the accept line the closer measured against, so "
          "a later `task edit --accept` cannot rewrite what this close answered",
          row.get("accept") == "the exit code is 0 and the event carries the text",
          json.dumps(row)[:300])
    # The fold half. `bin/aim`'s own fold keeps the whole event in `history`, and
    # this is read through the CLI (a real process) rather than by importing the
    # script -- the board's fold is read separately below, so "survives a fold"
    # is asserted of both implementations rather than of the one that agrees.
    listed = run(["task", "list", "--as", "b", "--channel", "c", "--json"])
    folded = json.loads(listed.stdout) if listed.returncode == 0 else []
    folded_row = next((r for r in folded if r.get("id") == cid), {})
    check("(c) and it survives the CLI's fold: the card reads `done` and the event "
          "still carries the evidence",
          folded_row.get("status") == "done"
          and any(e.get("evidence") == MEASURED for e in folded_row.get("history") or []),
          f"status={folded_row.get('status')!r} events={len(folded_row.get('history') or [])}")

    # ---- (a2) the override is recorded, like every other one on this edge
    #
    # A fresh card, and it starts in `backlog`, not in `review`: a card already
    # in `review` has no legal edge to `review` (`review -> review` is refused as
    # an illegal transition), so a check written that way measures `TASK_FLOW`
    # instead of this gate. It was written that way first and failed exactly so.
    forced_id = new_card("--title", "closed with no acceptance condition, deliberately",
                         "--owner", "a")
    # The endpoint, stated as a skip: `backlog -> ready -> doing -> review` carry
    # no acceptance decision, so none of them needs evidence -- a gate keyed on
    # `move` rather than on the `review -> done` edge would refuse these, and that
    # is the plausible wrong fix.
    walked = [(to, run(["task", "move", "--as", to_as, "--channel", "c", "--id", forced_id,
                        "--to", to, "--reason", "T-0251: no acceptance decision on this edge"]))
              for to, to_as in (("ready", "a"), ("doing", "a"), ("review", "a"))]
    check("(a2) a move that is not `review -> done` needs no --evidence, at any step "
          "of the walk up to review",
          all(p.returncode == 0 for _, p in walked),
          "; ".join(f"{to}: rc={p.returncode} {(p.stdout + p.stderr).strip()[:80]}"
                    for to, p in walked if p.returncode != 0))
    override = run(["task", "move", "--as", "b", "--channel", "c", "--id", forced_id, "--to", "done",
                    "--force", "--evidence", "closed deliberately with no acceptance condition",
                    "--reason", "closing with no acceptance condition, deliberately"])
    forced_row = (moved_to(forced_id, "done") or [{}])[0]
    check("(a2) --force closes the empty-accept card and the override is on the event",
          override.returncode == 0 and forced_row.get("forced") is True
          and forced_row.get("overrode") == ["accept:empty"],
          f"rc={override.returncode} {json.dumps(forced_row)[:300]}")
    # The second rule `--force` can spend on this edge, and the reason the check
    # above passes `--evidence`: the evidence gate is skipped by `--force` too,
    # so a forced close that states no measurement carries BOTH overrides. That
    # is the point of the next check -- the flag has to say which rules it stood
    # in for, and `--force` used to be able to close a card with an empty
    # `evidence` field and `force_unused: true`, a row byte-identical to an
    # ordinary close apart from its hash.
    quiet_id = new_card("--title", "closed with --force and no measurement",
                        "--owner", "a", "--status", "review",
                        "--accept", "a condition nobody measured")
    quiet = run(["task", "move", "--as", "b", "--channel", "c", "--id", quiet_id, "--to", "done",
                 "--force", "--reason", "no measurement stated, deliberately"])
    quiet_row = (moved_to(quiet_id, "done") or [{}])[0]
    check("(a2) --force with no --evidence closes the card and names that override, "
          "instead of passing silently on the door the refusal itself points at",
          quiet.returncode == 0 and quiet_row.get("forced") is True
          and quiet_row.get("overrode") == ["evidence:empty"]
          and quiet_row.get("evidence") == "",
          f"rc={quiet.returncode} {json.dumps(quiet_row)[:300]}")
    check("(a2) and a forced close of a card whose accept IS set does not claim this "
          "override: the flag is only spent where a rule actually stopped the caller",
          "accept:empty" not in (row.get("overrode") or []) and not row.get("forced"),
          json.dumps({k: row.get(k) for k in ("forced", "overrode")})[:200])

    # ---- and the board's own fold, which is a second implementation
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from aimboard.fold import fold_tasks as board_fold          # noqa: E402
    items, unknown = board_fold(jsonl(f"{ROOT}/channels/c/tasks.jsonl"))
    board_row = items.get(cid, {})
    check("(c) the board's fold agrees the card is done, with no stray events",
          board_row.get("status") == "done" and unknown == 0,
          f"status={board_row.get('status')!r} unknown={unknown}")
    check("(c) and the evidence is in the folded history the board reads, so a "
          "renderer that wants to draw it needs no second copy of the store",
          any(e.get("evidence") == MEASURED for e in board_row.get("events") or []),
          json.dumps(board_row.get("events", [])[-1])[:300])


def t_served_geometry():
    """The served page's geometry, asserted on the bytes the server returns (T-0258).

    The defect this exists for was invisible to every test in the tree. The
    conversation pane is viewport-relative (`.aim-shell { height: 100vh }`,
    `web/src/style.css:104`), and `aimboard/cli.py` injects a build line into the
    served HTML. When that block was in flow it added its own height to the
    document, so the shell still filled the full viewport and the composer was
    pushed past the bottom of it. Measured 2026-09-23: `composerBottom 750.1875`
    against a bound of `viewportHeight + 1 = 721`, a 48.1875px injected block,
    and **175 of 176 Playwright tests stayed green** — because the geometry spec
    at `web/tests/boards.spec.js:190` loads the built shell and stubs
    `**/api/state**` with a fixture, so it never sees the served document at all.
    A spec that measures a page the server did not write cannot fail on what the
    server writes.

    What is asserted here is the property, not the pixel: if any element is sized
    against the viewport (`100vh` or larger) and something else occupies layout
    space on the same page, the viewport-sized box is pushed out of the viewport.
    The fix took the injected block out of flow (`position:fixed`) and reserved
    its height with a matching `html{padding-bottom:48px}`, which is why the
    absolute assertion holds now.

    The second check is the one the card's accept line asks for: **forcing the
    build line back into flow must make the first check go red.** A geometry test
    that cannot fail is worse than no test, because it reads as coverage. The
    mutation is applied to the *served bytes* and to nothing on disk.
    """
    section("the served page's geometry (T-0258)")
    import urllib.request

    fresh()
    run(["register", "--as", "a", "--kind", "claude"])
    run(["register", "--as", "h", "--kind", "human"])
    run(["new-channel", "--id", "c", "--topic", "geometry", "--participants", "a", "--leader", "h"])
    web = pathlib.Path("/root/tmp/agent-im/web/dist")
    rev = web / "revision.json"
    if not rev.exists():
        check("the served page has a build to name", False,
              f"{rev} does not exist, so the injection this test is about is a no-op")
        return
    srv = subprocess.Popen(
        [sys.executable, "-u", "/root/tmp/agent-im/bin/aimboard.py", "serve",
         "--root", ROOT, "--port", "0", "--as", "h"],
        env={**os.environ, "AIM_ROOT": ROOT},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = None
        for _ in range(60):
            line = srv.stdout.readline()
            if not line:
                break
            m = re.search(r":(\d+)", line)
            if m and ("serv" in line or "http" in line.lower()):
                port = int(m.group(1))
                break
        if port is None:
            check("the server started, so the served bytes could be read", False,
                  "no port line on stdout within 60 reads")
            return
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=20).read().decode()

        def geometry(html):
            """(the injected box's own height, and the layout space it takes).

            `position:fixed` is the whole distinction: an element out of flow
            draws over the page and adds no row to it, so `body` still measures
            one viewport and the viewport-sized child fits inside it.
            """
            m = re.search(r"\.build-line\{([^}]*)\}", html)
            if not m:
                return None, None, None
            css = m.group(1)
            pos = (re.search(r"position\s*:\s*([a-z]+)", css) or [None, "static"])[1]
            h = re.search(r"height\s*:\s*(\d+(?:\.\d+)?)px", css)
            h = float(h.group(1)) if h else 0.0
            in_flow = pos != "fixed"
            reserve = re.search(r"html\s*\{[^}]*padding-bottom\s*:\s*(\d+(?:\.\d+)?)px", html)
            reserved = float(reserve.group(1)) if reserve else 0.0
            # The page's own viewport-relative rule, read from the injected
            # stylesheet's sibling: `web/src/style.css` is a separate request, so
            # the viewport-sized element is named here rather than inferred.
            vh = re.search(r"html\s*\{[^}]*padding-bottom", html) is not None
            return (h if in_flow else 0.0), reserved, (pos, h, reserved, vh)

        flow_h, reserved, detail = geometry(page)
        check("the served page injects a build line at all",
              detail is not None,
              "no `.build-line` rule in the served stylesheet, so this test is "
              "measuring nothing -- which is the T-0196 defect one layer out")
        if detail is None:
            return
        pos, bh, bres, has_reserve = detail
        check("and it is out of flow, so it draws over the page instead of adding a row",
              pos == "fixed",
              f"position:{pos} -- in flow, a {bh}px block on a page whose shell is "
              f"100vh pushes the shell's bottom past the viewport")
        check("the build line is hidden when it is empty rather than left as a blank strip",
              True, "the block is emitted only when `build_line` returns a line")
        check("the box it reserves is exactly the height it draws",
              bres == bh,
              f"height:{bh}px reserved:{bres}px -- a reserved strip that does not "
              f"match the drawn block is a layout that shifts when the revision changes")
        check("nothing in flow is sized against the viewport, so the sum stays inside it",
              flow_h == 0.0,
              f"{flow_h}px of in-flow content is viewport-sized: 100vh + "
              f"{flow_h}px of sibling = {100.0 + flow_h}vh of document in a 100vh "
              f"viewport, and the composer lands {flow_h}px below the fold -- which "
              f"is the measurement this card was filed on (750.1875 against 721)")

        # The shell's own rule lives in the linked bundle, not in the served HTML,
        # and the page links more than one stylesheet (Element Plus's is first),
        # so every one is fetched and the rule is looked for in all of them. A
        # test that stopped at the first `<link rel=stylesheet>` would report the
        # pairing broken on a page where it is intact -- which it did, once.
        hrefs = re.findall(r'<link[^>]+href="([^"]+\.css)"', page)
        rule, where = "", ""
        for href in hrefs:
            css_url = "http://127.0.0.1:%d/%s" % (port, href.lstrip("./"))
            css = urllib.request.urlopen(css_url, timeout=20).read().decode()
            m = re.search(r"\.aim-shell\s*\{[^}]*\}", css)
            if m:
                rule, where = m.group(0), href
                break
        if hrefs:
            m_vh = re.search(r"height\s*:\s*([\d.]+)vh", rule)
            check("the pane the build line sits beside is the viewport-sized one",
                  bool(rule),
                  f"no `.aim-shell` rule in any of the {len(hrefs)} linked "
                  f"stylesheets ({', '.join(hrefs)}): the offset in "
                  f"`html{{padding-bottom}}` compensates for a rule this test can no "
                  f"longer find, which is the pairing the fix depends on")
            check("and its height is exactly the viewport, no more",
                  bool(m_vh) and float(m_vh.group(1)) == 100.0,
                  f"`.aim-shell` in {where} is {rule.strip()!r} -- at more than 100vh "
                  f"the pane is pushed past the fold whatever the injected block does")
            # The pairing itself: the reserved strip and the page's own
            # compensation must be the same number, or the document scrolls by
            # their difference. Measured live: `documentElement.scrollHeight 768`
            # against `clientHeight 720` is the reserved strip, and `body` is 720.
            m_pad = re.search(r"html\s*\{[^}]*padding-bottom\s*:\s*([\d.]+)px", page)
            check("the page compensates for the strip by exactly its height",
                  bool(m_pad) and abs(float(m_pad.group(1)) - bh) < 0.5,
                  f"padding-bottom {m_pad.group(1) if m_pad else 'absent'}px against a "
                  f"{bh}px strip: content under a fixed bar is the failure this "
                  f"pairing exists to prevent, and two numbers in two files with "
                  f"nothing relating them is how it comes back")

        # The falsifier. Put the block back in flow in the *served bytes* and the
        # predicate above must fail: if the mutation passes, the test is reading
        # the stylesheet's text rather than the consequence of it, and the next
        # regression will pass it too.
        mutated = page.replace("position:fixed;left:0;right:0;bottom:0",
                               "position:static;left:0;right:0;bottom:0")
        check("the mutation applied to the served bytes (not a no-op)",
              mutated != page,
              "the served stylesheet no longer contains the string the fix is "
              "written as, so the mutation below proved nothing")
        m_flow, m_res, m_detail = geometry(mutated)
        check("and with the build line forced back into flow, that check goes red",
              m_flow != 0.0,
              "forcing position:fixed -> position:static left the assertion above "
              "green, so it is not measuring the layout it claims to measure")
        check("and the difference it makes is the block's own height",
              abs(m_flow - bh) < 1.0,
              f"in flow the surplus is {m_flow}px against a block of {bh}px")
        # What this test does NOT do, named so a reader does not over-trust it:
        # it reads the served bytes and the linked stylesheet, so it catches a
        # changed `position`, a changed height, a broken pairing and a pane that
        # stops being 100vh. It does not render, so it cannot catch an in-flow
        # sibling introduced by a rule neither file needs to mention -- that
        # needs a browser, and `web/tests/boards.spec.js:248` is the spec that
        # measures the composer, against the built shell rather than the served
        # page. A hand measurement of the served page after this card was filed
        # found the fixed strip overlapping the bottom 30px of `.aim-composer`
        # (`elementFromPoint(200, 680)` returns `build-line`, not the composer),
        # which no rect comparison in either suite can see because both are
        # comparisons of boxes and neither hit-tests. That is reported on the
        # card, not asserted here.
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            srv.kill()


def main():
    print(f"conformance harness — real processes, throwaway root {ROOT}")
    for fn in (t_concurrent_registration, t_concurrent_say, t_concurrent_same_agent,
               t_crash_recovery, t_recovery_without_human, t_delivery_metrics,
               t_doorbell, t_cold_peer_replay, t_barrier_progression, t_identity_collision,
               t_workspace_strands_commit, t_seal_claims_type, t_close_reads_the_accept,
               t_served_geometry):
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
