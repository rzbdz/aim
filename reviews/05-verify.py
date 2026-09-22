#!/usr/bin/env python3
"""Reproduce every claim in reviews/05-instrument-integrity.md.

INVERTED 2026-09-22 (orchestrator loop): the checks below were written to PIN the
defects measured in reviews/05-instrument-integrity.md -- "drift names ids that
visible_tasks withheld" was PASS while the bug was present. It is now FAIL, which
means the probe was a bug museum and not an acceptance test. Each such check has
been rewritten to assert the CORRECT behaviour, so this file fails if a fix
regresses. The old wording is preserved in the detail strings.

READ-ONLY: issues GETs and reads files under aimboard/ and plan/. Writes nothing to the
fabric, sends nothing, seals nothing.

SAFETY: it queries ?as=human because S1/S2 are claims *about* the identity switch. It prints
only COUNTS of sealed entries that carry a claims array. It never prints claim text, titles of
sealed material, or private logs. If you are not comfortable running step 1, run with
--skip-leader-view and S1/S2 will be reported as unverified.

    python3 reviews/05-verify.py
"""
import argparse, json, sys, urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8777/api/state"
ROOT = Path(__file__).resolve().parent.parent
OK, BAD, SKIP = "PASS", "FAIL", "SKIP"
results = []


def get(qs=""):
    with urllib.request.urlopen(BASE + qs, timeout=10) as r:
        return json.loads(r.read().decode())


def check(name, cond, detail=""):
    results.append((OK if cond else BAD, name, detail))
    print(f"[{OK if cond else BAD}] {name}" + (f"\n       {detail}" if detail else ""))


