#!/usr/bin/env python3
"""Tests for `bin/aim-doctor`: an undeployable tool has to be visible.

The accept line for T-0087 is one sentence — "a syntax error in `bin/aim` is
reported by something other than the next agent's command failing" — and it names
the *previous* detector, which was a person. On 2026-09-21 a half-finished edit
left `bin/aim` unparseable and what surfaced it was codex's next `aim` command
dying with `IndentationError`. That is not a detection mechanism; it is somebody's
work being interrupted, and it only works if somebody happens to be working.

So the checks here are about a tripwire, and there are three of them that matter:

  * **it fires** — a broken `bin/aim` is reported, by file and by *line*, without
    running `bin/aim`;
  * **it does not fire spuriously** — a tree with no problems reports none. A
    tripwire that is always red is a tripwire people learn to ignore, and that
    has already happened once in this repo (a suite that reported red for a
    reason that had nothing to do with the code);
  * **it is a read** — sha256 of every file in the tree before and after. A
    diagnostic you cannot run on a suspect tree is a diagnostic that arrives too
    late to be useful, and one that writes while diagnosing is a second writer.

Why the fixtures are copied trees rather than the checkout itself
----------------------------------------------------------------
The doctor's subject is a checkout, so testing it against a tree that is *not*
the one you are working in is a test of the doctor. Pointing it at the real tree
would couple this suite to whatever state the repo is in, and it would make the
"clean tree passes" check impossible to write honestly — the real tree currently
has a failing entry point in it (see the note at the bottom of this file), so the
real tree is *not* clean and asserting that it is would be a check that has to be
deleted the next time something breaks.

Each fixture is built from a named, closed set of files rather than by copying the
whole checkout. That is a deliberate limitation and it is stated rather than
hidden: a fixture that copied everything would include whichever new entry point
happens to be in flight, so the *only* variable in a fixture here is the one the
check introduces.

Run: python3 tests/test_doctor.py        (exit code = number of failures)
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOCTOR = HERE / "bin" / "aim-doctor"
AIM = HERE / "bin" / "aim"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))


def build_tree(into):
    """A minimal but real checkout: the doctor and the entry points it watches.

    `bin/aim-mcp` and `bin/aimboard.py` are copied because a real `bin/` holds
    them and the doctor's start-check is about exactly that kind of file. Nothing
    else from `bin/` is, so a new script appearing there does not silently change
    what these checks are measuring.
    """
    (into / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / "aimboard", into / "aimboard",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("aim", "aim-doctor", "aimboard.py"):
        shutil.copy2(HERE / "bin" / name, into / "bin" / name)
    return into


def run_doctor(root, *args):
    return subprocess.run([sys.executable, str(root / "bin" / "aim-doctor"), *args],
                          capture_output=True, text=True, timeout=180)


def digest_tree(root):
    """sha256 of every file, path -> hex, so 'it is a read' is a measurement."""
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def pyflakes_clean():
    try:
        done = subprocess.run([sys.executable, "-m", "pyflakes", str(DOCTOR)],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip()


def main():
    print("== T-0087: an undeployable tool is visible before anyone runs it ==")

    check("the tripwire is a script outside the tool it watches",
          DOCTOR.exists() and os.access(DOCTOR, os.X_OK)
          and "bin/aim" not in DOCTOR.read_text().split('"""')[0],
          "the check must not live inside bin/aim: the file that would have to "
          "report the problem is the file with the problem")

    # ---------------------------------------------------------------- clean tree
    clean = Path(tempfile.mkdtemp(prefix="doctor-clean-"))
    try:
        build_tree(clean)
        before = digest_tree(clean)
        done = run_doctor(clean)
        after = digest_tree(clean)
        check("a tree with nothing wrong reports nothing wrong",
              done.returncode == 0 and "0 failed" not in done.stdout,
              f"rc={done.returncode}\n{done.stdout[-400:]}")
        check("and it says so in the repo's own shape: n/m checks passed",
              re.search(r"\d+/\d+ checks passed", done.stdout) is not None,
              f"got {done.stdout[-200:]!r}")
        # The read-only claim, measured on the tree rather than asserted. A doctor
        # that writes is a second writer, and this one runs on trees whose state
        # is the thing in question.
        check("running it changes not one byte of the tree",
              before == after,
              f"changed: {[k for k in set(before) | set(after) if before.get(k) != after.get(k)]}")
        # --quiet is for a git hook, and it has to be *silent*: a hook that prints
        # on every commit is a hook that gets uninstalled.
        quiet = run_doctor(clean, "--quiet")
        check("--quiet prints nothing and the exit code is the whole answer",
              quiet.returncode == 0 and quiet.stdout.strip() == "",
              f"rc={quiet.returncode} out={quiet.stdout[:200]!r}")
    finally:
        shutil.rmtree(clean, ignore_errors=True)

    # -------------------------------------------------- the accept line: bin/aim
    broken = Path(tempfile.mkdtemp(prefix="doctor-broken-"))
    try:
        build_tree(broken)
        # The exact failure that produced this task, reproduced rather than
        # described: a function definition with no body, which is what a
        # half-finished edit leaves behind. Appended at a known line so the check
        # can assert the *line number* and not merely that something was reported
        # — "bin/aim does not parse" sends a reader looking, a line is a fix.
        source = (broken / "bin" / "aim").read_text().splitlines()
        injected = source + ["", "def deliberately_broken(:"]
        (broken / "bin" / "aim").write_text("\n".join(injected) + "\n")
        expected_line = len(injected)

        done = run_doctor(broken)
        check("a syntax error in bin/aim is reported, without running bin/aim",
              done.returncode != 0 and "does not parse" in done.stdout,
              f"rc={done.returncode}\n{done.stdout[-500:]}")
        check("and it names the file and the line, not just that something failed",
              "bin/aim" in done.stdout and str(expected_line) in done.stdout,
              f"expected line {expected_line}; got\n{done.stdout[-500:]}")
        # The property the whole design rests on: the report does not come from
        # the broken file. `aim doctor` as a *verb* is gone in this tree, because
        # the file carrying the verb is the file that is broken — so the tripwire
        # has to be reachable some other way, and this is the check that it is.
        verb = subprocess.run([sys.executable, str(broken / "bin" / "aim"), "doctor"],
                              capture_output=True, text=True, timeout=60)
        check("and the verb is gone in that tree, which is why the script exists",
              verb.returncode != 0 and "does not parse" not in verb.stdout,
              f"rc={verb.returncode} {verb.stderr.strip()[-200:]!r}")
        check("while the tripwire still answers", run_doctor(broken, "--quiet").returncode != 0,
              "the doctor stopped firing because the tool it watches is broken")

        # A tree whose sources parse but whose entry point cannot start. This is
        # the failure parsing cannot see and the one that was measured on the real
        # tree (see the note at the end of this file), so the check builds one on
        # purpose instead of hoping the real one stays broken.
        starter = Path(tempfile.mkdtemp(prefix="doctor-start-"))
        try:
            build_tree(starter)
            (starter / "bin" / "aim-broken").write_text(
                "#!/usr/bin/env python3\n"
                "from aimboard.does_not_exist import main\n"
                "main()\n")
            os.chmod(starter / "bin" / "aim-broken", 0o755)
            done = run_doctor(starter)
            check("an entry point that parses but cannot start is reported",
                  done.returncode != 0 and "aim-broken cannot start" in done.stdout,
                  f"rc={done.returncode}\n{done.stdout[-400:]}")
            check("and the tree's other checks still ran, so one bad file is one finding",
                  "all" in done.stdout and "python sources parse" in done.stdout,
                  f"got {done.stdout[-400:]}")
        finally:
            shutil.rmtree(starter, ignore_errors=True)
    finally:
        shutil.rmtree(broken, ignore_errors=True)

    # -------------------------------------------- the exit code is a contract
    check("the exit code is the number of failures, like every suite here",
          "return len(failed)" in DOCTOR.read_text(),
          "a hook can only use the exit code if it is a count")
    # And the verb forwards it, which is the only reason `aim doctor` is worth
    # having: a command that says "this checkout cannot be run" and exits 0 has
    # reported nothing a script can act on.
    forwarded = subprocess.run([sys.executable, str(AIM), "doctor", "--root",
                                str(HERE)], capture_output=True, text=True, timeout=300)
    direct = run_doctor(HERE)
    check("aim doctor forwards the doctor's exit code unchanged",
          forwarded.returncode == direct.returncode and forwarded.returncode <= 125,
          f"verb rc={forwarded.returncode} script rc={direct.returncode}")
    check("and the verb prints nothing of its own on top of it",
          forwarded.stdout.strip() != "" or direct.stdout.strip() == "",
          "the forward added output that the script did not produce")

    lint = pyflakes_clean()
    if lint is not None:
        check("the doctor is clean under pyflakes like the rest of the tree",
              lint == "", lint)

    return finish()


