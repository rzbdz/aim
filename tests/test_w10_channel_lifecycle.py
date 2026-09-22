#!/usr/bin/env python3
"""W10 / T-0216: a channel must say whether it is empty or alive, and what it is.

The defect, measured on the live store: five channels, one flat namespace. `dev`
carries a real topic, a leader and two participants and then **nothing** -- no
message, no task, no ledger event, no seal -- while `hello`, named after a
transport test, holds the work. `aim status --channel dev` printed the same
declaration fields for both, so the board could not tell the channel it was told
to develop in from the one the development happened in.

These tests fail against the old `load_fabric`, which had no derived lifecycle at
all: `state` is absent from every channel dict, so the first check is the one that
speaks.

Run: python3 tests/test_w10_channel_lifecycle.py     (exit code = failures)
"""
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from aimboard.fabric import (DORMANT_AFTER_DAYS, channel_lifecycle,
                             channel_kind, load_fabric)

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}"
          + (f"\n          {detail}" if detail and not ok else ""))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def jsonl(path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")


def manifest(cid, topic, created, participants=("human", "codex"), extra=None):
    m = {
        "id": cid, "topic": topic, "created_at": created, "leader": "human",
        "synthesizer": "", "participants": list(participants),
        "barrier": {"phase": "SEALED_DIVERGENT", "round": 0,
                    "history": [{"phase": "SEALED_DIVERGENT", "by": "human"}]},
    }
    return {**m, **(extra or {})}


def fixture(root):
    write(root / "registry.json", {"agents": {
        "human": {"id": "human", "kind": "human"},
        "codex": {"id": "codex", "kind": "codex"},
    }})
    chans = root / "channels"

    # The card's own example: a real declaration, zero traffic.
    write(chans / "dev" / "manifest.json",
          manifest("dev", "aim development: task store, rooms, dashboard",
                   "2026-09-20T00:00:00Z"))

    # The channel the work actually happened in, named after a transport test.
    write(chans / "live" / "manifest.json",
          manifest("live", "Transport test: can two sessions reach each other",
                   "2026-09-21T00:00:00Z"))
    jsonl(chans / "live" / "log.jsonl",
          [{"ts": "2026-09-22T01:00:00Z", "from": "codex", "body": "on the record"}])
    jsonl(chans / "live" / "ledger.jsonl",
          [{"ts": "2026-09-22T01:00:01Z", "event": "seal", "agent": "codex"}])
    jsonl(chans / "live" / "tasks.jsonl",
          [{"ts": "2026-09-22T01:00:02Z", "event": "created", "task": "T-1",
            "actor": "codex", "title": "a task", "status": "doing"}])
    write(chans / "live" / "seals" / "codex.json",
          {"agent": "codex", "ts": "2026-09-22T01:00:03Z", "claims": []})

    # A throwaway probe, distinguished by nothing but its topic today (T-0232).
    write(chans / "probe" / "manifest.json",
          manifest("probe", "scratch: does aim authenticate --as?",
                   "2026-09-05T00:00:00Z", participants=("human",)))
    jsonl(chans / "probe" / "ledger.jsonl",
          [{"ts": "2026-09-05T00:10:00Z", "event": "seal", "agent": "codex"}])

    # A manifest that *declares* its kind: the declaration wins over the topic.
    write(chans / "declared" / "manifest.json",
          manifest("declared", "internal review of the allocator",
                   "2026-09-21T00:00:00Z", extra={"kind": "scratch"}))
    jsonl(chans / "declared" / "log.jsonl",
          [{"ts": "2026-09-22T02:00:00Z", "from": "codex", "body": "hi"}])

    # One day idle, below the threshold: still active, not dormant.
    write(chans / "quiet" / "manifest.json",
          manifest("quiet", "a real project channel", "2026-09-19T00:00:00Z"))
    jsonl(chans / "quiet" / "ledger.jsonl",
          [{"ts": "2026-09-21T00:00:00Z", "event": "seal", "agent": "codex"}])
    return root


def by_id(state):
    return {c["id"]: c for c in state["channels"]}


def main():
    work = Path(tempfile.mkdtemp(prefix="w10-lifecycle-"))
    try:
        root = fixture(work)
        state = load_fabric(root, [], date(2026, 9, 22))
        chans = by_id(state)

        print("== the card's example: dev is empty, live is active ==")
        dev, live = chans["dev"], chans["live"]
        check("the old code has no `state` at all -> this is the failing check",
              "state" in dev, sorted(dev))
        check("an empty channel is classified empty",
              dev.get("state") == "empty", dev.get("state"))
        check("an active channel is classified active",
              live.get("state") == "active", live.get("state"))
        check("empty and active are distinguishable without a hand-maintained field",
              dev.get("state") != live.get("state"))
        check("the empty channel's traffic is all zero",
              dev.get("traffic") == {"messages": 0, "ledger": 0, "tasks": 0,
                                     "rooms": 0, "friction": 0, "seals": 0},
              dev.get("traffic"))
        check("the active channel's traffic is counted per source",
              live.get("traffic") == {"messages": 1, "ledger": 1, "tasks": 1,
                                      "rooms": 0, "friction": 0, "seals": 1},
              live.get("traffic"))
        check("last_activity is the newest record, not the manifest",
              live.get("last_activity") == "2026-09-22T01:00:03Z",
              live.get("last_activity"))

        print("== created / phase / participants are all on the channel ==")
        check("a channel records when it was created",
              dev.get("created_at") == "2026-09-20T00:00:00Z", dev.get("created_at"))
        check("a channel still states its phase",
              dev.get("phase") == "SEALED_DIVERGENT", dev.get("phase"))
        check("a channel still states its participants",
              dev.get("participants") == ["human", "codex"], dev.get("participants"))

        print("== idle channels are visible, not left looking alive ==")
        check("a channel idle past the threshold is dormant",
              chans["probe"].get("state") == "dormant", chans["probe"].get("state"))
        check("a channel one day idle is still active",
              chans["quiet"].get("state") == "active", chans["quiet"].get("state"))
        check("idle_days is exposed so a real calendar can override the threshold",
              chans["probe"].get("idle_days") == 17, chans["probe"].get("idle_days"))

        print("== a probe channel is distinguishable from a real project (T-0232) ==")
        check("a topic-declared scratch channel reads as scratch",
              chans["probe"].get("kind") == "scratch", chans["probe"].get("kind"))
        check("an ordinary channel reads as a project",
              chans["dev"].get("kind") == "project", chans["dev"].get("kind"))
        check("a manifest `kind` field wins over the topic fallback",
              chans["declared"].get("kind") == "scratch", chans["declared"].get("kind"))

        print("== the rule itself, called directly ==")
        counts = {"messages": 0, "ledger": 0, "tasks": 0,
                  "rooms": 0, "friction": 0, "seals": 0}
        empty = channel_lifecycle(manifest("x", "t", "2026-09-01T00:00:00Z"),
                                  counts, "", date(2026, 9, 22))
        check("zero traffic is empty", empty["state"] == "empty", empty)
        check("an empty channel falls back to created_at for last_activity",
              empty["last_activity"] == "2026-09-01T00:00:00Z", empty["last_activity"])
        busy = dict(counts, messages=1)
        dormant = channel_lifecycle(manifest("x", "t", "2026-09-01T00:00:00Z"),
                                    busy, "2026-09-10T00:00:00Z", date(2026, 9, 22))
        check("traffic older than the threshold is dormant",
              dormant["state"] == "dormant", dormant)
        boundary = channel_lifecycle(
            manifest("x", "t", "2026-09-01T00:00:00Z"), busy,
            "2026-09-20T00:00:00Z", date(2026, 9, 22))
        check("the threshold is inclusive and is the documented constant",
              boundary["state"] == "dormant" and DORMANT_AFTER_DAYS == 2, boundary)
        fresh = channel_lifecycle(manifest("x", "t", "2026-09-01T00:00:00Z"),
                                  busy, "2026-09-22T00:00:00Z", date(2026, 9, 22))
        check("traffic inside the threshold is active",
              fresh["state"] == "active" and fresh["idle_days"] == 0, fresh)
        check("a kind the manifest declares is never re-derived",
              channel_kind({"topic": "scratch: x", "kind": "project"}) == "project")

        print("== the classification is derived, not a stored field ==")
        check("no manifest carries a lifecycle field the board would just read",
              all("state" not in c["manifest"] for c in state["channels"]))
        # Add one message to `dev` with no manifest edit: the answer must change.
        jsonl(root / "channels" / "dev" / "log.jsonl",
              [{"ts": "2026-09-22T03:00:00Z", "from": "codex", "body": "traffic"}])
        again = by_id(load_fabric(root, [], date(2026, 9, 22)))
        check("a session moving work into dev changes the answer with no hand edit",
              again["dev"]["state"] == "active", again["dev"]["state"])
    finally:
        shutil.rmtree(work, ignore_errors=True)

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("failed:")
        for name in failed:
            print(f"  - {name}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
