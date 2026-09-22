"""No message body reaches a reader who is not a party to it.

T-0199, re-measured as a test rather than as a one-off probe. The acceptance
sentence was "no outbox body string appears anywhere in the rendered HTML", and
this file holds it to that on a throwaway AIM_ROOT, so the check does not depend
on whatever happens to be in the live fabric's mailboxes.

Two false negatives this file was written to avoid, both measured while probing
the live board first:

  * the body arrives JSON-escaped, so a needle taken from the raw file -- with its
    real newlines -- does not match the payload even when the body is plainly
    there. Every string is normalised before it is searched for.
  * a message from A to B lives in `outbox/B/`, so a needle keyed on the sender's
    own path silently searches for the wrong mail. The path is not used as the
    signal at all here: the token is injected and then searched for.

Run: python3 tests/test_mail_gate.py
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
    """Whitespace-folded, JSON-unescaped text. Both sides go through this."""
    return re.sub(r"\s+", " ", text.replace("\\n", " ").replace('\\"', '"')).strip()


def run(env, *argv, expect=0):
    p = subprocess.run([sys.executable, str(AIM), *argv], capture_output=True,
                       text=True, env=env, timeout=60)
    if expect is not None and p.returncode != expect:
        print(f"        (setup) aim {' '.join(argv)} -> rc {p.returncode}\n{p.stdout}{p.stderr}")
    return p


def serve(root, *extra):
    proc = subprocess.Popen([sys.executable, "-u", str(BOARD), "serve", "--root", str(root),
                             "--port", "0", "--as-of", "2026-09-21", *extra],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    said, deadline = [], time.time() + 30
    while time.time() < deadline:
        said.append(proc.stdout.readline())
        if proc.poll() is not None:
            break
        m = re.search(r"http://[\d.]+:(\d+)/", "".join(said))
        if m:
            return f"http://127.0.0.1:{m.group(1)}", proc
    return None, proc


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as fh:
        return fh.read().decode("utf-8")


TOKEN = "ZQ7F4M2XRV8K1TWB-this-token-must-not-be-readable-by-a-bystander"
TOKEN2 = "HP3N9C5DJ2QW7LY-the-bystander-s-own-mail-which-they-must-see"

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    env = dict(os.environ, AIM_ROOT=str(root))
    run(env, "init")
    for agent, kind in (("alpha", "claude"), ("beta", "codex"),
                        ("bystander", "claude"), ("leader", "human")):
        run(env, "register", "--as", agent, "--kind", kind, "--session", "mail-gate test")
    run(env, "new-channel", "--id", "ch", "--topic", "mail gate",
        "--participants", "alpha,beta", "--leader", "leader")
    run(env, "push", "--as", "alpha", "--to", "beta", "--channel", "ch",
        "--subject", "private between two agents", "--body", f"body starts here {TOKEN} body ends here")
    # A second message to the bystander, so "they cannot see it" cannot be
    # satisfied by a payload that is empty for everyone. A gate that denies
    # everything passes the first assertion and fails this one.
    run(env, "push", "--as", "alpha", "--to", "bystander", "--channel", "ch",
        "--subject", "addressed to the bystander", "--body", f"their own mail {TOKEN2} ends here")

    print("== the gate, on a throwaway root ==")
    url, proc = serve(root)
    check("board serves on a throwaway root", url is not None)
    if not url:
        sys.exit(1)
    try:
        parties = {who: fetch(f"{url}/api/state?as={who}") for who in
                   ("alpha", "beta", "bystander", "leader")}
        shell = fetch(f"{url}/")

        check("the sender can read what they sent", TOKEN in norm(parties["alpha"]))
        check("the recipient can read what was sent to them", TOKEN in norm(parties["beta"]))
        check("the human leader can read it, by design (gate.conversation_view: 'leader: every message between agents')",
              TOKEN in norm(parties["leader"]))
        check("a bystander agent CANNOT read the body",
              TOKEN not in norm(parties["bystander"]))
        check("the SPA shell carries no message body at all", TOKEN not in norm(shell))
        check("the bystander still gets the record's shape, not its contents",
              '"mail"' in parties["bystander"] and '"conversation"' in parties["bystander"])
        # Selectivity: the gate withholds the one body and delivers the other.
        # Without this pair, "deny everything" would pass every check above.
        check("the bystander CAN read mail addressed to them (so the denial above is selective)",
              TOKEN2 in norm(parties["bystander"]))
        check("and beta cannot read the bystander's mail either",
              TOKEN2 not in norm(parties["beta"]))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

print(f"\n{passed}/{passed + failed} checks passed")
sys.exit(1 if failed else 0)