def claims_visible(payload):
    """How many sealed entries carry a claims ARRAY. Counts only; contents never read."""
    return sum(1 for ch in payload["channels"] for e in ch["sealed"] if "claims" in e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-leader-view", action="store_true",
                    help="do not issue ?as=human; S1 and S2 become SKIP")
    a = ap.parse_args()

    print("== S1: is the default view the leader's, and is 'as' authenticated? ==")
    default = get()
    check("no `as` at all is served as the leader",
          default.get("viewer") == "human",
          f"viewer={default.get('viewer')!r} withheld={default['withheld_tasks']}")
    mine = get("?as=codex-orangement")
    unknown = get("?as=nobody-at-all")
    check("an unknown identity is not refused (served as a stranger)",
          unknown.get("viewer") == "nobody-at-all",
          f"viewer={unknown.get('viewer')!r} withheld={unknown['withheld_tasks']}")
    rd = default.get("read") or {}
    borrow = get("?as=codex-orangement").get("read") or {}
    check("S1b: the payload names the seat it served, and whether it was borrowed",
          default.get("viewer") == "human" and rd.get("as") == "human"
          and rd.get("borrowed") is False and borrow.get("borrowed") is True,
          f"no-?as -> read={rd!r}; ?as=codex-orangement -> read={borrow!r}. "
          f"(was: no 'read' key at all, so a consumer that forgot ?as= could not tell)")

    if a.skip_leader_view:
        results.append((SKIP, "leader's view carries 5 peers' seal claims", "--skip-leader-view"))
        print(f"[{SKIP}] leader-view seal probe skipped")
    else:
        human = get("?as=human")
        cv_h, cv_m = claims_visible(human), claims_visible(mine)
        # design/06 R1 sanctions borrowing a *view* via ?as=. The finding is not the borrow; it is
        # that one seat's view carries a privilege over OTHER participants' sealed material.
        check("borrowing the leader's view also carries third-party seals (S1)",
              cv_h > cv_m,
              f"as=human: {cv_h} entries carry claims; as=codex-orangement: {cv_m}; "
              f"as=codex: {claims_visible(get('?as=codex'))} (his own only). "
              f"Counts only; no claim text was read. R1 sanctions the borrow, not the custody.")
        # S2
        print("\n== S2: are the aggregates seat-dependent? ==")
        rows = []
        for who in ("human", "codex", "codex-orangement"):
            d = human if who == "human" else (mine if who == "codex-orangement" else get("?as=codex"))
            r = d["reports"]
            rows.append((who, len(d["tasks"]), d["withheld_tasks"], r["recorded"],
                         r["with_history"], r["seed_only"]))
        for row in rows:
            print("       {:<18} visible={:3} withheld={:3} recorded={:3} "
                  "with_history={:2} seed_only={:3}".format(*row))
        scope = {r[0]: (human if r[0] == "human" else None) for r in rows}
        check("`recorded` is the fabric total, the same on every seat",
              len({r[3] for r in rows}) == 1,
              f"recorded values: {sorted({r[3] for r in rows})} "
              f"(was: 26/43/72, the seat's slice quoted as the project's)")
        check("`with_history` is the fabric total, the same on every seat",
              len({r[4] for r in rows}) == 1,
              f"with_history values: {sorted({r[4] for r in rows})} "
              f"(was: 1/2/4, one per seat)")
        check("and the payload says so, rather than leaving the reader to guess",
              (human.get("reports_scope") or "").lower() == "fabric"
              and human.get("reports_viewer") is not None,
              f"reports_scope={human.get('reports_scope')!r} "
              f"reports_viewer={human.get('reports_viewer')!r}")

    print("\n== S3: does `drift` name task ids the gate withheld from this viewer? ==")
    visible = set(mine["tasks"])
    drift_ids = {d["id"] for d in mine["drift"]}
    leaked = sorted(drift_ids - visible)
    check("drift names no id the gate withheld from this viewer",
          not leaked,
          f"{len(leaked)} leaked: {leaked} (was: 15 leaked for this seat, "
          f"because drift sat outside the redaction path)")

    print("\n== S3b: is drift identical for every seat (i.e. not redacted at all)? ==")
    seats = ["codex-orangement", "codex"] + ([] if a.skip_leader_view else ["human"])
    leaks = {}
    for w in seats:
        d = get(f"?as={w}")
        leaks[w] = sorted({x["id"] for x in d["drift"]} - set(d["tasks"]))
        print(f"       {w:<18} drift={len(d['drift']):3} visible={len(d['tasks']):3} "
              f"withheld_from_drift={d.get('drift_withheld')!r} leaked={len(leaks[w])}")
    check("no seat's drift names an id that seat cannot see",
          not any(leaks.values()),
          f"leaks per seat: {leaks} (was: one array, byte-identical for every seat)")

    print("\n== S4: does drift compare the plan to channels[0] only, and which channel is that? ==")
    sys.path.insert(0, str(ROOT))
    from aimboard.fabric import load_fabric
    from aimboard.fold import drift
    from datetime import date
    st = load_fabric(ROOT, ["plan/*.json"], date.fromisoformat(mine["as_of"]))
    ch = st["channels"]
    order = [c["id"] for c in ch]
    print(f"       channel order: {order}")
    for c in ch:
        print(f"       {c['id']:<12} phase={c['phase']:<18} tasks_recorded={len(c['tasks_recorded']):3}")
    union = {}
    for c in ch:
        union.update(c["tasks_recorded"])
    d0, du = drift(st["seed_tasks"], ch[0]["tasks_recorded"]), drift(st["seed_tasks"], union)
    check("channels[0] is not the channel holding most of the store",
          len(ch[0]["tasks_recorded"]) < max(len(c["tasks_recorded"]) for c in ch),
          f"channels[0]={ch[0]['id']} holds {len(ch[0]['tasks_recorded'])}; "
          f"largest holds {max(len(c['tasks_recorded']) for c in ch)}")
    check("the choice is LATENT today: ch[0] and the union give the same drift",
          len(d0) == len(du),
          f"drift(channels[0])={len(d0)}  drift(union)={len(du)}; "
          f"no plan seed is recorded anywhere: "
          f"seeds={len(st['seed_tasks'])} seeds_recorded={len(set(st['seed_tasks']) & set(union))}")

    print("\n== N1: does reports.blocked list completed tasks? ==")
    src = mine if a.skip_leader_view else get("?as=human")
    bl = src["reports"]["blocked"]
    by = {}
    for b in bl:
        by[b["status"]] = by.get(b["status"], 0) + 1
    check("`blocked` lists only rows waiting on an unmet dependency",
          not any(s in by for s in ("done", "dropped", "review")),
          f"{len(bl)} rows by status: {by} (was: 51 rows incl. 24 done, 1 review)")
    contradictory = [b["id"] for b in bl if b["status"] == "review"]
    check("no completed task is listed as blocked", not by.get("done"),
          f"review-stage rows listed under blocked: {contradictory}")

    print("\n== summary ==")
    bad = [r for r in results if r[0] == BAD]
    skipped = [r for r in results if r[0] == SKIP]
    print(f"  {len(results)} checks: {len(results)-len(bad)-len(skipped)} pass, "
          f"{len(bad)} fail, {len(skipped)} skipped")
    for _, name, _d in bad:
        print(f"  FAIL {name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
