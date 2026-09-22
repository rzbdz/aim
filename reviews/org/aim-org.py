#!/usr/bin/env python3
"""aim org -- prototype. One surface that answers "how is this organised?"

The leader's question, verbatim: *"I just don't get how these channels organized…
that's a big problem right now"*, and separately *"能否最快获取到组织架构，清楚谁可以调度，
向谁汇报"*. Today the answer exists only as prose in a message one agent typed to
another. This is the smallest thing that answers it out loud.

It reads `registry.json` (root-level, not inside any channel) and `aim status
--channel <id>` (a verb a registered non-member may already run and which is refused
by the barrier when it should be). It reads **no** private log, **no** seal, **no**
task store, and **no** ledger. That is not politeness: a derived org chart built
from gated bytes would be a route around a refusal, and an org chart that is itself
a leak is worse than no org chart.

The rule the output keeps, and the reason it prints two sections and not one:

    derive what the record already knows; declare what it cannot know.

Membership, phases and who is sealed are *facts in the record* -- derived here and
labelled (derived). Who reports to whom is *not* in the record anywhere and cannot
be inferred without guessing, so it is read from an optional declared file and
labelled (declared). An inferred reporting line presented as a recorded one is the
exact failure this project is built to refuse.

What it honestly cannot answer, printed at the end rather than omitted: whether an
agent's session is alive. `registry.json` carries `registered_at` and nothing else.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if "__file__" in dir() else Path.cwd()
DECLARED = "org.json"


def run_status(channel, root):
    p = subprocess.run(["aim", "status", "--channel", channel],
                       capture_output=True, text=True, cwd=str(root))
    if p.returncode != 0:
        return {"error": (p.stderr or p.stdout).strip().splitlines()[0][:120]}
    out = p.stdout
    def grab(label):
        m = re.search(rf"^{label}\s+(.*)$", out, re.M)
        return m.group(1).strip() if m else ""
    members = []
    # [ \t]+ and not \s+: \s crosses a newline, so the optional group for a seal
    # digest swallowed the *next* participant's name on every line that ended
    # "unsealed". The tool then printed a confident membership list with rows
    # missing -- the same failure as "a log that silently drops events still
    # draws a clean board". Found by running it against #dev, which has two
    # participants and reported one.
    for m in re.finditer(r"^  (\S+)[ \t]+private=(\d+)[ \t]+public=(\d+)[ \t]+(\w+)(?:[ \t]+(\w+))?",
                         out, re.M):
        members.append({"agent": m.group(1), "private": int(m.group(2)),
                        "public": int(m.group(3)), "seal": m.group(4),
                        "digest": (m.group(5) or "")})
    # "leader    human   synthesizer synthesizer-v0" is ONE line carrying TWO
    # relations. Reading only the first token reported barrier-v0's synthesizer as
    # unset, which is the same failure as reading only `participants`: an org chart
    # that models one relation reports the leader and the synthesizer as unplaced.
    lm = re.search(r"^leader[ \t]+(\S+)[ \t]+synthesizer[ \t]+(.*)$", out, re.M)
    leader = lm.group(1) if lm else ""
    synth_raw = (lm.group(2).strip() if lm else "")
    synth = "" if synth_raw in ("(unset)", "") else synth_raw.split()[0]
    return {"phase": grab("phase").split()[0] if grab("phase") else "",
            "leader": leader,
            "synthesizer": synth,
            "topic": grab("topic"),
            "rules": grab("rules"),
            "history": grab("history"),
            "log": grab("log"),
            "members": members}


def main():
    ap = argparse.ArgumentParser(description="who exists, who is where, who reports to whom")
    ap.add_argument("--root", default="/root/tmp/agent-im")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)

    reg = json.loads((root / "registry.json").read_text())["agents"]
    channels = sorted(p.name for p in (root / "channels").iterdir() if p.is_dir()
                      and (p / "manifest.json").exists())
    status = {c: run_status(c, root) for c in channels}

    placed, unplaced, leads, synths = {}, [], {}, {}
    for aid in sorted(reg):
        rooms = [c for c in channels if any(m["agent"] == aid
                                            for m in (status[c].get("members") or []))]
        placed[aid] = rooms
        # The leader is a participant of none by design -- "the leader is the
        # audience, not a participant" -- so membership alone renders the human as
        # unplaced. Leadership is recorded in every manifest, so it is derived,
        # not asserted.
        leads[aid] = [c for c in channels if status[c].get("leader") == aid]
        synths[aid] = [c for c in channels if status[c].get("synthesizer") == aid]
        if not rooms and not leads[aid] and not synths[aid]:
            unplaced.append(aid)

    declared = {}
    dpath = root / DECLARED
    if dpath.exists():
        try:
            declared = json.loads(dpath.read_text())
        except ValueError as exc:
            declared = {"_error": f"{DECLARED} exists but does not parse: {exc}"}

    if a.json:
        print(json.dumps({"agents": reg, "membership": placed, "channels": status,
                          "declared": declared}, indent=2))
        return 0

    print("== agents (derived from registry.json) ==")
    for aid, v in sorted(reg.items(), key=lambda kv: (not placed[kv[0]], kv[0])):
        where = ", ".join("#" + c for c in placed[aid]) or "— in no channel —"
        if leads[aid]:
            where += f"   [leads {', '.join('#' + c for c in leads[aid])}]"
        if synths[aid]:
            where += f"   [synthesises {', '.join('#' + c for c in synths[aid])}]"
        print(f"  {aid:18} {v.get('kind',''):7} {str(v.get('model',''))[:12]:12} "
              f"registered {v.get('registered_at','')[:16]}  {where}")
        if v.get("session"):
            print(f"      session: {v['session']}")

    print("\n== channels (derived from `aim status`) ==")
    for c in channels:
        s = status[c]
        if s.get("error"):
            print(f"  #{c:14} UNREADABLE: {s['error']}")
            continue
        members = ", ".join(f"{m['agent']}({m['seal']})" for m in s["members"]) or "(none)"
        print(f"  #{c:14} {s['phase']:17} leader={s['leader']:6} "
              f"synthesizer={s['synthesizer'] or '(unset)':16} log={s['log'] or '-'}")
        print(f"      participants: {members}")

    print("\n== dispatch surface (derived: who is reachable at all) ==")
    print(f"  in at least one channel : {len(reg) - len(unplaced)} of {len(reg)}")
    print(f"  leads at least one      : {sum(1 for a in leads if leads[a])} of {len(reg)}")
    print(f"  synthesises at least one: {sum(1 for a in synths if synths[a])} of {len(reg)}")
    print(f"  in no channel           : {unplaced or '(none)'}")
    if unplaced:
        print("      ^ registered, addressable by doorbell, and a member of nothing: the")
        print("        only way an instruction reaches them is a direct push, and there is")
        print("        no queue that shows a request is pending.")

    print("\n== reporting lines (DECLARED, not derivable) ==")
    if not dpath.exists():
        print(f"  no {DECLARED} at {root}. Nothing in the record states who reports to")
        print("  whom, and this tool will not infer it: a guessed edge drawn as a recorded")
        print("  one is the failure the rest of this fabric exists to prevent.")
        print(f"  To declare it, write {root/DECLARED}:")
        print('    {"reports_to": {"codex-orangement": "codex", "codex": "human"},')
        print('     "role": {"codex": "PM/reviewer", "human": "team leader"}}')
    elif declared.get("_error"):
        print(f"  {declared['_error']}")
    else:
        for who, boss in sorted((declared.get("reports_to") or {}).items()):
            role = (declared.get("role") or {}).get(who, "")
            print(f"  {who:18} -> {boss:14} {role}")

    print("\n== what this cannot answer ==")
    print("  * whether a session is alive. registry.json has registered_at and no")
    print("    last-seen, so 'idle' and 'dead' are the same value here.")
    print("  * how much work is waiting inside a channel this viewer may not read.")
    print("    The count is published (`aim task list --count-hidden`); the contents are")
    print("    not, and must not be.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
