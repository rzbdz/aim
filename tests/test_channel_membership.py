"""Joining a channel, and whether the remedies a refusal names actually work.

Two defects, both measured on the live fabric, both about a registered agent that
is not a participant of the channel it is talking to -- the "stranger" this project
spends a lot of words on.

1. `aim task list` refuses a stranger's read and then recommends
   `--owner <the stranger>`. The exemption that would have honoured that request
   was ANDed with channel membership, so it could never fire for exactly the
   caller it was written for, and the recommended remedy returned the identical
   refusal. The rule the code's own comment states -- "a result that can only
   contain your own rows cannot leak a peer's" -- does not depend on membership.

2. The refusal's "(you own N of them)" was computed from the post-filter result
   set, so it tracked the *requested* owner rather than the caller. Same viewer,
   `--owner gamma` and `--owner delta`, two different claims about what the
   viewer owned. On the live fabric the same seat produced 23 / 21 / 1.

And one missing verb. `aim new-channel` was the only place `participants` was
ever written, so an agent that was registered after the channel was opened could
never be joined to it: every speaking verb refuses a non-participant, and none
of them can create the membership they test for. `aim channel add` is the join,
leader-only and recorded in the ledger so a membership change is in the record
and not only in a file.

Group C is T-0226, the leader's own rule -- `the task should not belong to
anyone before assigned, anyone (existing, new join guy) could pickup not
assigned tasks` -- which has three halves that fail independently: a card
created without `--owner` must not be handed to its creator by default, an
unowned card must be readable by every participant in every phase (it states no
position, so the barrier has nothing to protect on it), and taking one must be a
recorded `assigned` with `from: ""` rather than a private intention. It also
pins the two edges the rule needs to be livable: an *owned* draft keeps the old
rule unchanged, and a claim that a peer already holds is refused rather than
overwritten.

Run: python3 tests/test_channel_membership.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    env = dict(os.environ, AIM_ROOT=str(root))

    def run(*argv):
        return subprocess.run([sys.executable, str(AIM), *argv], capture_output=True,
                              text=True, env=env, timeout=60)

    def ledger(ch):
        path = root / "channels" / ch / "ledger.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    run("init")
    for who in ("alpha", "beta", "gamma", "delta", "newcomer"):
        run("register", "--as", who, "--kind", "codex", "--session", "membership test")
    run("register", "--as", "lead", "--kind", "human", "--session", "membership test")

    # ---------------------------------------------------------------- group A
    # A channel in a divergence phase, holding: two drafts the viewer owns, one
    # draft a peer owns (so something is withheld), and published items owned by
    # two other agents (so `--owner <third party>` has visible rows to count).
    out = run("new-channel", "--id", "c", "--topic", "membership and remedies",
              "--participants", "alpha,beta,gamma,delta", "--leader", "lead",
              "--synthesizer", "gamma")
    check("Group A setup: the channel is in a divergence phase",
          "SEALED_DIVERGENT" in out.stdout, out.stdout + out.stderr)
    # A card is born unowned as of T-0226, so this fixture has to *own* its
    # drafts the way the leader's rule says work is owned: out loud, by a claim.
    # Left unowned, every card below would be readable by every participant and
    # A1's refusal would have nothing to withhold -- passing for the wrong
    # reason, which is the failure the rest of this file is about.
    run("task", "new", "--as", "alpha", "--channel", "c", "--title", "alpha one")
    run("task", "claim", "--as", "alpha", "--channel", "c", "--id", "T-0001")
    run("task", "new", "--as", "alpha", "--channel", "c", "--title", "alpha two")
    run("task", "claim", "--as", "alpha", "--channel", "c", "--id", "T-0002")
    run("task", "new", "--as", "beta", "--channel", "c", "--title", "beta draft")
    run("task", "claim", "--as", "beta", "--channel", "c", "--id", "T-0003")
    run("advance", "--as", "lead", "--channel", "c", "--to", "COMMIT")
    for who in ("alpha", "beta", "gamma", "delta"):
        run("seal", "--as", who, "--channel", "c", "--summary", f"position {who}")
    import time
    for to in ("SYNTHESIS", "CROSS_EXAMINE"):
        run("advance", "--as", "lead", "--channel", "c", "--to", to)
    time.sleep(1)
    run("task", "new", "--as", "gamma", "--channel", "c", "--title", "gamma pub",
        "--visibility", "published")
    for i in (1, 2, 3):
        run("task", "new", "--as", "delta", "--channel", "c", "--title", f"delta pub {i}",
            "--visibility", "published")
    run("advance", "--as", "lead", "--channel", "c", "--to", "SYNTHESIS")
    phase = json.loads((root / "channels" / "c" / "manifest.json").read_text())["barrier"]["phase"]
    check("Group A setup: the channel is back in a divergence phase to be refused in",
          phase in ("SEALED_DIVERGENT", "COMMIT", "SYNTHESIS"), phase)

    proc = run("task", "list", "--as", "alpha", "--channel", "c", "--owner", "gamma")
    check("A1 a peer's rows are still refused (the gate did not simply open)",
          proc.returncode != 0, proc.stdout + proc.stderr)

    me = re.search(r"\(you own (\d+) work item", proc.stderr)
    check("A2 the refusal states what the viewer owns", me is not None, proc.stderr[:300])
    proc2 = run("task", "list", "--as", "alpha", "--channel", "c", "--owner", "delta")
    me2 = re.search(r"\(you own (\d+) work item", proc2.stderr)
    check("A3 the count does not change with the requested owner",
          me and me2 and me.group(1) == me2.group(1),
          f"gamma -> {me and me.group(1)}; delta -> {me2 and me2.group(1)}")
    check("A4 the count is the VIEWER's own (alpha owns 2), not the requested owner's",
          me is not None and me.group(1) == "2", me and me.group(1))

    # The defect itself: a registered agent that is not a participant, asking for
    # its *own* rows. That request can only return rows it already owns.
    run("register", "--as", "stranger", "--kind", "codex", "--session", "not a participant")
    proc = run("task", "list", "--as", "stranger", "--channel", "c", "--owner", "stranger")
    check("A5 a registered non-participant is not refused for asking for its own rows",
          proc.returncode == 0, proc.stdout + proc.stderr)

    # The general rule, tested generically rather than by hard-coding the fix:
    # every remedy named inside a refusal message must work when it is run.
    refusal = run("task", "list", "--as", "stranger", "--channel", "c", "--owner", "gamma")
    remedy = re.search(r"--owner (\S+) for your own work", refusal.stderr)
    check("A6 the refusal names an owner remedy", remedy is not None, refusal.stderr[:300])
    if remedy:
        again = run("task", "list", "--as", "stranger", "--channel", "c",
                    "--owner", remedy.group(1))
        check("A7 and that named remedy works when it is actually run",
              again.returncode == 0, again.stdout + again.stderr)
    hidden = run("task", "list", "--as", "stranger", "--channel", "c", "--count-hidden")
    check("A8 the other named remedy (--count-hidden) works too",
          hidden.returncode == 0 and '"withheld"' in hidden.stdout,
          hidden.stdout + hidden.stderr)
    check("A9 the outsider's refusal is recorded as a barrier event",
          any(r.get("event") == "refusal" and r.get("agent") == "stranger"
              and r.get("class") == "barrier" for r in ledger("c")),
          json.dumps([r for r in ledger("c") if r.get("agent") == "stranger"])[:400])

    # ---------------------------------------------------------------- group B
    out = run("new-channel", "--id", "m", "--topic", "membership",
              "--participants", "alpha", "--leader", "lead")
    check("Group B setup: a channel exists with one participant",
          "SEALED_DIVERGENT" in out.stdout, out.stdout + out.stderr)

    before = run("task", "new", "--as", "newcomer", "--channel", "m",
                 "--title", "the work that could not be started")
    check("B1 before the join, a registered agent cannot act in the channel",
          before.returncode != 0, before.stdout + before.stderr)

    usage = run("channel", "--help")
    check("B2 `aim channel --help` lists the new subcommand",
          "add" in usage.stdout and "remove" in usage.stdout, usage.stdout)

    ok = run("channel", "add", "--as", "lead", "--channel", "m", "--agent", "newcomer",
             "--reason", "new arrival needs to work here")
    check("B3 the leader can join a registered agent to an existing channel",
          ok.returncode == 0, ok.stdout + ok.stderr)
    parts = json.loads((root / "channels" / "m" / "manifest.json").read_text())["participants"]
    check("B4 the agent is now a participant", "newcomer" in parts, parts)

    ev = [r for r in ledger("m") if r.get("event") == "channel_member_added"]
    check("B5 the membership change is in the LEDGER, not only in the file",
          len(ev) == 1, json.dumps(ev))
    if ev:
        e = ev[0]
        check("B6 and that event names the leader, the agent, the channel, the time and the reason",
              e.get("agent") == "lead" and e.get("member") == "newcomer"
              and e.get("ts") and e.get("reason") == "new arrival needs to work here"
              and "newcomer" in (e.get("members") or []),
              json.dumps(e))

    after = run("task", "new", "--as", "newcomer", "--channel", "m",
                "--title", "the work that can now be started")
    check("B7 after the join, the same verb that was refused now works",
          after.returncode == 0, after.stdout + after.stderr)

    twice = run("channel", "add", "--as", "lead", "--channel", "m", "--agent", "newcomer")
    parts2 = json.loads((root / "channels" / "m" / "manifest.json").read_text())["participants"]
    check("B8 re-adding is an idempotent recorded no-op, not a duplicate",
          twice.returncode == 0 and parts2.count("newcomer") == 1
          and any(r.get("event") == "channel_member_noop" for r in ledger("m")),
          f"rc={twice.returncode} participants={parts2}")

    n = len(ledger("m"))
    refused = run("channel", "add", "--as", "alpha", "--channel", "m", "--agent", "delta")
    check("B9 a non-leader is refused", refused.returncode != 0, refused.stdout + refused.stderr)
    tail = ledger("m")[n:]
    check("B10 and that refusal is recorded, with cls=barrier and the action it names",
          any(r.get("event") == "refusal" and r.get("agent") == "alpha"
              and r.get("class") == "barrier" and r.get("action") == "channel add"
              for r in tail), json.dumps(tail))
    check("B11 and the refused agent was not added anyway",
          "delta" not in json.loads(
              (root / "channels" / "m" / "manifest.json").read_text())["participants"])

    unknown = run("channel", "add", "--as", "lead", "--channel", "m", "--agent", "ghost")
    check("B12 an unregistered id is refused rather than joined",
          unknown.returncode != 0 and "ghost" not in json.loads(
              (root / "channels" / "m" / "manifest.json").read_text())["participants"],
          unknown.stdout + unknown.stderr)

    # `remove`: the inverse, plus the two states it must refuse to create.
    run("channel", "workspace", "--as", "lead", "--channel", "m",
        "--set", "newcomer=/tmp/somewhere")
    rm = run("channel", "remove", "--as", "lead", "--channel", "m", "--agent", "newcomer",
             "--reason", "left the team")
    m_after = json.loads((root / "channels" / "m" / "manifest.json").read_text())
    check("B13 the leader can remove a participant", rm.returncode == 0, rm.stdout + rm.stderr)
    check("B14 the removed participant is gone from the manifest",
          "newcomer" not in m_after["participants"], m_after["participants"])
    check("B15 its workspace declaration was dropped with it (else it blocks the barrier forever)",
          (m_after.get("workspace") or {}).get("newcomer") is None, m_after.get("workspace"))
    check("B16 the removal is in the ledger",
          any(r.get("event") == "channel_member_removed" and r.get("member") == "newcomer"
              for r in ledger("m")))

    leader = run("channel", "remove", "--as", "lead", "--channel", "m", "--agent", "lead")
    still = json.loads((root / "channels" / "m" / "manifest.json").read_text())
    check("B17 removing the leader is refused (nobody could then move the phase)",
          leader.returncode != 0 and still["leader"] == "lead",
          leader.stdout + leader.stderr)

    unknown_ch = run("channel", "add", "--as", "lead", "--channel", "nope", "--agent", "alpha")
    check("B18 joining a channel that does not exist is refused",
          unknown_ch.returncode != 0, unknown_ch.stdout + unknown_ch.stderr)

    # ---------------------------------------------------------------- group C
    # T-0226, the leader's rule: `the task should not belong to anyone before
    # assigned, anyone (existing, new join guy) could pickup not assigned
    # tasks`. Three mechanically separate claims, each checked against the
    # store rather than against the CLI's own echo: the record carries
    # `owner: ""`, every participant may read the card in every phase, and
    # taking it is an `assigned` event with `from: ""`.
    out = run("new-channel", "--id", "u", "--topic", "unowned work",
              "--participants", "alpha,beta,gamma", "--leader", "lead")
    check("Group C setup: a channel in a divergence phase",
          "SEALED_DIVERGENT" in out.stdout, out.stdout + out.stderr)

    def store_events(ch):
        path = root / "channels" / ch / "tasks.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    run("task", "new", "--as", "alpha", "--channel", "u", "--title", "an offer of work")
    created = [e for e in store_events("u")
               if e.get("event") == "created" and e.get("task") == "T-0001"]
    check('C1 a card created without --owner carries owner "" in the record',
          bool(created) and created[0].get("owner") == "", json.dumps(created)[:300])
    check("C2 and its creator is still on the record, as creator",
          bool(created) and created[0].get("actor") == "alpha", json.dumps(created)[:300])

    # "readable by *every* participant", so every participant is asked, not one
    # proxy: alpha created it, beta and gamma did not, and the clause under test
    # is the one that makes the difference between those two cases disappear.
    for reader in ("alpha", "beta", "gamma"):
        seen = run("task", "list", "--as", reader, "--channel", "u")
        check(f"C3 ({reader}) reads an unowned card in a divergence phase",
              seen.returncode == 0 and "an offer of work" in seen.stdout,
              f"rc={seen.returncode} {seen.stdout}{seen.stderr}")
    counted = run("task", "list", "--as", "gamma", "--channel", "u", "--count-hidden")
    check("C4 and it is withheld from nobody", '"withheld": 0' in counted.stdout,
          counted.stdout + counted.stderr)

    outsider = run("task", "claim", "--as", "delta", "--channel", "u", "--id", "T-0001")
    check("C5 a registered non-participant cannot claim it",
          outsider.returncode != 0 and "participant" in outsider.stderr,
          outsider.stdout + outsider.stderr)

    took = run("task", "claim", "--as", "beta", "--channel", "u", "--id", "T-0001")
    check("C6 a participant can claim it", took.returncode == 0,
          took.stdout + took.stderr)
    assigned = [e for e in store_events("u") if e.get("event") == "assigned"]
    check('C7 the claim is one assigned event naming actor, owner and from ""',
          len(assigned) == 1 and assigned[0].get("actor") == "beta"
          and assigned[0].get("owner") == "beta" and assigned[0].get("from") == "",
          json.dumps(assigned)[:300])

    again = run("task", "claim", "--as", "beta", "--channel", "u", "--id", "T-0001")
    check("C8 claiming your own card is an idempotent no-op, not a second event",
          again.returncode == 0 and len(store_events("u")) == 2,
          f"rc={again.returncode} events={len(store_events('u'))}")

    # `alpha` created the card, so it is readable to alpha even now that beta
    # holds it -- the refusal below is the claim rule and not the barrier. A
    # peer who cannot see the card at all is refused one layer earlier, which
    # C10 shows.
    steal = run("task", "claim", "--as", "alpha", "--channel", "u", "--id", "T-0001")
    check("C9 taking a card somebody holds is refused, and names the verb that moves it",
          steal.returncode != 0 and "assign" in steal.stderr,
          steal.stdout + steal.stderr)

    # The barrier is not weakened by any of this. An *owned* draft keeps the old
    # rule, and the reader who can no longer see it is the evidence that C3 was
    # the unowned exemption firing and not the barrier simply coming down.
    denied = run("task", "list", "--as", "gamma", "--channel", "u")
    check("C10 an owned draft is withheld from a peer participant again",
          denied.returncode != 0 and "an offer of work" not in denied.stdout,
          f"rc={denied.returncode} {denied.stdout}{denied.stderr}")

    # Readable in *every* phase, not only the one it was born in. Its own
    # channel, because the check is about the phase and not about mixing in a
    # withheld draft; COMMIT is a divergence phase that needs no seals to reach.
    run("new-channel", "--id", "v", "--topic", "unowned in every phase",
        "--participants", "alpha,gamma", "--leader", "lead")
    run("task", "new", "--as", "alpha", "--channel", "v", "--title", "readable in any phase")
    before = run("task", "list", "--as", "gamma", "--channel", "v")
    run("advance", "--as", "lead", "--channel", "v", "--to", "COMMIT")
    after = run("task", "list", "--as", "gamma", "--channel", "v")
    check("C11 an unowned card is readable in a divergence phase, before and after the phase moves",
          before.returncode == 0 and after.returncode == 0
          and "readable in any phase" in before.stdout
          and "readable in any phase" in after.stdout,
          f"before={before.stdout!r}{before.stderr!r} after={after.stdout!r}{after.stderr!r}")

    # The claim's decision is the *absence* of a record, so it has to be made
    # again under the lock the append takes. Otherwise both claimants read an
    # empty owner, both append a well-formed claim, and the fold keeps whichever
    # landed last: one card, two claims, nothing erroring anywhere.
    run("new-channel", "--id", "w", "--topic", "two claimants",
        "--participants", "alpha,beta", "--leader", "lead")
    run("task", "new", "--as", "alpha", "--channel", "w", "--title", "exactly one taker")
    procs = [subprocess.Popen([sys.executable, str(AIM), "task", "claim", "--as", who,
                               "--channel", "w", "--id", "T-0001"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env)
             for who in ("alpha", "beta")]
    outs = [proc.communicate() for proc in procs]
    race = [e for e in store_events("w") if e.get("event") == "assigned"]
    check("C12 two racing claims leave exactly one owner and one assigned event",
          sum(1 for proc in procs if proc.returncode == 0) == 1 and len(race) == 1,
          f"rcs={[p.returncode for p in procs]} events={json.dumps(race)[:200]} "
          f"stderr={[o[1].strip()[:60] for o in outs]}")

    # Releasing: the other half of a rule that makes work pickable, because a
    # card taken by a session that then dies must be able to come back.
    no_reason = run("task", "assign", "--as", "beta", "--channel", "u", "--id", "T-0001",
                    "--owner", "")
    check("C13 releasing without a reason is refused",
          no_reason.returncode != 0 and "reason" in no_reason.stderr,
          no_reason.stdout + no_reason.stderr)
    released = run("task", "assign", "--as", "beta", "--channel", "u", "--id", "T-0001",
                   "--owner", "", "--reason", "handing it back")
    last = [e for e in store_events("u") if e.get("event") == "assigned"][-1:]
    check("C14 the release is recorded with its actor, the empty owner and the reason",
          released.returncode == 0 and last and last[0].get("owner") == ""
          and last[0].get("actor") == "beta" and last[0].get("from") == "beta"
          and last[0].get("reason") == "handing it back",
          f"rc={released.returncode} {json.dumps(last)[:300]}")
    back = run("task", "list", "--as", "gamma", "--channel", "u")
    check("C15 and the card is unowned and readable again",
          back.returncode == 0 and "an offer of work" in back.stdout,
          f"rc={back.returncode} {back.stdout}{back.stderr}")

    # ---------------------------------------------------------------- group D
    # T-0231, the smallest piece of the role vocabulary: a seat can *say* what it
    # is. design/13 section 7's first acceptance item reads "its registry entry
    # says what it is (`kind: orchestration`)" and was unsatisfiable -- the
    # register vocabulary was claude|codex|human|other, so the live
    # `codex-orangement` entry says `kind: codex`, a false statement about a seat
    # that dispatches work and writes no code. The interesting half is the
    # second: a kind is a name, not a permission, so the barrier, the membership
    # rule and the human-leader rule must be untouched by it.
    run("register", "--as", "orch", "--kind", "orchestration")
    entry = json.loads((root / "registry.json").read_text())["agents"].get("orch") or {}
    check("D1 `orchestration` is a kind a registry entry can actually say",
          entry.get("kind") == "orchestration", json.dumps(entry))
    joined = run("channel", "add", "--as", "lead", "--channel", "m", "--agent", "orch",
                 "--reason", "the wave's dispatch seat")
    check("D2 and such an agent is joinable to a channel like any other",
          joined.returncode == 0, joined.stdout + joined.stderr)

    adv = run("advance", "--as", "orch", "--channel", "m", "--to", "COMMIT")
    phase = json.loads((root / "channels" / "m" / "manifest.json").read_text())
    check("D3 but it still cannot move a phase: the leader is the human, not the orchestrator",
          adv.returncode != 0 and phase["barrier"]["phase"] == "SEALED_DIVERGENT",
          f"rc={adv.returncode} phase={phase['barrier']['phase']} {adv.stderr[:200]}")
    made = run("new-channel", "--id", "d", "--topic", "roles", "--participants", "alpha",
               "--leader", "orch")
    check("D4 and it cannot be a channel's leader either, for the same reason",
          made.returncode != 0 and "human" in made.stderr, made.stdout + made.stderr)
    owned = run("task", "assign", "--as", "alpha", "--channel", "u", "--id", "T-0001",
                "--owner", "orch")
    check("D5 it can be named the owner of work, which the old vocabulary could not express",
          owned.returncode == 0, owned.stdout + owned.stderr)

print(f"\n{passed}/{passed + failed} checks passed")
print("A5-A7 are the rule: a refusal may not name a remedy that cannot run.")
print("B5/B6 are the one that matters most: membership changes belong in the ledger.")
sys.exit(1 if failed else 0)
