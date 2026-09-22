#!/usr/bin/env python3
"""Does the T-0110 workspace guard see reality, or only a declaration?

T-0110 (`done`, owner claude-session1) created `assert_barrier_defensible` (bin/aim:437) and
`_workspace_conflicts` (bin/aim:393). Its acceptance: "a manifest may declare workspace; if two
participants share a writable one, a divergence phase on that channel is REFUSED ... a test opens
a divergence phase on such a channel and expects the refusal".

Two cases, on a throwaway AIM_ROOT:

  A  two participants really do write to the same directory, nothing is declared
     -> does the tool notice?  (it cannot: _workspace_conflicts reads manifest["workspace"] only)
  B  the same fact, declared
     -> does the refusal fire?  (it should)

Case A is the one that matters, because `channels/hello/manifest.json` has no `workspace` key and
`hello` is in COMMIT, while both of its participants work in this checkout.

Read-only apart from a temp root. Run: python3 reviews/08-workspace-guard-probe.py
"""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"
passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1; print(f"  PASS  {name}")
    else:
        failed += 1; print(f"  FAIL  {name}" + (f"     {detail}" if detail else ""))


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "fabric"
    shared = Path(tmp) / "shared-checkout"
    shared.mkdir()
    env = dict(os.environ, AIM_ROOT=str(root))

    def run(*a):
        return subprocess.run([sys.executable, str(AIM), *a], capture_output=True,
                              text=True, env=env, timeout=60)

    run("init")
    for who, kind in (("alpha", "claude"), ("beta", "codex"), ("leader", "human")):
        run("register", "--as", who, "--kind", kind, "--session", "ws probe")
    run("new-channel", "--id", "ch", "--topic", "t", "--participants", "alpha,beta",
        "--leader", "leader")

    # both participants really edit the same checkout, before anyone seals
    (shared / "bin").mkdir()
    (shared / "bin" / "aim").write_text("# alpha edits this file\n")
    (shared / "bin" / "aim").write_text("# beta edits the same file, having read alpha's\n")

    claims = Path(tmp) / "claims.json"
    claims.write_text(json.dumps([{"id": "c1", "claim": "x", "confidence": "low",
                                   "kill_if": "y"}]))
    for who in ("alpha", "beta"):
        run("seal", "--as", who, "--channel", "ch", "--summary", "s",
            "--claims", str(claims))

    # --- case A: the fact is real and undeclared ---
    a = run("advance", "--as", "leader", "--channel", "ch", "--to", "COMMIT")
    undeclared_refused = "declares a shared workspace" in (a.stdout + a.stderr)
    check("A: an UNDECLARED shared workspace is invisible to the guard (it advances)",
          not undeclared_refused and a.returncode == 0,
          f"rc={a.returncode} out={(a.stdout + a.stderr).strip()[:220]}")

    # --- case B: the same fact, declared, on a fresh channel ---
    run("new-channel", "--id", "ch2", "--topic", "t2", "--participants", "alpha,beta",
        "--leader", "leader")
    # measured: a participant may NOT declare it -- "'alpha' may not change the channel's
    # declaration. only the human team leader 'leader' controls phase transitions."
    as_agent = run("channel", "workspace", "--as", "alpha", "--channel", "ch2",
                   "--set", f"alpha={shared}", "--set", f"beta={shared}")
    check("B0: a participant cannot declare the shared workspace (leader-only)",
          "only the human team leader" in (as_agent.stdout + as_agent.stderr),
          (as_agent.stdout + as_agent.stderr).strip()[:160])
    d = run("channel", "workspace", "--as", "leader", "--channel", "ch2",
            "--set", f"alpha={shared}", "--set", f"beta={shared}")
    declared = "workspace recorded" in (d.stdout + d.stderr)
    print(f"        leader declaration output: {(d.stdout + d.stderr).strip()[:150]}")
    for who in ("alpha", "beta"):
        run("seal", "--as", who, "--channel", "ch2", "--summary", "s",
            "--claims", str(claims))
    b = run("advance", "--as", "leader", "--channel", "ch2", "--to", "COMMIT")
    btext = b.stdout + b.stderr
    check("B: a DECLARED shared workspace is refused when a divergence phase is requested",
          declared and b.returncode != 0 and "declares a shared workspace" in btext,
          f"declared={declared} rc={b.returncode} out={btext.strip()[:240]}")
    check("B: and the refusal names the manifest and the path (design/07 §7)",
          str(shared) in btext and "claim the tool cannot keep" in btext)
    check("B: and names both participants",
          "alpha" in btext and "beta" in btext)

print(f"\n{passed}/{passed + failed} checks passed")
print("Case A is the finding: the guard's only input is the manifest "
      "(bin/aim:416 `manifest.get(\"workspace\")`), so a shared checkout that nobody")
print("declares is indistinguishable from independent work -- and the docstring of")
print("_workspace_conflicts names channels/hello as the reason it exists.")
sys.exit(1 if failed else 0)
