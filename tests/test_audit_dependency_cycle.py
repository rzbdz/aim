"""T-0221, after the fix: the closing edge is refused on the record, and `--force` is legible.

This file is the *retirement* of a characterization test. Until the fix landed it
asserted the defect itself: that `aim task link` accepted an edge closing a
dependency cycle, that the two cards in the cycle could therefore never reach
`done`, and that `--force` -- the only way out -- wrote a `moved` event
indistinguishable from an ordinary move while the ledger received nothing at all.
It passed while that was true, and it went red on the rows that described the
fixed behaviour as if it were the defect's absence (the last recorded run was
11/18). The fix is in `cmd_task_link` (bin/aim:2318): it walks `blocked_by` from
the named blocker looking for the card, refuses the edge that closes a cycle with
`cls="form"` unless `--force`, and writes the verdict onto the event
(`cycle_check: "clean" | "forced"`, plus `forced: true` and `cycle: <route>`).

So the file now asserts what the fix makes true, and goes red if any of it
regresses. The old row-by-row table is kept here, because the flip is the
evidence that the fix is the fix and not a shrug -- and because
`tests/test_room_gate.py` keeps its history the same way:

    step                                        before the fix        now
    link T-0001 blocked_by T-0002               rc 0, no check        rc 0, cycle_check=clean
    link T-0002 blocked_by T-0001 (the cycle)   rc 0, ACCEPTED        rc 2, refusal in the ledger
    move T-0001 -> done (blocked)               rc 2, no --force hint rc 2, names --force + class
    move T-0001 -> done --force                 rc 0, nothing on the  rc 0, forced=true,
                                                move; ledger empty   overrode=[blocker:T-0002];
                                                                     ledger still empty
    move T-0002 -> done (after the override)    rc 0, no override    rc 0, no override, and the
                                                recorded             store says who paid

What this file measures now, i.e. what must stay true:

  * `link` refuses an edge that would close a cycle, names both cards *and* the
    route between them, and the refusal is a ledger row carrying a class -- the
    barrier's claim that a refusal is auditable is only falsifiable if the row
    is there (`_record_refusal`, bin/aim:260);
  * the verdict travels on the event, so a reader holding the store alone can
    tell an edge that was checked from one written by a build that did not
    check -- which is the whole difference between the defect and the fix;
  * `--force` on the edge writes the edge *and* the cycle it closed;
  * a forced `move` over an open blocker writes `forced: true`, the reason, and
    `overrode: ["blocker:<id>"]`, and a `--force` that overrode no rule is
    marked `force_unused` instead -- so "the flag was spent" became a fact about
    the event rather than about the caller's nerves;
  * the cycle check terminates on a graph that already contains a cycle: a
    checker that hangs on a cycle cannot report the fault it exists to find.

Two measured boundaries are pinned here deliberately, and neither is part of the
fix. Both are named in the row rather than smoothed over:

  * BOUNDARY: the override is on the *store's* record, not the ledger's. A forced
    move still writes no ledger row -- the ledger is where refusals live, and a
    forced move is not a refusal. See the row's comment for what would change it.
  * DEFECT (surviving): the check is about the *requested edge*, not about the
    card. An edge into a card whose dependency closure already contains a cycle
    is admitted with `cycle_check: "clean"`, and nothing on the board says that
    card can never close either. That is the same F-a complaint one hop out, and
    it is the one row here that is still asserting a defect.

What this file does not assert: the actor rules of T-0243 (`review -> done` by
the card's own owner). They are separate work, and `move` records their override
the same way.

Run: python3 tests/test_audit_dependency_cycle.py     (exit code = number of failures)
"""
import json
import os
import subprocess
import sys
import tempfile
import time
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

    def ledger_rows():
        if not ledger.exists():
            return []
        return [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]

    def refusals():
        return [r for r in ledger_rows() if r.get("event") == "refusal"]

    def linked(task=None):
        return [e for e in events() if e.get("event") == "linked"
                and (task is None or e.get("task") == task)]

    def moved(task=None):
        return [e for e in events() if e.get("event") == "moved"
                and (task is None or e.get("task") == task)]

    def out_of(res):
        return res.stdout + res.stderr

    # ---------------------------------------------------------------- fixture
    run("init")
    for who, kind in (("alpha", "claude"), ("beta", "codex"), ("human", "human")):
        run("register", "--as", who, "--kind", kind, "--session", "cycle audit")
    opened = run("new-channel", "--id", "c", "--topic", "dependency cycle",
                 "--participants", "alpha,beta", "--leader", "human")
    check("the fixture channel opened", "SEALED_DIVERGENT" in opened.stdout,
          opened.stdout + opened.stderr)

    # `review` (not `doing`) so `done` is a legal transition and the only thing
    # between a card and `done` is the dependency. Otherwise the transition
    # refusal fires first and the row would not be about the cycle at all.
    #
    # `--accept` on every card is a fixture line for the same reason and it is
    # T-0251's clause: `review -> done` now refuses a card with no acceptance
    # condition, so a suite about *cycles* would be refused by a rule it is not
    # measuring. The closes below carry `--evidence` for the same reason -- the
    # unforced close of `B` in section 6 and of `Q` in section 7 are here to show
    # the blocker rule and the cycle rule, not the accept gate.
    cards = ["card A", "card B", "card C", "card D",
             "card P", "card Q", "card V", "card W"]
    for title in cards:
        made = run("task", "new", "--as", "alpha", "--channel", "c",
                   "--title", title, "--status", "review",
                   "--accept", f"the cycle audit holds for {title}")
        check(f"fixture: {title} created in review", made.returncode == 0,
              out_of(made))
    A, B, C, D, P, Q, V, W = (f"T-{i:04d}" for i in range(1, 9))

    # ------------------------------------------- 1. the edge a reader can trust
    print("\n== 1. a plain edge, and the verdict the writer reached ==")
    a_on_b = run("task", "link", "--as", "alpha", "--channel", "c",
                 "--id", A, "--blocked-by", B)
    check("FIX: a plain dependency edge is accepted",
          a_on_b.returncode == 0 and f"{A} blocked_by {B}" in a_on_b.stdout,
          f"rc={a_on_b.returncode} {out_of(a_on_b)}")
    clean_edge = linked(A)[0] if linked(A) else {}
    check("FIX: the `linked` event states the verdict it was written with -- "
          "cycle_check=clean -- so the store distinguishes a checked edge from an "
          "unchecked one",
          clean_edge.get("cycle_check") == "clean", json.dumps(clean_edge)[:220])
    check("FIX: an edge that closes nothing carries no override: no `forced`, no `cycle`",
          "forced" not in clean_edge and "cycle" not in clean_edge,
          f"keys={sorted(clean_edge.keys())}")
    check("FIX: and the clean link does not claim to have forced anything",
          "FORCED" not in a_on_b.stdout, a_on_b.stdout)

    # --------------------------------- 2. the closing edge is refused, on record
    print("\n== 2. the closing edge ==")
    refusals_before = len(refusals())
    b_on_a = run("task", "link", "--as", "alpha", "--channel", "c",
                 "--id", B, "--blocked-by", A)
    check("FIX: the edge that would close the cycle is refused (rc 2)",
          b_on_a.returncode == 2,
          f"rc={b_on_a.returncode} {out_of(b_on_a).strip()[:200]}")
    check("FIX: the refusal names both cards *and* the route between them "
          f"({B} -> {A} -> {B})",
          f"{B} -> {A} -> {B}" in out_of(b_on_a), out_of(b_on_a).strip()[:300])
    check("FIX: the refused edge is not in the store",
          linked(B) == [], json.dumps(linked(B))[:200])
    board = run("task", "list", "--as", "alpha", "--channel", "c")
    b_row = [l for l in board.stdout.splitlines() if l.startswith(B)]
    check("FIX: and the fold agrees -- B carries no blocker after the refusal",
          bool(b_row) and "blocked_by=" not in b_row[0],
          f"{b_row} | {out_of(board).strip()[:120]}")
    wrote = refusals()[refusals_before:]
    check("FIX: the refusal is a ledger row with a class, so the ledger alone "
          "answers 'did anybody try'",
          len(wrote) == 1 and wrote[0].get("class") == "form"
          and wrote[0].get("action") == "task link",
          json.dumps(wrote, ensure_ascii=False)[:300])
    check("FIX: and that ledger row carries the route, not just the two ids",
          bool(wrote) and f"{B} -> {A} -> {B}" in wrote[0].get("reason", ""),
          json.dumps(wrote, ensure_ascii=False)[:300])

    # ------------------------- 3. longer cycles and the length-one cycle
    print("\n== 3. longer cycles, and the self edge ==")
    run("task", "link", "--as", "alpha", "--channel", "c", "--id", C, "--blocked-by", A)
    run("task", "link", "--as", "alpha", "--channel", "c", "--id", D, "--blocked-by", C)
    three = run("task", "link", "--as", "alpha", "--channel", "c",
                "--id", A, "--blocked-by", D)
    check(f"FIX: a three-card cycle is refused too, naming the whole route "
          f"({A} -> {D} -> {C} -> {A})",
          three.returncode == 2 and f"{A} -> {D} -> {C} -> {A}" in out_of(three),
          f"rc={three.returncode} {out_of(three).strip()[:280]}")
    self_edge = run("task", "link", "--as", "alpha", "--channel", "c",
                    "--id", A, "--blocked-by", A)
    check("FIX: the length-one cycle (a card blocked by itself) is refused, with "
          "its own message",
          self_edge.returncode == 2 and "cannot block itself" in out_of(self_edge),
          f"rc={self_edge.returncode} {out_of(self_edge).strip()[:160]}")
    check("FIX: a self edge is not accepted even with --force -- the refusal is a "
          "statement about the request, not about the flag",
          run("task", "link", "--as", "alpha", "--channel", "c",
              "--id", A, "--blocked-by", A, "--force").returncode == 2,
          "a --force'd self edge was accepted")

    # ---------------------------- 4. --force writes the cycle onto the edge
    print("\n== 4. `--force` on the edge writes the edge *and* the cycle ==")
    forced_link = run("task", "link", "--as", "alpha", "--channel", "c",
                      "--id", B, "--blocked-by", A, "--force")
    check("FIX: --force writes the closing edge",
          forced_link.returncode == 0 and f"{B} blocked_by {A}" in forced_link.stdout,
          f"rc={forced_link.returncode} {out_of(forced_link)}")
    check("FIX: --force says out loud what it did, naming the route",
          "FORCED" in forced_link.stdout and f"{B} -> {A} -> {B}" in forced_link.stdout,
          forced_link.stdout)
    forced_edge = linked(B)[0] if linked(B) else {}
    check("FIX: the forced `linked` event carries cycle_check=forced, forced=true "
          "and the route it closed",
          forced_edge.get("cycle_check") == "forced"
          and forced_edge.get("forced") is True
          and forced_edge.get("cycle") == f"{B} -> {A} -> {B}",
          json.dumps(forced_edge)[:300])
    check("FIX: a --force that closes nothing is still a clean edge, not a forced "
          "one -- the flag does not change the verdict",
          all(e.get("cycle_check") == "clean" for e in linked(C) + linked(D)),
          json.dumps(linked(C) + linked(D))[:240])

    # The graph now contains a cycle by design: A <-> B. The walker runs on
    # every later link, so this is where "a checker that cannot report a cycle
    # must at least not hang on one" is measured, on the real graph rather than
    # on a unit-test fiction.
    started = time.monotonic()
    v_on_d = run("task", "link", "--as", "alpha", "--channel", "c",
                 "--id", V, "--blocked-by", D)
    walker_secs = time.monotonic() - started
    check("FIX: the cycle check terminates on a graph that already contains a "
          "forced cycle (no hang, no timeout)",
          v_on_d.returncode == 0 and walker_secs < 10,
          f"rc={v_on_d.returncode} after {walker_secs:.1f}s: {out_of(v_on_d).strip()[:200]}")
    d_on_v = run("task", "link", "--as", "alpha", "--channel", "c",
                 "--id", D, "--blocked-by", V)
    check("FIX: and the reciprocal of that edge is refused, route named in full",
          d_on_v.returncode == 2 and f"{D} -> {V} -> {D}" in out_of(d_on_v),
          f"rc={d_on_v.returncode} {out_of(d_on_v).strip()[:240]}")
    v_edge = linked(V)[0] if linked(V) else {}
    check("DEFECT (surviving): an edge into a card whose dependency closure already "
          "contains a cycle is admitted as `clean` -- the check answers \"does this "
          "edge close a cycle\" (it does not) and not \"can this card ever close\" "
          "(it cannot, while A and B are open), and no board row says so",
          v_on_d.returncode == 0 and v_edge.get("cycle_check") == "clean"
          and "cycle" not in v_edge,
          f"rc={v_on_d.returncode} {json.dumps(v_edge)[:240]}\n"
          f"        chain at this point: {V} blocked_by {D} blocked_by {C} "
          f"blocked_by {A} <-> {B}; {A} and {B} cannot close, so neither can {D} "
          f"or {V}, and {V}'s event says cycle_check=clean")

    # -------------------------------- 5. the forced move, and what it records
    print("\n== 5. the forced move ==")
    blocked = run("task", "move", "--as", "alpha", "--channel", "c",
                  "--id", A, "--to", "done")
    check("FIX: an unforced `done` over an open blocker is still refused (rc 2)",
          blocked.returncode == 2,
          f"rc={blocked.returncode} {out_of(blocked).strip()[:200]}")
    check("FIX: the refusal names the escape hatch, so the override is discoverable "
          "from the refusal itself",
          "--force" in out_of(blocked), out_of(blocked).strip()[:200])
    check("FIX: and it no longer names a rule this verb does not have (T-0221: the "
          "old text claimed `done` is decided by somebody other than the actor)",
          "decided by something other than the person asserting it" not in out_of(blocked),
          out_of(blocked).strip()[:240])
    check("FIX: the blocked refusal is on the ledger as a class=form row",
          any(r.get("action") == "task move" and r.get("reason", "").startswith(
              f"REFUSED: {A} is blocked by") for r in refusals()),
          json.dumps(refusals(), ensure_ascii=False)[-300:])

    ledger_before = len(ledger_rows())
    forced = run("task", "move", "--as", "alpha", "--channel", "c",
                 "--id", A, "--to", "done", "--force",
                 "--evidence", "walked the cycle by hand; the pair is each other's blocker",
                 "--reason", "the pair is deadlocked by hand")
    check("FIX: --force closes the card against an open blocker",
          forced.returncode == 0 and f"{A}: review -> done" in forced.stdout,
          f"rc={forced.returncode} {out_of(forced)}")
    check("FIX: --force says on stdout what it overrode",
          "FORCED" in forced.stdout and f"blocker:{B}" in forced.stdout,
          forced.stdout)
    a_move = moved(A)[0] if moved(A) else {}
    check("FIX: the `moved` event records forced=true -- an override is no longer "
          "byte-identical to an ordinary move",
          a_move.get("forced") is True, json.dumps(a_move)[:280])
    check("FIX: the `moved` event names the blocker it overrode",
          a_move.get("overrode") == [f"blocker:{B}"], json.dumps(a_move)[:280])
    check("FIX: the `moved` event carries the reason, so the override can be "
          "reconstructed from the store alone",
          a_move.get("reason") == "the pair is deadlocked by hand",
          json.dumps(a_move)[:280])
    check("FIX: who forced it is on the event too (actor, and the session)",
          a_move.get("actor") == "alpha" and bool(a_move.get("session")),
          json.dumps(a_move)[:280])
    # BOUNDARY, not a defect. The fix's own criterion was "somewhere a reader can
    # find them (ledger or store)", and the store now carries all of it. The
    # ledger is where *refusals* live (`_record_refusal`), and a forced move is
    # not a refusal -- so it stays empty of this act, and unlike `task publish`
    # (which got `task_published_during_divergence`) there is no ledger class for
    # it. If a later change gives the override its own ledger class, this row
    # flips and that change is an improvement: re-point the row, do not "repair"
    # it.
    check("BOUNDARY: a forced move writes no ledger row -- the trace is on the "
          "store's event, and the ledger (the refusal index) does not grow",
          len(ledger_rows()) == ledger_before,
          f"{len(ledger_rows()) - ledger_before} ledger row(s) written by the override")

    unused = run("task", "move", "--as", "alpha", "--channel", "c",
                 "--id", W, "--to", "done", "--force",
                 "--evidence", "nothing to measure here; this card closes cleanly")
    w_move = moved(W)[0] if moved(W) else {}
    check("FIX: a --force that overrode no rule is marked force_unused, not forced "
          "-- the flag means 'the caller was stopped', not 'the caller was nervous'",
          unused.returncode == 0 and w_move.get("force_unused") is True
          and "forced" not in w_move,
          f"rc={unused.returncode} {json.dumps(w_move)[:240]}")

    # ----------------------------------- 6. what the override cost the pair
    print("\n== 6. the other half of the cycle ==")
    second = run("task", "move", "--as", "alpha", "--channel", "c",
                 "--id", B, "--to", "done",
                 "--evidence", "T-0251 fixture: A is closed, so the cycle is broken")
    check("FIX: with A forced through, B closes with no override at all",
          second.returncode == 0,
          f"rc={second.returncode} {out_of(second).strip()[:200]}")
    b_move = moved(B)[0] if moved(B) else {}
    check("FIX: and B's move is honestly unforced -- no `forced`, no `overrode` key",
          "forced" not in b_move and "overrode" not in b_move,
          json.dumps(b_move)[:240])
    ab_moves = [m for m in moved() if m.get("task") in (A, B) and m.get("to") == "done"]
    check("FIX: the pair's two `moved` events reconstruct the whole story from the "
          "store alone -- A says what it overrode, B is plain",
          [(m["task"], m.get("forced", False), m.get("overrode")) for m in ab_moves]
          == [(A, True, [f"blocker:{B}"]), (B, False, None)],
          json.dumps(ab_moves, ensure_ascii=False)[:300])
    forced_edges = [e for e in linked() if e.get("forced")]
    check("FIX: exactly one edge in the store was written over a refusal, and it "
          "carries the route it closed",
          [(e["task"], e["blocked_by"], e.get("cycle"), e.get("cycle_check"))
           for e in forced_edges] == [(B, A, f"{B} -> {A} -> {B}", "forced")],
          json.dumps(forced_edges, ensure_ascii=False)[:300])

    # ------------------------ 7. an ordinary pair still closes with no override
    print("\n== 7. an ordinary dependency still gates `done` ==")
    p_on_q = run("task", "link", "--as", "alpha", "--channel", "c",
                 "--id", P, "--blocked-by", Q)
    p_blocked = run("task", "move", "--as", "alpha", "--channel", "c",
                    "--id", P, "--to", "done",
                    "--evidence", "T-0251 fixture: refused before the accept gate is reached")
    q_done = run("task", "move", "--as", "alpha", "--channel", "c",
                 "--id", Q, "--to", "done",
                 "--evidence", "T-0251 fixture: Q closes on its own")
    p_done = run("task", "move", "--as", "alpha", "--channel", "c",
                 "--id", P, "--to", "done",
                 "--evidence", "T-0251 fixture: the blocker is done, the edge is clear")
    check("FIX: a real dependency still refuses `done` while its blocker is open",
          p_on_q.returncode == 0 and p_blocked.returncode == 2
          and f"{P} is blocked by {Q}" in out_of(p_blocked),
          f"link rc={p_on_q.returncode} move rc={p_blocked.returncode} "
          f"{out_of(p_blocked).strip()[:200]}")
    check(f"FIX: finish the blocker and the card closes unforced, with no `forced` "
          f"key anywhere in its history",
          q_done.returncode == 0 and p_done.returncode == 0
          and all("forced" not in m for m in moved(P) + moved(Q)),
          f"rc={q_done.returncode}/{p_done.returncode} "
          f"{json.dumps(moved(P) + moved(Q), ensure_ascii=False)[:260]}")
    cycle_refusals = [r for r in refusals() if "would close a cycle" in r.get("reason", "")]
    check("FIX: every cycle refusal in the ledger names the route it refused, and "
          "every one is a class=form row -- the audit question 'how did this cycle "
          "get here' is answerable from the chain",
          len(cycle_refusals) == 3
          and all("->" in r["reason"] and r.get("class") == "form"
                  for r in cycle_refusals),
          json.dumps([r.get("reason", "")[:90] for r in cycle_refusals], ensure_ascii=False))
    check("FIX: and the length-one cycle has its own refusal row, with the same class, "
          "so 'a card was made to block itself' is on the chain too",
          any(r.get("action") == "task link" and r.get("class") == "form"
              and "cannot block itself" in r.get("reason", "") for r in refusals()),
          json.dumps([r.get("reason", "")[:60] for r in refusals()], ensure_ascii=False))
    verified = run("verify", "--channel", "c")
    check("FIX: the chain over the events written with the new fields still verifies",
          "chain OK" in out_of(verified), out_of(verified).strip()[:200])

    # ----------------------------------------------------------------- table
    def status(tid):
        for e in reversed(events()):
            if e.get("task") == tid and e.get("to"):
                return e["to"]
        return "?"

    print("\n  what the cycle produced, row by row")
    print(f"    {'step':<48} {'rc':>3}  what it wrote")
    rows = [
        (f"link {A} blocked_by {B}", a_on_b.returncode,
         "the edge, cycle_check=clean on the event"),
        (f"link {B} blocked_by {A}  <- the cycle", b_on_a.returncode,
         "rc 2 + a refusal row, class=form, naming the route"),
        (f"link {A} blocked_by {D}  (3-cycle)", three.returncode,
         "rc 2 + a refusal row naming the whole route"),
        (f"link {A} blocked_by {A}  (self edge)", self_edge.returncode,
         "rc 2 + a refusal row; not even --force writes this one"),
        (f"link {B} blocked_by {A} --force", forced_link.returncode,
         "the edge, cycle_check=forced, forced=true, cycle=<route>"),
        (f"link {V} blocked_by {D}  (into the cycle)", v_on_d.returncode,
         "admitted as cycle_check=clean -- see the surviving-defect row"),
        (f"move {A} -> done (blocked)", blocked.returncode,
         "rc 2 + a refusal row, class=form, names --force"),
        (f"move {A} -> done --force --reason", forced.returncode,
         "forced=true, overrode=[blocker:%s], with the reason" % B),
        (f"move {W} -> done --force (nothing to override)", unused.returncode,
         "force_unused=true; the ledger does not grow"),
        (f"move {B} -> done (after the override)", second.returncode,
         "rc 0, no forced field: A paid for the pair"),
        (f"move {Q} -> done, then {P} -> done", p_done.returncode,
         "an ordinary pair, no override anywhere in it"),
    ]
    for label, rc, wrote in rows:
        print(f"    {label:<48} {rc:>3}  {wrote}")
    print(f"    final statuses: {A}={status(A)} {B}={status(B)} {C}={status(C)} "
          f"{D}={status(D)} {P}={status(P)} {Q}={status(Q)} {V}={status(V)} "
          f"{W}={status(W)}")

print(f"\n{passed}/{passed + failed} checks passed")
print("This file measures the fix for T-0221: `link` refuses an edge that closes a")
print("cycle and records the refusal with a class, the verdict travels on the")
print("`linked` event, and a forced move records the flag, the reason and the rule")
print("it overrode. It goes red if any of that regresses.")
print("Two rows are pinned as measured boundaries rather than as fix behaviour: the")
print("forced move writes no ledger row (BOUNDARY -- the trace is on the store), and")
print("an edge into a card whose closure already contains a cycle is admitted as")
print("`clean` while that card still cannot close (DEFECT, surviving). Neither is")
print("fixed here; `bin/aim` is not this file's to change.")
sys.exit(1 if failed else 0)
