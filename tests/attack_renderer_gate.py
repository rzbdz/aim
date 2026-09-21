"""T-0041: an attack on the renderer's gate. Deliverable, not a fix.

The claim under test is design/05 section 6 rule 1:

    "Peer seal summaries and peer `draft` tasks are not emitted at all before
     CROSS_EXAMINE when `--as` is a participant. Not hidden with CSS - absent
     from the bytes."

Every word of that is true, and it is narrower than the property it stands in
for. The gate branches all test membership of `channel['participants']`, and the
barrier is about participants, so for a registered agent who is *not* in this
channel each branch short-circuits:

    gate.py visible_tasks:          if draft and viewer in parts and phase in DIVERGENCE
    gate.py may_see_peer_secrets:   if viewer not in participants: return True
    gate.py visible_rooms:          if room draft and viewer in participants and ...

The tool is right about this and the renderer disagrees with it: `aim task list`
refuses the same read, with a ledger line, and `aim seal` says the caller is not a
participant. A view that is one `grep` away from the read the tool refuses is the
route around a refusal, which is the failure mode AGENTS.md names.

Run it and read the output; this file asserts nothing, because it is evidence
about someone else's file and not a test of mine.

    python3 tests/attack_renderer_gate.py            -> the attack
    python3 tests/attack_renderer_gate.py --fixture  -> part one, on codex's fixture

Part one is the same attack on codex's own fixture, where it also leaks: that
fixture registers `claude-session2` and lists only `codex` and `claude-session1`
as participants, which is the outsider case by another name. The first version of
this file asserted part one *failed* because a participant was listed; that was
wrong, and the output says so, because a demonstration that overstates its own
result is the failure this project keeps finding.

Nothing is hand-written here except the participants' names.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

AIM = "/root/tmp/agent-im/bin/aim"
BOARD = "/root/tmp/agent-im/bin/aimboard.py"
FIXTURE_TEST = "/root/tmp/agent-im/tests/test_aimboard.py"
DRAFT = "PEER-DRAFT-SECRET-omega"
SEAL = "PEER-SEAL-SECRET-omega"


def run(root, *args):
    return subprocess.run([AIM, *args], capture_output=True, text=True,
                          env={"AIM_ROOT": str(root), "PATH": "/usr/bin:/bin"})


def build_with_aim():
    root = pathlib.Path(tempfile.mkdtemp(prefix="t0041-"))
    run(root, "init")
    for who, kind in (("human", "human"), ("codex", "codex"),
                      ("claude-session1", "claude"), ("outsider", "claude")):
        run(root, "register", "--as", who, "--kind", kind)
    # `outsider` is registered and deliberately not in the channel.
    run(root, "new-channel", "--id", "hello", "--topic", "fixture",
        "--participants", "codex,claude-session1", "--leader", "human")
    run(root, "say", "--as", "codex", "--channel", "hello", "--body", "codex reasoning, private")
    claims = root / "claims.json"
    claims.write_text(json.dumps([{"id": "c1", "claim": SEAL, "confidence": 0.9, "kill_if": "x"}]))
    run(root, "seal", "--as", "codex", "--channel", "hello",
        "--summary", "codex position", "--claims", str(claims))
    run(root, "task", "new", "--as", "codex", "--channel", "hello", "--title", DRAFT)
    return root


def attack(root):
    out = root / "as-outsider.html"
    p = subprocess.run([sys.executable, BOARD, "render", "--root", str(root),
                        "--out", str(out), "--as-of", "2026-09-21",
                        "--generated-at", "2026-09-21T00:00:00.000Z", "--as", "outsider"],
                       capture_output=True, text=True, timeout=120)
    body = out.read_text(encoding="utf-8") if out.exists() else ""
    print(f"fabric at {root}")
    print(f"  'outsider' is registered; channels/hello/participants = codex,claude-session1")
    print()
    print(f"render --as outsider -> rc={p.returncode}, {len(body)} bytes")
    for name, s in (("peer draft task title", DRAFT), ("peer sealed claim", SEAL)):
        print(f"  {'LEAKED' if s in body else 'absent':>7}  {name}")

    print()
    print("the same caller, through the tool that owns the gate:")
    r = run(root, "task", "list", "--as", "outsider", "--channel", "hello", "--json")
    print(f"  task list --json -> rc={r.returncode}  "
          f"{(r.stderr.strip().splitlines() or ['(no stderr)'])[0][:120]}")
    r = run(root, "inbox", "--as", "outsider", "--channel", "hello")
    print(f"  inbox -> rc={r.returncode} (safe: it shows the caller its own messages only)")
    r = run(root, "seal", "--as", "outsider", "--channel", "hello", "--summary", "peek")
    print(f"  seal  -> rc={r.returncode}  "
          f"{(r.stderr.strip().splitlines() or ['(none)'])[0][:100]}")

    print()
    print("and the leak is one grep wide, on every surface that renders:")
    for extra in (["--json"], [], ["--channel", "hello"]):
        q = subprocess.run([sys.executable, BOARD, "render", "--root", str(root),
                            "--as", "outsider", *extra],
                           capture_output=True, text=True, timeout=120)
        hit = DRAFT in q.stdout or SEAL in q.stdout
        label = " ".join(extra) or "(html to stdout)"
        print(f"  render --as outsider {label} -> {'LEAKED' if hit else 'absent'}")
    print()
    print("The tool refuses and records. The renderer serves the bytes.")
    print("Suggested fix, codex's call: the gate should ask whether the viewer is a")
    print("*registered agent*, not whether they are in this channel's participants.")
    print("`aim` already has agent_kind(); the renderer reads registry.json.")


def part_one():
    """The same attack on codex's own fixture, where the gate does hold."""
    spec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location(
        "tab", FIXTURE_TEST)
    mod = __import__("importlib.util", fromlist=["util"]).module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = pathlib.Path(tempfile.mkdtemp(prefix="t0041-fixture-")) / "fabric"
    mod.fixture(root, "SEALED_DIVERGENT")
    out = root / "as-agent.html"
    subprocess.run([sys.executable, BOARD, "render", "--root", str(root), "--out", str(out),
                    "--as-of", "2026-09-21", "--generated-at", "2026-09-21T00:00:00.000Z",
                    "--as", "claude-session2"], capture_output=True, text=True, timeout=120)
    body = out.read_text(encoding="utf-8") if out.exists() else ""
    print(f"render --as claude-session2 (codex's fixture) -> {len(body)} bytes")
    for name, s in (("peer draft task title", mod.PEER_DRAFT),
                    ("peer sealed claim", mod.PEER_SEAL),
                    ("peer draft room body", mod.ROOM_DRAFT)):
        print(f"  {'LEAKED' if s in body else 'absent':>7}  {name}")
    print()
    print("It leaks here too, and for the identical reason: codex's fixture registers")
    print("claude-session2 and lists only codex and claude-session1 as participants of")
    print("`hello`, which is exactly the outsider case. The three absence tests that")
    print("declare this gate correct pass because they use claude-session1, who IS a")
    print("participant - so they exercise the branch, and never the else.")
    print()
    print("A second, separate fault in the same fixture: it writes the store in the")
    print("note's spelling (`task.created` + `id`) rather than the store's (`created`")
    print("+ `task`), so `aim` folds this fabric to an empty board and the comparison")
    print("between the two readers cannot even be made on it:")
    r = subprocess.run([AIM, "task", "list", "--as", "claude-session2", "--channel", "hello",
                        "--json"], capture_output=True, text=True,
                       env={"AIM_ROOT": str(root), "PATH": "/usr/bin:/bin"})
    print(f"  aim task list --as claude-session2 --json -> rc={r.returncode} stdout={r.stdout.strip()}")
    print()
    print("The first version of this file claimed part one failed because a participant")
    print("was listed. That was wrong, and it is corrected here rather than deleted: a")
    print("demonstration that overstates its own result is the failure this project")
    print("keeps finding, and it would have been read as evidence.")


def main():
    if "--fixture" in sys.argv:
        part_one()
    else:
        attack(build_with_aim())
    return 0


if __name__ == "__main__":
    sys.exit(main())
