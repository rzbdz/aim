#!/usr/bin/env python3
"""The work-item contract, executed.

`tests/selftest.sh` asserts the barrier's rules; `tests/conformance.py` asserts the
transport under real processes; `tests/test_aimboard.py` asserts the renderer.
This file asserts the third thing: the work-item surface that `design/05` froze,
including the refusals - because a contract with unasserted refusals is a
description of what the author intended, not of what the tool does.

Every check here was written from design/05 section 5 and then run against the
tool. Two of them failed the first time they were run, which is the reason the
file exists: an interface document nobody executes is a wish.

Run: python3 tests/test_pm_contract.py      (exit code = number of failures)
"""
import collections
import re
import concurrent.futures as futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AIM = Path(__file__).resolve().parent.parent / "bin" / "aim"
results = []
CH = "t"


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))


class Fabric:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="pm-contract-"))
        self.env = dict(os.environ, AIM_ROOT=str(self.root))

    def aim(self, *args, **kw):
        return subprocess.run([sys.executable, str(AIM)] + [str(a) for a in args],
                              env=self.env, capture_output=True, text=True,
                              timeout=120, **kw)

    def refused(self, *args):
        """Refused AND recorded.

        The contract is not "the command failed" - `aim` can fail for a dozen
        uninteresting reasons. It is that the gate held *and* the attempt is in the
        ledger, because the ledger is the only part of this system that can tell a
        barrier nobody leaned on from one that stopped somebody.
        """
        before = len([r for r in self.ledger() if r.get("event") == "refusal"])
        p = self.aim(*args)
        after = [r for r in self.ledger() if r.get("event") == "refusal"]
        return (p.returncode != 0 and len(after) > before), p

    def ledger(self):
        path = self.root / "channels" / CH / "ledger.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def store(self):
        path = self.root / "channels" / CH / "tasks.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def new_task(f, actor="codex", *extra):
    """Create a work item and return the id the tool assigned.

    Ids are read back rather than assumed: a fixture that hardcodes T-0004 breaks
    the moment an earlier step stops consuming an id, and the break looks like a
    product defect. That happened while writing this file.
    """
    p = f.aim("task", "new", "--as", actor, "--channel", CH, *extra)
    m = re.search(r"(T-\d+)", p.stdout)
    if not m:
        raise AssertionError(f"no task id in output: {p.stdout!r} {p.stderr!r}")
    return m.group(1)


def setup(f):
    f.aim("init")
    for a, k in (("human", "human"), ("codex", "codex"), ("claude-session1", "claude")):
        f.aim("register", "--as", a, "--kind", k)
    f.aim("new-channel", "--id", CH, "--topic", "contract", "--participants",
          "codex,claude-session1")
    draft = new_task(f, "codex", "--title", "a draft item")
    # The leader is exempt from the phase gate; an agent is not. Both halves matter,
    # so the fixture tests the exempt one deliberately rather than by accident.
    published = new_task(f, "human", "--title", "a published item", "--visibility", "published")
    return draft, published


