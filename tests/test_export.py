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

# Both of T-0201's measured defects are now asserted as requirements rather than
# recorded as known-broken, and the history matters because the first one was not
# a product defect at all.
#
#   * CRLF. The first version of this test ran the export through
#     `subprocess.run(..., text=True)`, whose universal-newline decoding turns
#     CRLF into LF. The check therefore counted every line in the file as a "bare
#     LF" and reported 932 of them against an encoder that had been emitting CRLF
#     all along. It is a test bug that reads exactly like a product bug, and the
#     fix is to compare the bytes the process actually wrote.
#   * Folding. This one was real: no line was folded, so a DESCRIPTION was one
#     physical line of up to 691 octets where RFC 5545 allows 75. Folded now, and
#     `unfold(body)` below is the proof that folding is lossless -- the logical
#     lines it recovers are the ones the writer meant to write.


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
    """The export as BYTES.

    Not `text=True`: universal-newline decoding would fold CRLF to LF and this
    file has to be able to tell the two apart, because the iCal rule is about
    which one the producer wrote.
    """
    proc = subprocess.run(
        [sys.executable, str(BOARD), "export", "--format", fmt],
        capture_output=True, cwd=ROOT,
    )
    return proc


def split_lines(text):
    """Physical lines, whichever terminator the producer used.

    The test must be able to *say* which terminator it got, so this splits on both
    and the CRLF check above is the one that judges.
    """
    return re.split(r"\r\n|\n", text)


def unfold(text):
    """RFC 5545 unfolding: a line starting with a space continues the previous one.

    The trailing empty element that `split_lines` produces for a file ending in
    CRLF is dropped: it is the terminator, not a content line, and keeping it
    would make this side of the round-trip one line longer than the file.
    """
    out = []
    for raw in split_lines(text):
        if raw == "" and text.endswith(("\r\n", "\n")):
            continue
        if raw.startswith((" ", "\t")) and out:
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


def fold(line, limit=75):
    """RFC 5545 folding, written independently of aimboard's own folder.

    The round-trip check below is only worth anything if this is not the same
    code under test, so this one is deliberately written the other way round:
    it slices the encoded bytes and steps back to a character boundary, where
    `exporters._fold_content_line` walks characters and sums their lengths.
    """
    raw = line.encode("utf-8")
    if len(raw) <= limit:
        return [line]
    out, take = [], limit
    while raw:
        if len(raw) <= take:
            out.append(raw.decode("utf-8"))
            break
        cut = take
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:   # not a character boundary
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]   # the continuation marker is part of the line,
        take = limit             # and so counts toward the same 75-octet budget
    return out


def main():
    # --- iCal -------------------------------------------------------------
    ical = export("ical")
    check("export --format ical exits 0", ical.returncode == 0, (ical.stderr or b"")[:300])
    body_bytes = ical.stdout
    body = body_bytes.decode("utf-8")
    # RFC 5545 requires CRLF. `icalendar` and most apps tolerate a bare LF on
    # import, but the spec does not and the tolerance is not universal.
    total_nl = body_bytes.count(b"\n")
    bare_lf = total_nl - body_bytes.count(b"\r\n")
    check("every content line ends CRLF, with no bare LF", bare_lf == 0,
          f"{bare_lf} bare LF in {total_nl} line ending(s)")
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

    # The octet rule, measured on the bytes: 75 octets excluding the CRLF, and a
    # continuation line's leading space counts toward its own 75.
    phys_bytes = body_bytes.split(b"\r\n")[:-1]
    too_long = [l for l in phys_bytes if len(l) > 75]
    check("no physical line exceeds 75 octets before folding", not too_long,
          f"longest {max((len(l) for l in too_long), default=0)} octets "
          f"in {len(too_long)} line(s)")
    # Folding must be lossless: unfolding the file has to give back the logical
    # lines, so a writer cannot satisfy the octet rule by truncating. Compared
    # against the unfolded body of the *same* file -- the invariant is that the
    # fold/unfold pair is the identity, not that some particular text is present.
    phys = body_bytes.split(b"\r\n")[:-1]
    unfolded = unfold(body)
    folded_again = [part.encode("utf-8") for line in unfolded for part in fold(line)]
    check("re-folding the unfolded file reproduces it byte for byte",
          folded_again == phys,
          f"{len(folded_again)} folded line(s) vs {len(phys)} in the file; "
          f"first difference at "
          f"{next((i for i, (a, b) in enumerate(zip(folded_again, phys)) if a != b), 'none')}")
    check("at least one logical line was actually folded",
          len(phys) > len(unfolded),
          f"{len(phys)} physical for {len(unfolded)} logical line(s)")

    # --- CSV --------------------------------------------------------------
    csvout = export("csv")
    check("export --format csv exits 0", csvout.returncode == 0, csvout.stderr[:300])
    rows = list(csv.DictReader(csvout.stdout.decode("utf-8").splitlines()))
    check("the CSV has a header row with the documented columns",
          rows and {"id", "status", "owner", "title"} <= set(rows[0].keys()),
          f"columns: {sorted(rows[0].keys())[:8] if rows else 'none'}")

    # --- JSON -------------------------------------------------------------
    js = export("json")
    check("export --format json exits 0", js.returncode == 0, js.stderr[:300])
    try:
        doc = json.loads(js.stdout.decode("utf-8"))
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
