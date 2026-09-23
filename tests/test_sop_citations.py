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

Four failure classes, in the order they bite:

  1. the declared base cannot be read (no declaration, or a commit git does not
     have) -- without it every other check is meaningless, so it fails first;
  2. a cited line is outside the file at that base -- the number is stale by more
     than the drift;
  3. a cited line carries no content at that base (blank, a lone bracket, or a
     bare `else:`/`pass`/`continue`/`return`) -- the number is off by a little,
     which is the shape a one-sided edit produces;
  4. a claim about *this document's own* lines, which is a different animal: it
     cannot be resolved against a base, because the reference dies with the edit
     that makes it. What is checkable is the sentence's shape -- the spelled
     number must match the citations listed, they must be in range, and when the
     sentence names a backticked mark word the list must be exactly the table
     rows above it whose *last* cell carries that word.

Class 4 was added after the class-1-through-3 machinery had been running green
for a day while a note in the document listed five `PROSE` cells and got three of
the five wrong -- one of them the marks glossary's *definition* of the word rather
than an instance of it. The last-cell rule is what decides that, and it is stated
in the body below.

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
# because it was measured rather than assumed: at this revision it reports 7
# candidates and **all seven are artifacts**, which is worth saying plainly
# because an earlier version of this comment claimed three were real. Each of the
# seven resolves correctly once you read what it is pointing at:
#
#   * `:56`, `:116`, `:117` -- a module-level constant (`PHASE_RULES`,
#     `TASK_STATUSES`, `TASK_FLOW`). There is no enclosing function to be near,
#     so "is the identifier close by" is the wrong question for these.
#   * `:1934`, `:2079`, `:1477` -- a `def` line exactly (`:1934` is
#     `cmd_task_new`), and two body lines that name their function in the prose
#     *beside* the citation and are in the right function at the base (`:2079` is
#     6 lines into `_load_task_or_die`, whose `def` is `:2073`; `:1477` is 27
#     lines into `cmd_advance`, whose `def` is `:1450`).
#   * `:3357` -- the doorbell cell, whose name reaches 69 lines up to `cmd_push`
#     because the cell spans the whole verb.
#
# So the check's own precision is zero at this revision: it names seven suspects
# and all seven are innocent. It is kept as a *pointer* rather than a finding --
# it is the list a human should read when the numbers move -- and the comment
# says so instead of quoting a hit rate it does not have.
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
        f"appear within 5 lines of the cited line (below): read these when the "
        f"numbers move -- at the revision this was written all of them resolve: "
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

# ------------------------------------------- the half about this document itself
# Everything above resolves references into `bin/aim`. This document also cites
# *itself*, and that half is where the numbers actually broke: a note listing the
# `PROSE` cells named three rows that had slid by one line and one that was the
# marks glossary's *definition* of the word rather than an instance of it, and no
# check anywhere could see either. A reference into `SOP.md` is invalidated by any
# edit above it -- including the edit making the reference -- so a self-citation
# cannot be validated against a base the way a `bin/aim` one can. What *is*
# decidable is the sentence's own shape, and it is decidable in two directions.
#
# A claim here looks like: "The cells whose mark word is `PROSE` above this
# paragraph are five -- `:166`, `:173`, `:2409`, `:2412`, `:2413`". So:
#
#   1. the spelled number must equal the number of citations listed;
#   2. every listed line must be inside this file;
#   3. when the sentence names a backticked mark word, the lines listed must be
#      exactly the table rows above the sentence whose *last* cell carries that
#      word -- and the last-cell rule is deliberate rather than incidental: the
#      glossary puts the word in its *first* cell because it is defining the
#      word, while a row the word is a verdict on carries it last. That single
#      rule is what separates the five instances from the definition, and it is
#      what the broken note got wrong.
SPELLED = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
           "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
           "thirteen": 13}
CLAIM = re.compile(r"\b(" + "|".join(SPELLED) + r")\s*—\s*"
                   r"((?:`:\d+`(?:,\s*|\s+and\s+)*)+)")
# char offset -> line number, so a claim that wraps across a line break still
# resolves to the line it starts on.
line_of = []
for i, line in enumerate(lines, 1):
    line_of.extend([i] * (len(line) + 1))

