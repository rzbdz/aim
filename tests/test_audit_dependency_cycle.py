"""T-0221: a dependency cycle is accepted, is unclosable, and `--force` leaves no trace.

This file is a **characterization test**: it pins the behaviour of the working
tree as it is, defect included, so that the fix is visible as a deliberate flip
of a named row rather than as a shrug. Every `DEFECT:` row below is a statement
about the tool today and is asserted to be *true*; when the fix lands those rows
go red, and the red row names exactly what changed. Do not "repair" this file by
weakening the assertion -- update it to assert the fixed behaviour and keep the
old row in the docstring as the history, the way `tests/test_room_gate.py` keeps
its three-row table.

The defect, measured on a throwaway AIM_ROOT with two cards created straight
into `review` so the only obstacle to `done` is the dependency:

    aim task link --id T-0001 --blocked-by T-0002   -> rc 0
    aim task link --id T-0002 --blocked-by T-0001   -> rc 0   (the cycle, accepted)

    aim task move --id T-0001 --to done             -> REFUSED: blocked by T-0002
    aim task move --id T-0002 --to done             -> REFUSED: blocked by T-0001

`cmd_task_link` (bin/aim:1931) checks two things -- that the named task exists
and that it is not the task itself -- and nothing else. `cmd_task_move`
(bin/aim:1823) opens the block gate with

    open_blockers = [b for b in t["blocked_by"] if board.get(b, {}).get("status") != "done"]

so a cycle is two cards each waiting on the other, and neither can ever reach
`done`. The stated recourse is `--force`, and the finding is what the override
costs: the `moved` event written for a forced move carries no `forced` field and
no reason, and the ledger receives nothing at all. Compare `task publish`, which
got its own `task_published_during_divergence` event class for the analogous
deliberate breach -- so "how did this reach done with an open blocker" is
unanswerable from either chain, and the two cards it deadlocked are the reason
somebody asked.

Each row shows one blocker id, so nothing on the board says the two block each
other (audit `14-independent-audit-raw.md` F-a).

What the fix must make true, for the reader who comes here after it lands:

  * `link` refuses an edge that would close a cycle (so the first `rc 0` row
    becomes rc 2, and the next two rows never happen);
  * a forced `move` writes the actors, the blocker statuses it overrode and a
    reason somewhere a reader can find them (ledger or store);
  * the actor rule of T-0243 is separate work -- this file does not assert it.

Run: python3 tests/test_audit_dependency_cycle.py     (exit code = number of failures)
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
        return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                              capture_output=True, text=True, env=env, timeout=60)

    ch = root / "channels" / "c"
    tasks = ch / "tasks.jsonl"
    ledger = ch / "ledger.jsonl"

    def events():
        if not tasks.exists():
            return []
        return [json.loads(l) for l in tasks.read_text(encoding="utf-8").splitlines() if l.strip()]

    def refusals():
        if not ledger.exists():
            return []
        return [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()
                if l.strip() and json.loads(l).get("event") == "refusal"]

    # ---------------------------------------------------------------- fixture
    run("init")
    for who, kind in (("alpha", "claude"), ("beta", "codex"), ("human", "human")):
        run("register", "--as", who, "--kind", kind, "--session", "cycle audit")
    opened = run("new-channel", "--id", "c", "--topic", "dependency cycle",
                 "--participants", "alpha,beta", "--leader", "human")
    check("the fixture channel opened", "SEALED_DIVERGENT" in opened.stdout,
          opened.stdout + opened.stderr)

    # `review` (not `doing`) so `done` is a legal transition and the only thing
    # between the card and `done` is the dependency. Otherwise the transition
    # refusal fires first and the row would not be about the cycle at all.
    for title in ("card A", "card B"):
        made = run("task", "new", "--as", "alpha", "--channel", "c",
                   "--title", title, "--status", "review")
        check(f"fixture: {title} created in review", made.returncode == 0,
              made.stdout + made.stderr)

    # ------------------------------------------------- the cycle is accepted
    print("\n== 1. the cycle ==")
    refusals_before = len(refusals())
    a_on_b = run("task", "link", "--as", "alpha", "--channel", "c",
                 "--id", "T-0001", "--blocked-by", "T-0002")
    check("a plain dependency edge is accepted",
          a_on_b.returncode == 0 and "T-0001 blocked_by T-0002" in a_on_b.stdout,
          f"rc={a_on_b.returncode} {a_on_b.stdout}{a_on_b.stderr}")

    b_on_a = run("task", "link", "--as", "alpha", "--channel", "c",
                 "--id", "T-0002", "--blocked-by", "T-0001")
    check("DEFECT: the closing edge of a cycle is accepted, so A and B each block the other",
          b_on_a.returncode == 0 and "T-0002 blocked_by T-0001" in b_on_a.stdout,
          f"rc={b_on_a.returncode} {b_on_a.stdout}{b_on_a.stderr}")
    check("DEFECT: and the cycle is not recorded as a refusal anywhere",
          len(refusals()) == refusals_before,
          f"{len(refusals()) - refusals_before} refusal row(s) written by the cycle")

    links = [e for e in events() if e.get("event") == "linked"]
    check("the two `linked` events land in the store as ordinary edges",
          {e.get("task"): e.get("blocked_by") for e in links}
          == {"T-0001": "T-0002", "T-0002": "T-0001"},
          json.dumps(links, ensure_ascii=False)[:300])
    check("DEFECT: neither `linked` event carries a cycle check's verdict",
          all("cycle" not in json.dumps(e).lower() for e in links),
          json.dumps(links, ensure_ascii=False)[:200])

    # ------------------------------------------------- both cards unclosable
    print("\n== 2. neither card can be closed ==")
    for tid, other in (("T-0001", "T-0002"), ("T-0002", "T-0001")):
        done = run("task", "move", "--as", "alpha", "--channel", "c",
                   "--id", tid, "--to", "done")
        check(f"DEFECT: {tid} cannot reach done while {other} is open, so the cycle "
              f"deadlocks the pair",
              done.returncode == 2 and f"blocked by {other}" in (done.stdout + done.stderr),
              f"rc={done.returncode} {(done.stdout + done.stderr).strip()[:160]}")
        check(f"{tid}'s refusal names no escape hatch, so the override is undiscoverable "
              f"from the refusal",
              "--force" not in (done.stdout + done.stderr),
              (done.stdout + done.stderr).strip()[:200])

    # ------------------------------------------- --force closes it, silently
    print("\n== 3. --force is the only way out, and it writes nothing ==")
    ledger_before = len(refusals())
    forced = run("task", "move", "--as", "alpha", "--channel", "c",
                 "--id", "T-0001", "--to", "done", "--force")
    check("--force closes T-0001 against an open blocker",
          forced.returncode == 0 and "T-0001: review -> done" in forced.stdout,
          f"rc={forced.returncode} {forced.stdout}{forced.stderr}")

    forced_ev = [e for e in events()
                 if e.get("event") == "moved" and e.get("task") == "T-0001"
                 and e.get("to") == "done"]
    check("the forced move is the one `moved` event, so the store saw the move",
          len(forced_ev) == 1, json.dumps(forced_ev, ensure_ascii=False)[:200])
    if forced_ev:
        ev = forced_ev[0]
        check("DEFECT: the moved event records no `forced` field, so the store cannot "
              "tell an override from an ordinary move",
              "forced" not in ev, f"keys={sorted(ev.keys())}")
        check("DEFECT: the moved event records no reason and no blocker statuses, so the "
              "override cannot be reconstructed",
              ev.get("reason") == "" and "overrode" not in ev and "blockers" not in ev,
              json.dumps(ev, ensure_ascii=False)[:220])
    check("DEFECT: the forced move writes no ledger row at all -- there is no "
          "`task_done_despite_blocker` class for it",
          len(refusals()) == ledger_before,
          f"{len(refusals()) - ledger_before} refusal row(s) added by the forced move")

    # The consequence the cycle was supposed to prevent: the pair only closes
    # because the override it was written to refuse was used.
    second = run("task", "move", "--as", "alpha", "--channel", "c",
                 "--id", "T-0002", "--to", "done")
    check("once one side is forced through, the other side closes with no override at all",
          second.returncode == 0,
          f"rc={second.returncode} {(second.stdout + second.stderr).strip()[:160]}")

    # ----------------------------------------------------------------- table
    def status(tid):
        for e in reversed(events()):
            if e.get("task") == tid and e.get("to"):
                return e["to"]
        return "?"

    print("\n  what the cycle produced, row by row")
    print(f"    {'step':<46} {'rc':>3}  what it wrote")
    rows = [
        ("link T-0001 blocked_by T-0002", a_on_b.returncode, "a linked event, no check"),
        ("link T-0002 blocked_by T-0001  <- the cycle", b_on_a.returncode,
         "a linked event, no refusal"),
        ("move T-0001 -> done (blocked)", 2, "a refusal, class=form, no --force hint"),
        ("move T-0002 -> done (blocked)", 2, "a refusal, class=form, no --force hint"),
        ("move T-0001 -> done --force", forced.returncode,
         "a moved event with no forced/reason field; ledger untouched"),
        ("move T-0002 -> done (after the override)", second.returncode,
         "the other half of the cycle, closed by the override"),
    ]
    for label, rc, wrote in rows:
        print(f"    {label:<46} {rc:>3}  {wrote}")
    print(f"    final statuses: T-0001={status('T-0001')} T-0002={status('T-0002')}")

print(f"\n{passed}/{passed + failed} checks passed")
print("Every DEFECT row above is asserted true against the working tree. This file is a")
print("characterization test, in the shape tests/test_room_gate.py uses: it passes while")
print("the defect is present and goes red when the fix lands, naming what changed.")
print("The fix must make `link` refuse a closing edge, and must leave a forced move's")
print("actor, reason and overridden blocker statuses where a reader can find them.")
sys.exit(1 if failed else 0)
