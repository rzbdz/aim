"""T-0253: an exit mechanism, and the boundary of what one can be.

The gap first, because it is why this file exists. A registered id was
permanent: `agent_kind` answers "does this id exist" and never "is anybody still
here", so a session that finished kept its name, its channel memberships and its
voice. Measured before the verb existed: `grep -c depart bin/aim` was 0, and none
of the 26 verbs ended, left or unregistered anything. The leader's own words for
it: "还有啊，那些 claude 他妈都死了，能不能做个退出机制啊".

`aim depart` closes the *orderly* half of that. The half it cannot close is
asserted here too (group E), because a verb that is oversold is worse than no
verb: a session that crashes cannot call anything, so a departed flag has
nothing to say about the case that prompted it.

Group A is the mechanism. Group B is the return path -- both of them, because a
refusal that names a remedy which cannot run is the failure the rest of this
suite is about. Group C is what a departure is *not*: not a de-registration, not
a membership change, not a kind change. Group D is the refusal's own shape.
Group E is the boundary.

Run: python3 tests/test_depart.py
"""
import json
import os
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

    def registry(agent):
        return json.loads((root / "registry.json").read_text())["agents"].get(agent) or {}

    def ledger(ch):
        path = root / "channels" / ch / "ledger.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    run("init")
    for who in ("alpha", "beta", "gamma"):
        run("register", "--as", who, "--kind", "claude", "--session", f"{who} s1")
    run("register", "--as", "lead", "--kind", "human", "--session", "the leader")
    run("new-channel", "--id", "c", "--topic", "departure", "--participants",
        "alpha,beta,gamma", "--leader", "lead")
    run("advance", "--as", "lead", "--channel", "c", "--to", "COMMIT")
    for who in ("alpha", "beta", "gamma"):
        run("seal", "--as", who, "--channel", "c", "--summary", f"position {who}")

    # -------------------------------------------------------------- group A
    # The verb is discoverable and says what it is. A departure nobody can find
    # is not an exit mechanism.
    top = subprocess.run([sys.executable, str(AIM), "--help"], capture_output=True,
                         text=True, env=env, timeout=60)
    check("A1 `depart` is a top-level verb", "depart" in top.stdout, top.stdout[:400])
    dhelp = subprocess.run([sys.executable, str(AIM), "depart", "--help"],
                           capture_output=True, text=True, env=env, timeout=60)
    check("A2 and its help says it is self-declaration, not liveness",
          dhelp.returncode == 0 and "self-declaration" in dhelp.stdout,
          dhelp.stdout + dhelp.stderr)

    # The baseline: this agent is alive, and a verb it can run now, it must not
    # be able to run after.
    before = run("card", "--as", "alpha")
    check("A3 an ordinary read works before the departure", before.returncode == 0,
          before.stdout + before.stderr)

    out = run("depart", "--as", "alpha", "--reason", "work finished")
    check("A4 `depart` succeeds", out.returncode == 0, out.stdout + out.stderr)
    rec = registry("alpha")
    check("A5 the record carries `departed_at`", bool(rec.get("departed_at")),
          json.dumps(rec))
    check("A6 and the session that departed, because two sessions can hold one id",
          bool(rec.get("departed_session")), json.dumps(rec))
    check("A7 and the reason it was given",
          rec.get("departed_reason") == "work finished", json.dumps(rec))
    check("A8 the timestamp is a real one and not a placeholder",
          str(rec.get("departed_at", "")).endswith("Z") and "T" in str(rec.get("departed_at")),
          repr(rec.get("departed_at")))

    # Every verb, not just the one. `card` is a pure read and `task new` is a
    # write, and both take the identity gate.
    after_read = run("card", "--as", "alpha")
    check("A9 a departed session is refused a read it could do a moment ago",
          after_read.returncode == 2, after_read.stdout + after_read.stderr)
    after_write = run("task", "new", "--as", "alpha", "--channel", "c", "--title", "zombie")
    check("A10 and refused a write", after_write.returncode == 2,
          after_write.stdout + after_write.stderr)
    check("A11 the refusal names the departure and its time",
          "departed at" in after_write.stderr and rec["departed_at"][:10] in after_write.stderr,
          after_write.stderr[:300])

    # A departure is per-id. The rest of the fabric keeps working, which is the
    # difference between an exit mechanism and a stop button.
    other = run("card", "--as", "beta")
    check("A12 a peer is unaffected: this is not a global halt", other.returncode == 0,
          other.stdout + other.stderr)
    check("A13 and the departed id is not the leader, so nothing about the barrier moved",
          json.loads((root / "channels" / "c" / "manifest.json").read_text())["barrier"]["phase"]
          == "COMMIT")

    # -------------------------------------------------------------- group B
    # Two remedies, and both have to run: a refusal may not name a command that
    # returns the identical refusal.
    back = run("depart", "--as", "alpha", "--return")
    check("B1 `depart --return` clears it", back.returncode == 0, back.stdout + back.stderr)
    check("B2 and the field is gone, not blanked",
          "departed_at" not in registry("alpha"), json.dumps(registry("alpha")))
    check("B3 the id speaks again", run("card", "--as", "alpha").returncode == 0)
    check("B4 a return with nothing to clear is a no-op that exits 0",
          run("depart", "--as", "beta", "--return").returncode == 0)

    run("depart", "--as", "alpha", "--reason", "second departure")
    stamped = registry("alpha")["departed_at"]
    again = run("depart", "--as", "alpha", "--reason", "third departure")
    check("B5 re-departing is a no-op that exits 0", again.returncode == 0,
          again.stdout + again.stderr)
    check("B6 and does not move the timestamp the refusal prints",
          registry("alpha")["departed_at"] == stamped,
          f"{stamped} -> {registry('alpha')['departed_at']}")

    # The second remedy the refusal names.
    forced = run("register", "--as", "alpha", "--kind", "claude", "--session", "alpha s2",
                 "--force")
    check("B7 the refusal's other remedy -- `register --force` -- runs",
          forced.returncode == 0, forced.stdout + forced.stderr)
    check("B8 and a takeover clears the departure",
          "departed_at" not in registry("alpha"), json.dumps(registry("alpha")))
    check("B9 the taken-over id speaks again", run("card", "--as", "alpha").returncode == 0)

    # -------------------------------------------------------------- group C
    # What a departure is not. Each of these would be a different, worse verb.
    check("C1 it is not a de-registration: the kind is untouched",
          registry("alpha").get("kind") == "claude", json.dumps(registry("alpha")))
    check("C2 and the id is still a participant of its channel",
          "alpha" in json.loads(
              (root / "channels" / "c" / "manifest.json").read_text())["participants"])
    man = json.loads((root / "channels" / "c" / "manifest.json").read_text())
    check("C3 and a departed participant is not silently dropped from the roster count",
          len(man["participants"]) == 3, json.dumps(man["participants"]))

    before_ledger = [r.get("hash") for r in ledger("c")]
    run("depart", "--as", "gamma", "--reason", "leaving")
    run("depart", "--as", "alpha", "--reason", "leaving too")
    check("C4 the manifest is untouched by any of it",
          json.loads((root / "channels" / "c" / "manifest.json").read_text()) == man,
          "the manifest changed across two departures")
    # The ledger is compared before-and-after rather than against a list I wrote
    # by hand: a departure that wrote a `seal` or a `phase` row would be a
    # departure changing the barrier, and the only way to assert "nothing was
    # written" is to have read the file a moment earlier.
    check("C5 and the ledger is byte-identical across both departures",
          [r.get("hash") for r in ledger("c")] == before_ledger,
          f"{before_ledger} -> {[r.get('hash') for r in ledger('c')]}")
    check("C6 so a departure writes no ledger row of its own -- it is a registry "
          "fact, not a channel event",
          not [r for r in ledger("c") if r.get("action") == "depart"],
          json.dumps([r.get("action") for r in ledger("c")]))

    # The history is one list whichever verb moved the record.
    evs = [e["reason"] for e in registry("alpha").get("registration_events", [])]
    check("C7 the departure is in `registration_events` beside the registration",
          evs[:1] == ["initial registration"] and "departure" in evs and "return" in evs
          and "forced takeover" in evs, json.dumps(evs))
    check("C8 and every entry has the same four keys",
          all(set(e) == {"at", "kind", "session", "reason"}
              for e in registry("alpha")["registration_events"]),
          json.dumps(registry("alpha")["registration_events"]))

    # -------------------------------------------------------------- group D
    # The refusal's own shape: recorded, classed, and not confused with the
    # identity refusal next to it.
    #
    # Two refusals from two different verbs, taken on purpose: one is a write
    # (`task new`) and one is a read (`task list`), and both name a channel, so
    # both reach `_record_refusal`. `card` -- the read used in group A -- takes no
    # `--channel` at all, which is why it refuses and records nothing: there is no
    # ledger for `_record_refusal` to write into.
    zombie_read = run("task", "list", "--as", "alpha", "--channel", "c")
    check("D1 a departed session is refused a read on a channel, too",
          zombie_read.returncode == 2, zombie_read.stdout + zombie_read.stderr)

    refusals = [r for r in ledger("c") if r.get("event") == "refusal"]
    ours = [r for r in refusals if "departed at" in r.get("reason", "")]
    check("D2 both refusals reach the ledger", len(ours) == 2,
          json.dumps([r["reason"][:60] for r in refusals]))
    check("D3 they are classed `barrier`, like the identity refusal they sit beside",
          all(r.get("class") == "barrier" for r in ours),
          json.dumps([r.get("class") for r in ours]))
    check("D4 each carries the action that was attempted, not the verb `depart`",
          sorted(r.get("action") for r in ours) == ["task list", "task new"],
          json.dumps([r.get("action") for r in ours]))
    check("D5 and each carries the phase, so a reader can place it",
          all(r.get("phase") == "COMMIT" for r in ours),
          json.dumps([r.get("phase") for r in ours]))
    check("D6 and the actor is recorded, because the id is known -- unlike the "
          "unknown-agent refusal beside it, which has no actor to name",
          all(r.get("agent") == "alpha" for r in ours),
          json.dumps([r.get("agent") for r in ours]))

    unknown = run("card", "--as", "nobody")
    check("D7 an unregistered id still gets the unknown-agent refusal, not this one",
          "unknown agent" in unknown.stderr, unknown.stderr[:200])
    check("D8 and `depart` itself refuses an id that was never registered",
          run("depart", "--as", "nobody").returncode == 2)

    # -------------------------------------------------------------- group E
    # The boundary, asserted so the verb cannot be sold as more than it is.
    run("register", "--as", "delta", "--kind", "claude", "--session", "still running")
    check("E1 an id that never departs carries no departure marker at all",
          "departed_at" not in registry("delta"), json.dumps(registry("delta")))
    check("E2 which is the honest limit: a crashed session writes nothing, so the "
          "store still cannot tell a finished session from an idle one -- `depart` "
          "covers orderly exits only",
          registry("delta").get("departed_at") is None
          and registry("delta").get("session") == "still running")
    a_dep = registry("alpha")
    check("E3 and the record distinguishes departed from live by one field, not by a "
          "deletion: both records keep the same five keys",
          {"id", "kind", "model", "session", "registered_at"} <= set(a_dep)
          and {"id", "kind", "model", "session", "registered_at"} <= set(registry("delta")),
          json.dumps(sorted(a_dep)) + " / " + json.dumps(sorted(registry("delta"))))

print(f"\n{passed}/{passed + failed} checks passed")
print("A9/A10 are the verb: a departed session is refused on every path, not one.")
print("B1-B9 are the remedy rule: both remedies a refusal names must actually run.")
print("E2 is the boundary: self-declaration cannot cover a crash, and says so.")
sys.exit(1 if failed else 0)
