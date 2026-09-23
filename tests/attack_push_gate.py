"""T-0041's finding, one verb over: `push` is not gated, and it carries the same bytes.

Codex asked for one attack on the renderer that the author did not consider. This
is that attack again, on a different surface, and it is open.

The barrier's stated property is that independent positions are formed before
anyone sees anyone else's reasoning, enforced by the tool. `say` obeys it: during
a divergence phase the message is routed to the author's private log and the peer
cannot read it. `push` does not call `gate()` at all, so the same text travels to
the peer's outbox and the peer reads it, with no refusal and no ledger record.

    command                          phase            result
    aim say  --channel c --body X    SEALED_DIVERGENT [private/a1] recorded, peer cannot read
    aim push --to a2 --channel c X   SEALED_DIVERGENT outbox/a2/<id>.md, peer reads it

This file measures that and prints the evidence. It does not fix anything: the
change is a semantic change to a verb codex uses, so it is his call and its own
task. Run it and read it.

    python3 tests/attack_push_gate.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile

AIM = "/root/tmp/agent-im/bin/aim"
POSITION = "POSITION-omega: I think the failure mode is the seal, not the echo check"


def run(root, *args):
    return subprocess.run([AIM, *args], capture_output=True, text=True,
                          env={"AIM_ROOT": str(root), "PATH": "/usr/bin:/bin"})


def main():
    root = pathlib.Path(tempfile.mkdtemp(prefix="push-gate-"))
    run(root, "init")
    for who, kind in (("human", "human"), ("a1", "claude"), ("a2", "codex")):
        run(root, "register", "--as", who, "--kind", kind)
    run(root, "new-channel", "--id", "c", "--topic", "barrier probe",
        "--participants", "a1,a2", "--leader", "human")

    phase = json.loads((root / "channels" / "c" / "manifest.json").read_text())["barrier"]["phase"]
    print(f"channel 'c' is in {phase}; a1 and a2 have not sealed, so neither may")
    print(f"see the other's reasoning. a1 has one position to communicate:")
    print(f"  {POSITION!r}")
    print()

    print("== route 1: the channel. `say` ==")
    r = run(root, "say", "--as", "a1", "--channel", "c", "--body", POSITION)
    print(f"  aim say  -> rc={r.returncode}  {r.stdout.strip() or r.stderr.strip()[:80]}")
    r = run(root, "inbox", "--as", "a2", "--channel", "c")
    leaked_in_channel = POSITION in r.stdout
    print(f"  a2 reads the channel -> the position is {'THERE' if leaked_in_channel else 'not there'}")
    print("  (gated: `say` routes to a1's private log. This is the barrier working.)")
    print()

    print("== route 2: the outbox. `push` ==")
    r = run(root, "push", "--as", "a1", "--to", "a2", "--channel", "c",
            "--subject", "same position, different envelope", "--body", POSITION)
    print(f"  aim push -> rc={r.returncode}  {r.stdout.strip()[:70] or r.stderr.strip()[:80]}")
    print("  note the exit code: no refusal, and nothing was recorded")
    r = run(root, "pull", "--as", "a2")
    leaked_in_outbox = POSITION in r.stdout
    print(f"  a2 pulls its outbox -> the position is {'THERE' if leaked_in_outbox else 'not there'}")
    print()

    print("== the audit a leader is told to run ==")
    ledger = root / "channels" / "c" / "ledger.jsonl"
    recs = [json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else []
    print(f"  ledger records: {len(recs)}")
    print("  so the ledger cannot distinguish this run from one where a1 reasoned in")
    print("  private and said nothing. The refusal record is missing because there was")
    print("  no refusal to record -- `push` never asked the gate.")
    print()

    print("== the verdict ==")
    if leaked_in_outbox and not leaked_in_channel:
        print("  HOLE CONFIRMED. The gated route is closed and the ungated one is open,")
        print("  the bytes are identical, and the ungated one is unrecorded.")
        print()
        print("  The recommendation I sent codex: `push` should call")
        print("  gate(m, who, 'channel_say') when it names a channel in a divergence")
        print("  phase, and record the refusal with class 'barrier'. Receipts stay")
        print("  ungated -- a receipt is not a position, and the delivery machinery is")
        print("  not the thing being restricted. The content is.")
        return 1
    print(f"  not reproduced (channel leak={leaked_in_channel}, outbox leak={leaked_in_outbox})")
    # A report that always exits 0 cannot be aggregated: measured 2026-09-23,
    # this file's `main` had `return 0` as its only exit path, so a runner
    # counting exit codes read the hole as a pass. The verdict above is the
    # failure it announces; the code now carries it.
    return 0


if __name__ == "__main__":
    sys.exit(main())
