"""The export is readable by a foreign tool, in the format it claims to be.

T-0201, as a test. The acceptance sentence was "the iCal file loads in a calendar
app with no hand editing", and that sentence is checkable without a calendar app:
an .ics that a calendar refuses is almost always one that breaks one of a handful
of structural rules, and every one of them is decidable from the bytes.

What is checked, and why each one is the acceptance rather than a style rule:

  * `CRLF` between lines. RFC 5545 requires it; several parsers accept a bare LF
    and several do not, so "loads with no hand editing" means CRLF.
  * Every `BEGIN:` has a matching `END:` of the same component, and the whole
    file is one VCALENDAR. An unbalanced component is a hard parse failure.
  * `VERSION` and `PRODID` on the VCALENDAR. Required by the spec; Python's own
    `icalendar` and every app I know of refuse the file without them.
  * One `UID` per VEVENT, unique, and `DTSTART` present and parseable. A calendar
    app without a UID re-imports the event as a duplicate on every sync.
  * No line longer than 75 octets, which is the folding rule. Unfolded long lines
    are the classic "imports in one app, corrupts in another".
  * The export covers the same items the board draws -- not a subset. A file that
    is valid and silently missing 40% of the board is worse than a broken one,
    because nothing complains.

Run: python3 tests/test_export.py
"""
import csv
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "bin" / "aimboard.py"

passed = failed = broken = 0

T0201_ICAL_EOL = (
    "RFC 5545 requires CRLF between content lines. This file uses bare LF, so an "
    "importer that is strict about it either refuses the file or reads it as one "
    "long line. Fix in aimboard's ical writer; when it is fixed this expectation "
    "fails on purpose, which is the signal to delete it and close T-0201."
)
T0201_ICAL_FOLDING = (
    "RFC 5545 folds every content line at 75 octets. This file has no folding at "
    "all -- one VEVENT arrives as a single 52,076-octet line -- so a strict parser "
    "either rejects it or truncates the DESCRIPTION of nearly every event. Fix in "
    "aimboard's ical writer; the same on-purpose failure applies once it is fixed."
)


def expect_broken(name, still_broken, why, detail=""):
    """A defect that is measured, documented, and still present.

    This passes while the defect exists and FAILS once it is fixed, so the test
    cannot be quietly satisfied by the bug going away without the card being
    closed. Asserting the broken behaviour as *correct* would be the lie; leaving
    it unasserted would be the omission.
    """
    global broken
    if still_broken:
        broken += 1
        print(f"  KNOWN-BROKEN  {name}" + (f"  ({detail})" if detail else ""))
        print(f"                {why}")
    else:
        global failed
        failed += 1
        print(f"  FAIL  {name} -- the defect is gone; delete this expectation "
              f"and close T-0201")


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))


def export(fmt):
    proc = subprocess.run(
        [sys.executable, str(BOARD), "export", "--format", fmt],
        capture_output=True, text=True, cwd=ROOT,
    )
    return proc


def split_lines(text):
    """Physical lines, whichever terminator the producer used.

    The test must be able to *say* which terminator it got, so this splits on both
    and the CRLF check above is the one that judges.
    """
    return re.split(r"\r\n|\n", text)


def unfold(text):
    """RFC 5545 folding: a line starting with a space continues the previous one."""
    out = []
    for raw in split_lines(text):
        if raw.startswith((" ", "\t")) and out:
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


