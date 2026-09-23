"""Which verbs can carry a position to a peer while the barrier is closed?

Two holes of one shape were found by hand before this file existed:

  tests/attack_push_gate.py     `push` delivers straight to a peer's outbox
  `request-advance --reason`    writes free text into the channel's public log,
                                hidden now, readable by the peer at CROSS_EXAMINE

Both are the same defect: a verb carries free text into peer-visible state and
never asks `gate()`. Finding them one at a time means finding them forever, so
this file asks structurally instead of anecdotally: for every verb that can carry
text, put a known string in it during SEALED_DIVERGENT and make every move a peer
is entitled to make, now and after the phase opens.

Three mistakes this file was written to stop making, each of which either cost
codex a signal or hid this file's own result:

  * a probe must run against a fabric that exists. The first version built
    nothing, so every verb failed with "unknown channel", `gate()` was never
    reached, and the refusal it reported on was a refusal to open a nonexistent
    file. That is a pass for the wrong reason, and the fix is `fabric()` below.
  * "the peer cannot read it" must be asked as the peer, on every surface the
    peer has. `inbox --as a1` proves nothing about a2 — twice already a probe in
    this repo was green because it looked at the wrong viewer.
  * `open_the_barrier` must refuse to return a phase it did not reach. It first
    advanced into SYNTHESIS with no synthesizer; that refusal is silent to a
    caller, the phase sat at COMMIT, and every `later` column read False — so the
    one hole the column exists to catch was invisible in its own output. It now
    asserts the phase it achieved. An instrument that cannot fail its own reading
    is not an instrument.

It is a *measure*, not a test with a verdict, because for some verbs the answer
is legitimately yes (`seal` publishes a digest the whole design rests on; `task
publish` is the deliberate act the gate exists to permit). The output names which
is which so the decision is made against a table rather than against a memory.

    python3 tests/attack_gate_sweep.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile

AIM = "/root/tmp/agent-im/bin/aim"
BOARD = "/root/tmp/agent-im/bin/aimboard.py"
SECRET = "POSITION-omega-the-echo-check-is-the-real-failure-mode"
# The claims format, as `aim seal --claims` documents it: an object needs
# `id`, `claim` and `kill_if` (bin/aim's `check_claims_file`). This fixture
# used `text`/`falsifier`, which nothing reads -- it was accepted silently
# until T-0247 gave the verb a guard, and then this file's seal probe failed
# at open_the_barrier with "seal a1 failed". The keys were always wrong for
# the documented format; they were only invisible.
CLAIMS = [{"id": "c1", "claim": "t", "kill_if": "f", "confidence": 0.5}]


def run(root, *args, stdin_text=None):
    return subprocess.run([AIM, *args], capture_output=True, text=True,
                          input=stdin_text, timeout=60,
                          env={"AIM_ROOT": str(root), "PATH": "/usr/bin:/bin"})


def fabric(registered=("human", "a1", "a2")):
    """A real fabric. Nothing in this file may probe a root that does not exist."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="gate-sweep-"))
    assert run(root, "init").returncode == 0, "init failed"
    for who in registered:
        assert run(root, "register", "--as", who,
                   "--kind", "human" if who == "human" else "claude").returncode == 0, who
    assert run(root, "new-channel", "--id", "c", "--topic", "sweep",
               "--participants", "a1,a2", "--leader", "human").returncode == 0
    return root


def peer_reads(root):
    """Every surface a2 is offered, asked as a2. Returns {surface: True if it sees it}."""
    seen = {}
    seen["channel (inbox as a2)"] = SECRET in run(
        root, "inbox", "--as", "a2", "--channel", "c").stdout
    seen["outbox (pull as a2)"] = SECRET in run(root, "pull", "--as", "a2").stdout
    seen["board (task list as a2)"] = SECRET in run(
        root, "task", "list", "--as", "a2", "--channel", "c").stdout
    b = subprocess.run([sys.executable, BOARD, "render", "--root", str(root),
                        "--as", "a2", "--generated-at", "2026-09-21T00:00:00.000Z"],
                       capture_output=True, text=True, timeout=180)
    seen["dashboard (aimboard as a2)"] = SECRET in b.stdout
    # the leader is not a participant; the leader must not see it either
    seen["leader (inbox as human)"] = SECRET in run(
        root, "inbox", "--as", "human", "--channel", "c").stdout
    return seen


def open_the_barrier(root):
    """Both seal, the leader walks the channel to CROSS_EXAMINE. The peer may
    then read everything the channel was ever holding. A verb that hides its text
    only until this moment has not hidden it; it has delayed it.

    This function refuses to return a phase it did not reach. The first version
    advanced into SYNTHESIS with no synthesizer, that refusal is silent to a
    caller, and the phase sat at COMMIT — so every `later` column in the run was
    False and the one hole the column exists to catch was invisible. An
    instrument that cannot fail its own reading is not an instrument."""
    cl = root / "claims.json"
    cl.write_text(json.dumps(CLAIMS))
    for a in ("a1", "a2"):
        assert run(root, "seal", "--as", a, "--channel", "c", "--summary", f"s-{a}",
                   "--claims", str(cl)).returncode == 0, f"seal {a} failed"
    assert run(root, "register", "--as", "syn", "--kind", "other").returncode == 0
    steps = [("COMMIT", []), ("SYNTHESIS", ["--synthesizer", "syn"]),
             ("CROSS_EXAMINE", [])]
    for to, extra in steps:
        r = run(root, "advance", "--as", "human", "--channel", "c", "--to", to, *extra)
        assert r.returncode == 0, f"advance -> {to} failed: {r.stderr.strip()[:120]}"
    phase = json.loads((root / "channels" / "c" / "manifest.json").read_text())
    phase = phase["barrier"]["phase"]
    assert phase == "CROSS_EXAMINE", f"barrier did not open, phase is {phase}"
    return run(root, "inbox", "--as", "a2", "--channel", "c").stdout