claims = []
for m in CLAIM.finditer(text):
    nums = [int(x) for x in re.findall(r"`:(\d+)`", m.group(2))]
    claims.append((line_of[m.start()], SPELLED[m.group(1)], m.group(1), nums,
                   text[text.rfind("\n", 0, m.start()) + 1:
                        text.find("\n", m.end())]))

check("this document makes claims about its own lines that can be checked",
      len(claims) >= 1, f"no `<spelled number> — <citations>` sentence found")

bad_count = [(ln, word, n, nums) for ln, n, word, nums, _ in claims if n != len(nums)]
check("and the spelled number in each one equals the number of lines it lists",
      not bad_count,
      "; ".join(f":{ln} says {word} and lists {len(nums)}" for ln, word, n, nums in bad_count))

out_of_doc = [n for _, _, _, nums, _ in claims for n in nums if not (1 <= n <= len(lines))]
check("and every self-citation points inside this file",
      not out_of_doc, f"line(s) do not exist in a {len(lines)}-line document: {out_of_doc}")


def mark_claim_failures(doc_text, doc_lines):
    """Every mark-word claim in `doc_text` whose list is not the rows that carry it.

    Takes the text and its lines as arguments rather than reading the globals, so
    the self-test below can run exactly this function on a mutated copy and prove
    it fires. A check that can only be exercised by breaking the real file is a
    check nobody will exercise.
    """
    offsets = []
    for i, line in enumerate(doc_lines, 1):
        offsets.extend([i] * (len(line) + 1))

    def last_cell(i):
        row = doc_lines[i - 1]
        if not row.startswith("|") or re.fullmatch(r"[\s|:-]+", row):
            return None
        return row.strip().strip("|").split("|")[-1].strip()

    out, checked = [], 0
    for m in CLAIM.finditer(doc_text):
        sentence = doc_text[doc_text.rfind("\n", 0, m.start()) + 1:
                             doc_text.find("\n", m.end())]
        tok = re.search(r"`([A-Z][A-Z_]{2,})`", sentence)
        if not tok:
            continue                  # a claim about something other than a mark
        word = tok.group(1)
        ln = offsets[m.start()]
        nums = sorted(int(x) for x in re.findall(r"`:(\d+)`", m.group(2)))
        want = [i for i in range(1, ln)
                if (c := last_cell(i)) and word in c]
        checked += 1
        if nums != want:
            out.append(f":{ln} lists {nums} for `{word}`, the rows carry {want}")
    return out, checked


rule_fail, rule_checked = mark_claim_failures(text, lines)
check(f"and each mark-word claim names exactly the rows that carry that mark "
      f"({rule_checked} claim(s) checked)",
      not rule_fail, "; ".join(rule_fail))

# The same self-test the `bin/aim` half gets, for the same reason: a claim whose
# list is one line short is the exact edit that produced the broken note, and this
# runs the real check on that copy rather than asserting that a parse saw four
# items. Both edits below are the two failures that actually happened -- a line
# dropped from a list, and a line swapped for the glossary's own row.
_probe2 = _inject(text, "`:166`, `:173`, `:2409`, `:2412`, `:2413`",
                  "`:166`, `:173`, `:2409`, `:2412`")
_f2, _ = mark_claim_failures(_probe2, _probe2.splitlines())
check("and it fires on a claim whose list dropped a line (self-test)",
      len(_f2) == 1, f"the injected drop was not caught (got {_f2})")

_probe3 = _inject(text, "`:166`, `:173`, `:2409`, `:2412`, `:2413`",
                  "`:166`, `:98`, `:2409`, `:2412`, `:2413`")
_f3, _ = mark_claim_failures(_probe3, _probe3.splitlines())
check("and on a claim that names the glossary's definition of the word instead of "
      "an instance of it (self-test)",
      len(_f3) == 1, f"the injected glossary row was not caught (got {_f3})")

print(f"\n{passed}/{passed + failed} checks passed")
for w in warnings:
    print(f"\nWARN  {w}")
print(f"\nThe base is {base_ref}. {len(cited)} distinct lines are cited; "
      f"{len(cited) - len(stable)} have moved to {'HEAD' if work else 'the worktree'}, "
      f"which the header's own `measured at` covers and this file does not treat "
      f"as a defect.")
sys.exit(1 if failed else 0)