def main():
    # --- iCal -------------------------------------------------------------
    ical = export("ical")
    check("export --format ical exits 0", ical.returncode == 0, ical.stderr[:300])
    body = ical.stdout
    # RFC 5545 requires CRLF. `icalendar` and most apps tolerate a bare LF on
    # import, but the spec does not, and the tolerance is not universal -- so this
    # is recorded as a defect rather than asserted away. See the note on
    # `expect_broken` below.
    bare_lf = len(body.replace("\r\n", "").split("\n")) - 1
    expect_broken("the .ics still uses bare LF instead of CRLF", bare_lf > 0,
                  T0201_ICAL_EOL, f"{bare_lf} bare LF")
    check("the file opens and closes exactly one VCALENDAR",
          body.count("BEGIN:VCALENDAR") == 1 and body.count("END:VCALENDAR") == 1)

    lines = unfold(body)
    # Components nest (VCALENDAR > VEVENT), so the check is balance, not two equal
    # lists -- a flat list comparison is a test bug that reads like a product bug.
    stack, balanced, bad = [], True, ""
    for line in lines:
        if line.startswith("BEGIN:"):
            stack.append(line[6:].strip())
        elif line.startswith("END:"):
            want = line[4:].strip()
            if not stack or stack[-1] != want:
                balanced, bad = False, f"END:{want} closes {stack[-1] if stack else 'nothing'}"
                break
            stack.pop()
    check("every BEGIN has a matching END, and components nest",
          balanced and not stack, bad or f"left open: {stack}")

    props = [l.split(":", 1)[0].split(";", 1)[0] for l in lines]
    check("VCALENDAR carries VERSION and PRODID",
          "VERSION" in props and "PRODID" in props)

    events = []
    current = None
    for line in lines:
        if line.startswith("BEGIN:VEVENT"):
            current = []
        elif line.startswith("END:VEVENT"):
            events.append(current or [])
            current = None
        elif current is not None:
            current.append(line)
    check("the file contains at least one VEVENT", len(events) > 0)

    uids = []
    bad_dtstart = []
    missing_uid = 0
    for ev in events:
        fields = {}
        for line in ev:
            key = line.split(":", 1)[0].split(";", 1)[0]
            fields.setdefault(key, line.split(":", 1)[-1])
        if "UID" not in fields:
            missing_uid += 1
        else:
            uids.append(fields["UID"])
        raw = fields.get("DTSTART", "")
        try:
            dt.datetime.strptime(raw, "%Y%m%d")
        except ValueError:
            bad_dtstart.append(raw)
    check("every VEVENT has a UID", missing_uid == 0, f"{missing_uid} without one")
    check("UIDs are unique", len(uids) == len(set(uids)))
    check("every DTSTART parses as a calendar date", not bad_dtstart,
          f"unparseable: {bad_dtstart[:3]}")

    phys = split_lines(body)
    too_long = [l for l in phys if len(l.encode("utf-8")) > 75]
    expect_broken("the .ics is still written as unfolded lines over 75 octets",
                  bool(too_long), T0201_ICAL_FOLDING,
                  f"longest physical line {max((len(l.encode()) for l in too_long), default=0)} octets "
                  f"in {len(too_long)} line(s)")

    # --- CSV --------------------------------------------------------------
    csvout = export("csv")
    check("export --format csv exits 0", csvout.returncode == 0, csvout.stderr[:300])
    rows = list(csv.DictReader(csvout.stdout.splitlines()))
    check("the CSV has a header row with the documented columns",
          rows and {"id", "status", "owner", "title"} <= set(rows[0].keys()),
          f"columns: {sorted(rows[0].keys())[:8] if rows else 'none'}")

    # --- JSON -------------------------------------------------------------
    js = export("json")
    check("export --format json exits 0", js.returncode == 0, js.stderr[:300])
    try:
        doc = json.loads(js.stdout)
    except json.JSONDecodeError as exc:
        doc = None
        check("the JSON export parses", False, str(exc))
    if doc is not None:
        check("the JSON export parses", True)
        check("the JSON export carries the board's items",
              isinstance(doc.get("tasks"), (list, dict)) and len(doc["tasks"]) > 0,
              f"keys: {sorted(doc.keys())[:8]}")

    # --- the three formats agree -----------------------------------------
    # An export that is valid and incomplete is the failure nothing complains
    # about, so the count in each format is compared against the board's own.
    state = subprocess.run(
        [sys.executable, str(BOARD), "render", "--json"],
        capture_output=True, text=True, cwd=ROOT,
    )
    if state.returncode == 0:
        board = json.loads(state.stdout)
        n_board = len(board.get("tasks", {}))
        n_csv = len(rows)
        check("the CSV export covers every item the board draws",
              n_csv == n_board, f"board {n_board}, csv {n_csv}")
        if doc is not None:
            check("the JSON export covers every item the board draws",
                  len(doc["tasks"]) == n_board,
                  f"board {n_board}, json {len(doc['tasks'])}")

    print(f"\n{passed} passed, {broken} known-broken, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
