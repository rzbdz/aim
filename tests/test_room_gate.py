"""The room gate, adversarially: what actually decides whether a peer may read a room?

T-0198's acceptance is "the room leak is tested by an angle nobody proposed in the
design note". The angle here is that the gate does not read the channel's phase at
all. `visible_rooms` (aimboard/gate.py:77) asks one question --

    room["visibility"] != "published"

-- so what protects a room during SEALED_DIVERGENT is a string in the room's own
JSON file, not the barrier. `design/06` says the opposite: a room created while the
parent channel is in a divergence phase is a draft room, and publishing it is
`aim room publish`, "deliberate, recorded, and visible on the board". That verb
does not exist, so the only way to set the string is to write the file by hand,
which is neither recorded nor on the board.

Measured, on a throwaway AIM_ROOT, channel in SEALED_DIVERGENT:

    room file                        peer (beta)   leader
    no `visibility` field            hidden        visible
    visibility: "Pubished" (typo)    hidden        visible
    visibility: "published"          VISIBLE       visible

So the gate is fail-closed against accidents and open against the one deliberate
value -- and no verb can produce that value. This file pins all three rows, because
the first two are the reason the third is a finding rather than a shrug.

Run: python3 tests/test_room_gate.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"
BOARD = ROOT / "bin" / "aimboard.py"

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def norm(text):
    return re.sub(r"\s+", " ", text.replace("\\n", " ")).strip()


TOKENS = {
    "nofield": "ROOMTOKEN-NO-VISIBILITY-FIELD",
    "typo": "ROOMTOKEN-TYPOGRAPHIC-VISIBILITY",
    "pub": "ROOMTOKEN-PUBLISHED",
}

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    env = dict(os.environ, AIM_ROOT=str(root))

    def run(*argv):
        return subprocess.run([sys.executable, str(AIM), *argv], capture_output=True,
                              text=True, env=env, timeout=60)

    run("init")
    for who, kind in (("alpha", "claude"), ("beta", "codex"), ("leader", "human")):
        run("register", "--as", who, "--kind", kind, "--session", "room gate test")
    out = run("new-channel", "--id", "ch", "--topic", "room gate",
              "--participants", "alpha,beta", "--leader", "leader")
    check("the test channel is in a divergence phase (or this proves nothing)",
          "SEALED_DIVERGENT" in out.stdout, out.stdout + out.stderr)

    rooms = root / "channels" / "ch" / "rooms"
    rooms.mkdir(parents=True, exist_ok=True)

    def message(body):
        return {"ts": "2026-09-22T00:00:01Z", "agent": "alpha", "body": body,
                "hash": "h1", "prev": "genesis"}

    for rid, meta in (("nofield", {}),
                      ("typo", {"visibility": "Pubished"}),
                      ("pub", {"visibility": "published"})):
        (rooms / f"{rid}.jsonl").write_text(json.dumps(message(TOKENS[rid])) + "\n")
        (rooms / f"{rid}.json").write_text(json.dumps({"id": rid, "topic": rid, **meta}))

    proc = subprocess.Popen([sys.executable, "-u", str(BOARD), "serve", "--root", str(root),
                             "--port", "0", "--as-of", "2026-09-21"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url, said, deadline = None, [], time.time() + 30
    while time.time() < deadline:
        said.append(proc.stdout.readline())
        m = re.search(r"http://[\d.]+:(\d+)/", "".join(said))
        if m:
            url = f"http://127.0.0.1:{m.group(1)}"
            break
    check("board serves", url is not None, "".join(said)[-200:])
    try:
        seen = {}
        for who in ("alpha", "beta", "leader"):
            with urllib.request.urlopen(f"{url}/api/state?as={who}", timeout=20) as fh:
                blob = norm(fh.read().decode())
            seen[who] = {k: (v in blob) for k, v in TOKENS.items()}
        print(f"        alpha(author)={seen['alpha']}\n"
              f"        beta(peer)   ={seen['beta']}\n"
              f"        leader       ={seen['leader']}")

        check("no visibility field -> the peer cannot read it (the default is draft)",
              seen["beta"]["nofield"] is False)
        check("a misspelled visibility -> the peer cannot read it (anything but the exact string is draft)",
              seen["beta"]["typo"] is False)
        check("THE FINDING: visibility 'published' alone lets a peer read a divergence-phase room",
              seen["beta"]["pub"] is True)
        check("the leader reads all three, as the policy says they should",
              all(seen["leader"].values()))
        # The row design/06 §2 names first, and the one `visible_tasks` already
        # implements (gate.py:70). Alpha wrote every message in each room here,
        # which is the only authorship evidence that reaches the gate: `fabric.py`
        # reads `rooms/<room>.json` but forwards id/topic/visibility/messages/
        # unread/mentions, so a declared `author` never arrives.
        check("design/06 §2: the AUTHOR reads their own draft room during divergence",
              seen["alpha"]["nofield"] and seen["alpha"]["typo"],
              "visible_rooms() has no author exemption, so alpha cannot read the room "
              "alpha wrote; walled_off() is true for any participant in a divergence phase")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

print(f"\n{passed}/{passed + failed} checks passed")
print("The three rows above are the review. A fix that names the channel's phase would")
print("make the fourth row false and would also take `aim task publish` with it -")
print("gate.py:77 and gate.py:68 are the same two lines, and design/05 §1 and design/06")
print("§2 both specify a deliberate early publish. See reviews/07-room-gate-decision.md.")
print("The author row is pinned because it was the omitted half: a fix must not weaken")
print("the peer row to grant it.")
sys.exit(1 if failed else 0)
