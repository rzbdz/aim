"""A `bin/aim` citation must resolve at the revision this document declares.

This file exists because the same defect was found five times in one session, by
three different readers, and every time the fix was one line and the *reason* was
the same: `bin/aim` line numbers move whenever anything above them is edited, and
this document carries 69 of them. Two of the five were worse than a stale number:

  * a pair inside one clause taken at two different revisions (`:3724`/`:3829`
    were correct at HEAD and pointed at a matrix computation at the declared
    base) -- the pair looked consistent because both numbers were real;
  * a line number cited for the *object* when the object sat three lines away,
    which reads correctly at neither revision.

None of these are caught by reading, because reading is what produced them. The
document already declares its base in its third line, so the base can be checked
mechanically, and that is all this file does.

Three failure classes, in the order they bite:

  1. the declared base cannot be read (no declaration, or a commit git does not
     have) -- without it every other check is meaningless, so it fails first;
  2. a cited line is outside the file at that base -- the number is stale by more
     than the drift;
  3. a cited line carries no content at that base (blank, a lone bracket, or a
     bare `else:`/`pass`/`continue`/`return`) -- the number is off by a little,
     which is the shape a one-sided edit produces.

The drift to the working tree is *not* a failure: the document names the tree it
was measured at, and re-pinning 69 citations is a separate act. It is printed, so
that a reader who opens the file today knows how far they are from the numbers.

Run: python3 tests/test_sop_citations.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOP = ROOT / "SOP.md"
AIM_REL = "bin/aim"

passed = failed = 0
warnings = []


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def show(ref):
    """`bin/aim` at a revision, as a list of lines."""
    out = subprocess.run(["git", "show", f"{ref}:{AIM_REL}"], cwd=ROOT,
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return out.stdout.splitlines()


def contentless(line):
    """A line a citation cannot be pointing at.

    Comments are *not* contentless: several citations in the document name a
    comment on purpose, because the comment is where a rule is stated. What is
    excluded is the lines that mean nothing on their own -- which is what a
    citation lands on when the object it names was pushed down by a few lines.
    """
    t = line.strip()
    return t in ("", ")", "}", "]", "else:", "try:", "pass", "continue") or t == ""


text = SOP.read_text(encoding="utf-8")
lines = text.splitlines()

# ---------------------------------------------------------------- declarations
m = re.search(r"measured at \*\*`([0-9a-f]{7,40})`\*\*", text)
check("the document declares the revision its measurements are taken at",
      m is not None,
      "no `measured at **`<sha>`**` in the header")
base_ref = m.group(1) if m else None

base = show(base_ref) if base_ref else None
check(f"and git has it ({base_ref})", base is not None,
      f"`git show {base_ref}:{AIM_REL}` failed")
if base is None:
    print(f"\n{passed}/{passed + failed} checks passed")
    sys.exit(1)
print(f"  ..    base {base_ref}: {len(base)} lines in {AIM_REL}")

# ------------------------------------------------------------------ citations
# A citation is an explicit `bin/aim:NNN`, plus any bare `:NNN` on the same line
# as a `bin/aim:` mention -- the continuation form this document uses throughout
# (`bin/aim:556`, `:1075`, `:1473`). The second form is only counted when the
# line names the file, so a `:NNN` about a different file is not swallowed.
# The continuation form is `:NNN` *at the head of a run* -- `bin/aim:556`, `:1075`
# -- and the scanner says so, because the document also uses `:NNN` in the middle
# of a sentence to mean "and also the line numbered", which is a mention and not a
# citation. Getting this wrong once made the check fail on a sentence that said
# "the working-tree lines are `:3287`, `:3338` ..." while declaring its own base in
# the same clause, which is the opposite of the defect this file is for.
cited = {}
for i, line in enumerate(lines, 1):
    for found in re.finditer(r"`bin/aim:(\d+)`", line):
        cited.setdefault(int(found.group(1)), []).append(i)
    # every `:NNN` on a line that names bin/aim, except one that follows a word
    # ("at lines `:3287`", "namely `:1234`") -- a citation is the head of the run.
    for found in re.finditer(r"(?<![A-Za-z] )`(?::)(\d+)`", line):
        if "bin/aim:" in line:
            cited.setdefault(int(found.group(1)), []).append(i)

check("the document cites lines in `bin/aim` at all", len(cited) > 50,
      f"only {len(cited)} distinct lines found -- the scan is probably wrong")

out_of_range = {n: at for n, at in cited.items() if not (1 <= n <= len(base))}
check("every cited line exists in the file at that base", not out_of_range,
      "; ".join(f":{n} (cited at :{at[0]})" for n, at in sorted(out_of_range.items())))

empty = {n: at for n, at in cited.items()
         if 1 <= n <= len(base) and contentless(base[n - 1])}
check("and every one of them carries content, not a stray bracket or a bare `else:`",
      not empty,
      "; ".join(f":{n} -> {base[n - 1].strip()!r} (cited at :{at[0]})"
                for n, at in sorted(empty.items())))

# --------------------------------------------------------------- the worst one
# The two-revision pair: a citation pair in one clause is only coherent if both
# members are read at the same base, so a clause whose two numbers are correct at
# *different* revisions is the failure this file was written for and it is
# invisible to both checks above -- `:3724` and `:3829` were both real lines with
# content at the base, and both correct at HEAD. There is no general test for
# "does this number mean what the sentence says" -- that is what reading is for.
# What is testable is the consequence: a cited line that is *identical* at the
# base and at the working tree cannot have moved, so the citations that are still
# safe to read without a checkout are exactly those. Reported, not asserted.
work = show("HEAD") or []


stable = [n for n in cited if n <= len(work) and work[n - 1] == base[n - 1]]
print(f"  ..    {len(stable)} of {len(cited)} cited lines are byte-identical at "
      f"{base_ref[:7]} and at HEAD ({len(work)} lines)")

# The identifier check: a citation usually names its object in the prose right
# beside it, so if *none* of the backticked identifiers on that line appears
# anywhere in a window around the cited line, the number is probably pointing at
# the wrong place. This is the check that would have caught the `:1982`/`:1979`
# pair, where `accept` and `owner` are three lines apart in one dict literal.
#
# Reported as a warning, never a failure, and its precision is worth stating
# because it was measured rather than assumed: at the revision this was written
# it reports 7 candidates, of which 3 are real (`:2079` at doc line 385, `:1934`
# at 2253, `:1477` at 1330 -- in each case the cited line is inside the right
# function and off by 13, 27 and 41 lines) and 4 are artifacts of the prose: one
# names the object in words rather than backticks, one names it in a parenthetical
# three clauses later, and one is `exporters.py:174` on a line that also contains
# a `bin/aim:` citation, which this scanner then counts as a `bin/aim:174`.
near_miss = []
for n, at in sorted(cited.items()):
    if not (1 <= n <= len(base)):
        continue
    src = lines[at[0] - 1]
    ids = [t for t in re.findall(r"`([A-Za-z_][A-Za-z0-9_]{2,})`", src)
           if t not in ("bin", "aim", "line", "lines")]
    if not ids:
        continue
    window = "\n".join(base[max(0, n - 6):n + 5])
    if not any(i in window for i in ids):
        near_miss.append((n, at[0], ids[0]))

if near_miss:
    warnings.append(
        f"{len(near_miss)} citation(s) whose nearest named identifier does not "
        f"appear within 3 lines of the cited line: "
        + "; ".join(f":{n} wants `{i}` (cited at :{at})" for n, at, i in near_miss[:8])
        + (" …" if len(near_miss) > 8 else ""))

# ---------------------------------------------------------------- the check itself
# A check that cannot fail is worse than no check, so this file demonstrates its
# own failure mode on an injected citation instead of asking the reader to trust
# it. On the real document the test above proves nothing about whether it
# *detects* the defect; here it does, on a copy held in memory, with the document
# on disk untouched.
def _inject(txt, old, new):
    assert txt.count(old) == 1, f"the injection anchor moved: {old!r}"
    return txt.replace(old, new, 1)


probe = _inject(text, "`bin/aim:3992`", "`bin/aim:4506`")
hit = []
for i, line in enumerate(probe.splitlines(), 1):
    for found in re.finditer(r"`bin/aim:(\d+)`", line):
        n = int(found.group(1))
        if 1 <= n <= len(base) and contentless(base[n - 1]):
            hit.append(n)
check("and it fires on a citation a one-sided edit pushed onto a blank line (self-test)",
      hit == [4506], f"the injected :4506 was not caught (caught: {hit})")

print(f"\n{passed}/{passed + failed} checks passed")
for w in warnings:
    print(f"\nWARN  {w}")
print(f"\nThe base is {base_ref}. {len(cited)} distinct lines are cited; "
      f"{len(cited) - len(stable)} have moved to {'HEAD' if work else 'the worktree'}, "
      f"which the header's own `measured at` covers and this file does not treat "
      f"as a defect.")
sys.exit(1 if failed else 0)