def lines(p):
    return len(p.read_text().splitlines()) if p.exists() else 0


def probe(name, argv, registered=("human", "a1", "a2")):
    root = fabric(registered)
    ch = root / "channels" / "c"
    (root / "claims.json").write_text(json.dumps(CLAIMS))
    argv = [str(root / "claims.json") if a == "@claims" else a for a in argv]
    before = (lines(ch / "ledger.jsonl"), lines(ch / "tasks.jsonl"))
    r = run(root, *argv)
    now = peer_reads(root)
    after = (lines(ch / "ledger.jsonl"), lines(ch / "tasks.jsonl"))
    later = SECRET in open_the_barrier(root)
    return {
        "verb": name, "rc": r.returncode,
        "refused": r.returncode != 0,
        "ledger": after[0] - before[0],
        "store": after[1] - before[1],
        "now": [k for k, v in now.items() if v],
        "later": later,
        "err": (r.stderr.strip().splitlines() or [""])[0][:64],
    }


def main():
    P = [
        probe("say --body", ["say", "--as", "a1", "--channel", "c", "--body", SECRET]),
        probe("push --body", ["push", "--as", "a1", "--to", "a2", "--channel", "c",
                              "--subject", "s", "--body", SECRET]),
        probe("request-advance --reason",
              ["request-advance", "--as", "a1", "--channel", "c", "--to", "COMMIT",
               "--reason", SECRET]),
        probe("task new --title", ["task", "new", "--as", "a1", "--channel", "c",
                                   "--title", SECRET]),
        probe("task comment --body", ["task", "comment", "--as", "a1", "--channel", "c",
                                      "--id", "T-0001", "--body", SECRET]),
        probe("reveal --body", ["reveal", "--as", "a1", "--channel", "c",
                                "--claim-id", "c1", "--body", SECRET]),
        probe("seal --summary", ["seal", "--as", "a1", "--channel", "c",
                                 "--summary", SECRET, "--claims", "@claims"]),
        probe("nudge", ["nudge", "--channel", "c", "--peer", "a2"]),
        # register takes an id, not free text; the secret goes in --session, which
        # is metadata an agent picks. It is in the sweep because "which fields carry
        # text" is the question, and a field nobody thought of is how this starts.
        probe("register --session", ["register", "--as", "a1", "--kind", "claude",
                                     "--session", SECRET]),
        probe("init (control: no text at all)", ["status", "--channel", "c"]),
    ]

    print(f"channel 'c' is SEALED_DIVERGENT for every probe; a1 writes, a2 and the")
    print(f"leader try to read it. secret = {SECRET!r}")
    print()
    print(f"  {'verb':<28} {'rc':>3} {'ledger':>7} {'store':>6}  readable by a peer")
    print("  " + "-" * 100)
    for p in P:
        where = ", ".join(p["now"]) if p["now"] else ("-- nothing now --" if not p["later"]
                                                      else "-- nothing until CROSS_EXAMINE --")
        print(f"  {p['verb']:<28} {p['rc']:>3} {p['ledger']:>7} {p['store']:>6}  {where}")

    print()
    print("  ledger = refusal/barrier lines appended to channels/c/ledger.jsonl.")
    print("  store  = channels/c/tasks.jsonl lines. A barrier event that lands only")
    print("           in the store is invisible to an audit that reads the ledger,")
    print("           which is the audit README section 3 tells the leader to run.")
    print()

    leaks = [p for p in P if (p["now"] or p["later"]) and not p["refused"]]
    if not leaks:
        print("no ungated leak found")
        return 0

    print("TEXT THAT REACHES A PEER WITH NO REFUSAL:")
    for p in leaks:
        when = "at once" if p["now"] else "when the phase opens"
        rec = f"{p['ledger']} ledger line(s)" if p["ledger"] else "NOTHING in the ledger"
        print(f"  {p['verb']:<28} {when:<22} {rec}")
    print()
    print("Some of these are correct on purpose: `seal` publishes a digest the design")
    print("rests on, and `task publish` is the deliberate act the gate exists to")
    print("permit. The unjustified ones are those whose *text* is a position:")
    print("  push --body              the outbox is not a channel, so no phase reaches it")
    print("  request-advance --reason the reason lands in the PUBLIC log, not the")
    print("                           requester's private one, so the barrier hides it")
    print("                           from the peer and then hands it over")
    return 0


if __name__ == "__main__":
    sys.exit(main())