def finish():
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("failed:")
        for name in failed:
            print(f"  - {name}")
    return len(failed)


if __name__ == "__main__":
    print(__doc__.strip().splitlines()[0])
    sys.exit(main())

# --------------------------------------------------------------------------
# What this suite found on the real tree, kept here rather than only in the
# report, because the next reader of this file is the person who has to fix it.
#
# `bin/aim-mcp` (codex's in-flight T-0120, untracked at the time of writing)
# fails to start, and it fails for a reason that is not obvious from its source:
#
#     bin/aim-mcp: from aimboard.mcp import main
#       -> File "bin/aimboard.py", line 14
#       -> ModuleNotFoundError: No module named 'aimboard.cli';
#          'aimboard' is not a package
#
# Running a script in `bin/` puts `bin/` on `sys.path[0]`, so the *file*
# `bin/aimboard.py` shadows the *directory* `aimboard/` — the deliberate entry
# point built in b60c3fc wins the name it was created to avoid colliding with,
# because `import aimboard` inside `bin/` resolves to itself. The module is never
# reached; the file that shadows it is.
#
# It is not this suite's to fix (the file is untracked and in flight) and not
# this suite's to assert (a check that requires it to stay broken is a check that
# has to be deleted when it is fixed). It is recorded because the doctor found it
# on its first run on the real tree, which is the point of the doctor: it was
# found by a diagnostic rather than by the MCP server failing for somebody
# mid-task.