def main():
    f = Fabric()
    try:
        draft_id, published_id = setup(f)

        print("== design/05 section 5: the refusals the contract demands ==")
        ok, p = f.refused("task", "new", "--as", "codex", "--channel", CH,
                          "--title", "leak", "--visibility", "published")
        check("publishing a work item during a divergence phase is refused", ok,
              p.stderr.strip()[:110])
        ok, p = f.refused("task", "new", "--as", "codex", "--channel", CH,
                          "--title", "orphan", "--owner", "nobody")
        check("assigning to an unregistered agent is refused", ok, p.stderr.strip()[:110])
        ok, p = f.refused("task", "list", "--as", "claude-session1", "--channel", CH, "--json")
        check("reading a peer's draft before cross-examination is refused", ok,
              f"rc={p.returncode} stdout={p.stdout.strip()[:60]} - an empty list is "
              f"indistinguishable from 'there is no work', which is the failure the ledger exists to prevent")
        ok, p = f.refused("task", "move", "--as", "codex", "--channel", CH,
                          "--id", draft_id, "--to", "blocked")
        check("moving to blocked without a reason is refused", ok, p.stderr.strip()[:110])
        ok, p = f.refused("task", "move", "--as", "codex", "--channel", CH,
                          "--id", draft_id, "--to", "dropped")
        check("dropping without a reason is refused", ok, p.stderr.strip()[:110])
        f.aim("register", "--as", "outsider", "--kind", "claude")
        ok, p = f.refused("task", "new", "--as", "outsider", "--channel", CH,
                          "--title", "not mine to write")
        check("a registered agent who is not a participant cannot write, and it is recorded",
              ok, f"rc={p.returncode}: {p.stderr.strip()[:90]}")

        print("== the blocker rule ==")
        blocker = new_task(f, "codex", "--title", "the blocker")
        created = [r for r in f.store()
                   if r.get("event") == "created" and r.get("title") == "the blocked one"]
        blocked = new_task(f, "codex", "--title", "the blocked one", "--blocked-by", blocker)
        created = [r for r in f.store()
                   if r.get("event") == "created" and r.get("title") == "the blocked one"]
        check("--blocked-by on `task new` records the dependency, or says it will not",
              bool(created) and bool(created[0].get("blocked_by")),
              "the flag is accepted and silently dropped: rc=0, no field, no warning. A "
              "dependency the tool agreed to record and did not is worse than a refusal, "
              "because the board then shows an item that nothing is holding up")
        f.aim("task", "link", "--as", "codex", "--channel", CH, "--id", blocked,
              "--blocked-by", blocker)
        for status in ("ready", "doing", "review"):
            f.aim("task", "move", "--as", "codex", "--channel", CH, "--id", blocked, "--to", status)
        ok, p = f.refused("task", "move", "--as", "codex", "--channel", CH,
                          "--id", blocked, "--to", "done")
        check("an item cannot be done while its blocker is open", ok,
              (p.stdout + p.stderr).strip()[:100])
        for status in ("ready", "doing", "review", "done"):
            f.aim("task", "move", "--as", "codex", "--channel", CH, "--id", blocker, "--to", status)
        p = f.aim("task", "move", "--as", "codex", "--channel", CH, "--id", blocked, "--to", "done")
        check("it can be done once the blocker is done", p.returncode == 0,
              (p.stdout + p.stderr).strip()[:110])

        print("== identifier allocation under concurrency ==")
        before = len([r for r in f.store() if r.get("event") == "created"])

        def spawn(i):
            return f.aim("task", "new", "--as", "codex", "--channel", CH, "--title", f"race {i}")

        with futures.ThreadPoolExecutor(max_workers=12) as pool:
            outs = list(pool.map(spawn, range(12)))
        made = [r for r in f.store() if r.get("event") == "created"]
        ids = collections.Counter(r.get("task") or r.get("id") for r in made)
        dupes = {k: v for k, v in ids.items() if v > 1}
        check("all 12 concurrent creations succeeded",
              sum(1 for o in outs if o.returncode == 0) == 12,
              str([o.stderr.strip()[:60] for o in outs if o.returncode]))
        check("every created record has a distinct id", not dupes,
              f"duplicate ids {dupes}: two work items share one id, and the fold then "
              f"collapses them, so work exists in the record and not on the board")
        check("the append survived it", len(made) - before == 12, f"{len(made) - before} records")

        print("== the ledger and the chain ==")
        refusals = [r for r in f.ledger() if r.get("event") == "refusal"]
        barrier_class = [r for r in refusals if r.get("class") == "barrier"]
        check("refusals are recorded, not just printed", len(refusals) >= 3, str(len(refusals)))
        check("the barrier refusals are distinguishable from malformed requests",
              bool(barrier_class), f"classes seen: {sorted({r.get('class') for r in refusals})}")
        check("every refusal names the agent, the action and the phase",
              all(r.get("agent") and r.get("action") and r.get("phase") for r in refusals))
        p = f.aim("verify", "--channel", CH)
        check("the task log is covered by aim verify", "OK" in (p.stdout + p.stderr),
              (p.stdout + p.stderr).strip()[:110])

        print("== the board reads what the tool wrote ==")
        board = Path(__file__).resolve().parent.parent / "bin" / "aimboard.py"
        p = subprocess.run([sys.executable, str(board), "render", "--root", str(f.root), "--json",
                            "--as-of", "2026-09-21", "--generated-at", "2026-09-21T00:00:00Z"],
                           capture_output=True, text=True, timeout=120)
        doc = json.loads(p.stdout) if p.returncode == 0 else {}
        check("the renderer exits 0 on this fabric", p.returncode == 0, p.stderr[:200])
        check("the board sees the same distinct ids the store holds",
              len(doc.get("tasks", {})) == len(ids), f"board {len(doc.get('tasks', {}))} vs store {len(ids)}")
        check("the board shows the refusal count the ledger holds",
              doc.get("phases", {}).get(CH, {}).get("refusals") == len(refusals))
    finally:
        f.close()

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for name in failed:
        print(f"  failed: {name}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
