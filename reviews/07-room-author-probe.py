#!/usr/bin/env python3
"""design/06 says a draft room is readable by its author. Is it?

`design/06-group-chat.md` §2: "Its messages are readable by their author and by the leader, and
by nobody else, enforced in `aim` and recorded by the same refusal path as a cross-read."

`tests/test_room_gate.py` pins the peer row and the leader row. It does not pin the author row,
which is the one the sentence names first. This probe adds that row, using the same fixture.

Read-only apart from a throwaway AIM_ROOT under /tmp and a board on a random port.
Run: python3 reviews/07-room-author-probe.py
"""
import json, os, re, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM, BOARD = ROOT / "bin" / "aim", ROOT / "bin" / "aimboard.py"
TOK = {"nofield": "ROOMTOKEN-NO-FIELD", "typo": "ROOMTOKEN-TYPO", "pub": "ROOMTOKEN-PUB"}
passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1; print(f"  PASS  {name}")
    else:
        failed += 1; print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def norm(t):
    return re.sub(r"\s+", " ", t.replace("\\n", " ")).strip()


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    env = dict(os.environ, AIM_ROOT=str(root))

    def run(*a):
        return subprocess.run([sys.executable, str(AIM), *a], capture_output=True,
                              text=True, env=env, timeout=60)

    run("init")
    for who, kind in (("alpha", "claude"), ("beta", "codex"), ("leader", "human")):
        run("register", "--as", who, "--kind", kind, "--session", "room author probe")
    out = run("new-channel", "--id", "ch", "--topic", "t", "--participants", "alpha,beta",
              "--leader", "leader")
    # A genuine bug in this probe, found by hitting it: the setup calls above
    # ignore rc, so when a concurrent agent left `bin/aim` mid-write the channel
    # was never created and every viewer -- the leader included -- came back
    # blind. That printed "2/4" with a FAIL naming the author gate, i.e. a
    # confident verdict about the wrong cause. Guard the premise instead.
    if not (root / "channels" / "ch" / "manifest.json").exists() or \
            "SEALED_DIVERGENT" not in out.stdout:
        print("  SETUP FAILED: the throwaway channel was not created, so any verdict here\n"
              "  would name the wrong cause (is `bin/aim` mid-edit?). `aim` said:\n"
              f"  rc={out.returncode} out={out.stdout.strip()!r} err={out.stderr.strip()!r}")
        sys.exit(2)
    rooms = root / "channels" / "ch" / "rooms"
    rooms.mkdir(parents=True, exist_ok=True)
    for rid, meta in (("nofield", {}), ("typo", {"visibility": "Pubished"}),
                      ("pub", {"visibility": "published"})):
        (rooms / f"{rid}.jsonl").write_text(json.dumps(
            {"ts": "2026-09-22T00:00:01Z", "agent": "alpha", "body": TOK[rid],
             "hash": "h1", "prev": "genesis"}) + "\n")
        (rooms / f"{rid}.json").write_text(json.dumps({"id": rid, "topic": rid, **meta}))

    proc = subprocess.Popen([sys.executable, "-u", str(BOARD), "serve", "--root", str(root),
                             "--port", "0", "--as-of", "2026-09-21"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url, said, deadline = None, [], time.time() + 30
    while time.time() < deadline:
        said.append(proc.stdout.readline())
        m = re.search(r"http://[\d.]+:(\d+)/", "".join(said))
        if m:
            url = f"http://127.0.0.1:{m.group(1)}"; break
    check("board serves", url is not None, "".join(said)[-200:])
    try:
        seen = {}
        for who in ("alpha", "beta", "leader"):
            with urllib.request.urlopen(f"{url}/api/state?as={who}", timeout=20) as fh:
                blob = norm(fh.read().decode())
            seen[who] = {k: (v in blob) for k, v in TOK.items()}
        print(f"        alpha(author)={seen['alpha']}\n"
              f"        beta(peer)   ={seen['beta']}\n"
              f"        leader       ={seen['leader']}")
        check("design/06 §2: the AUTHOR can read their own draft room",
              seen["alpha"]["nofield"] and seen["alpha"]["typo"],
              "a draft room is invisible to the agent that wrote it: walled_off() is true for a "
              "participant in a divergence phase and visible_rooms() has no author exemption, "
              "unlike visible_tasks() (gate.py:69)")
        check("design/06 §2: and by nobody else -- the peer still cannot",
              not seen["beta"]["nofield"] and not seen["beta"]["typo"])
        check("design/06 §2: the leader still reads everything",
              all(seen["leader"].values()))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

print(f"\n{passed}/{passed + failed} checks passed")
sys.exit(1 if failed else 0)
