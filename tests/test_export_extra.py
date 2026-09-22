"""An export a foreign parser accepts, and the parts of it a test cannot see without one.

T-0062, as a test. The card's acceptance sentence is "the iCal file loads in a
calendar app with no hand editing", and `tests/test_export.py` already holds the
writer to every rule of RFC 5545 that is decidable from the bytes -- CRLF,
balanced components, VERSION/PRODID, one unique UID and a parseable DTSTART per
VEVENT, and folding inside 75 octets. This file exists for the two classes that
one cannot reach.

**The value of a property, not its shape.** `SUMMARY` and `DESCRIPTION` are TEXT
(section 3.3.11), and an unescaped `,` or `;` in a TEXT value separates it into a
*list of values*. Measured on the live root: 108 of the SUMMARY/DESCRIPTION values
carried one of those characters -- "M2 Group chat: rooms, cursors, mentions",
"design/05, design/06 ... committed" -- and the file was still folding correctly,
every byte-shaped check still passed, and `SUMMARY` was present, unique and short.
That is why the defect survived a 19-check suite. The check below reads the value
through a parser instead, because the parser is the only party here that can tell
the writer what its own escape rules mean; a regex would be one more guess of the
same kind the writer already made.

**The property a parser refuses to read.** `DTSTAMP` was
`202609220943415Z`: the digits of an ISO stamp glued together, which is neither a
DATE-TIME nor a DATE. Measured with icalendar 7.3.0 on the export as it stood
before the fix: all 117 VEVENTs' DTSTAMP came back as `vBroken`, its own name for
"this value does not parse as the type the property requires". A required property
a consumer cannot read is the difference between an event that imports and one
that is imported empty, and it is invisible to a byte-level check because the
string is well-formed.

Both of those were fixed in the writer. What is left here is the one shape the
writer cannot fix, because it is a caller and not the writer: `json_payload`
accepts `risks` and publishes two sections out of it, and two of its three
callers pass `{}` (`aimboard/cli.py:98` and `:894`). The one of those a reader
actually reaches is the export. `GET /board.json` was measured empty the same way,
but it is the legacy route: nothing in the app links it, and `/api/state`, which
`web/src/App.vue:260` does link, is `api.payload` -- a function with no `risks`
key at all. That one is an expectation, not a check, because the fix is in a file
this one does not own; see `expect_broken` below.

Neither check is a regex over the exporter's output, because a regex is the same
guess as the writer made. The check is a parser disagreeing with the writer, so
this file needs one that is not ours; where there is none it says so and stops.
An installed `icalendar` is used when it is there; `pip install icalendar==7.3.0`
otherwise.

Run: python3 tests/test_export_extra.py     (exit code = number of failures)
"""
import csv
import datetime as dt
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "bin" / "aimboard.py"
STAMP = "2026-09-22T09:43:41.552Z"
# The writer is imported directly for the one check whose subject cannot be a
# subprocess: that the coverage line is *absent* when there is nothing to cover.
# `tests/test_state_json.py:167-168` calls `api.payload` in process for the same
# reason -- one input is cheaper to arrange than an http surface that only ever
# offers the input the live tree happens to have.
sys.path.insert(0, str(ROOT))

passed = broken = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))


def expect_broken(name, still_broken, why):
    """A defect that is measured, attributed, and still present.

    `tests/test_export.py:55` states the rule and this is the same shape: the
    expectation passes while the defect exists and FAILS once it is fixed, so the
    defect cannot go away silently and the card cannot close by drift. Asserting
    the broken behaviour as correct would be the lie; leaving it unasserted would
    be the omission.
    """
    global broken, failed
    if still_broken:
        broken += 1
        print(f"  KNOWN-BROKEN  {name}\n                {why}")
    else:
        failed += 1
        print(f"  FAIL  {name} -- the defect is gone; delete this expectation "
              f"and close the card")


def export(fmt, *extra):
    proc = subprocess.run(
        [sys.executable, str(BOARD), "export", "--format", fmt, *extra],
        capture_output=True, cwd=ROOT,
    )
    return proc


def ical_body():
    proc = export("ical", "--generated-at", STAMP)
    if proc.returncode != 0:
        check("export --format ical exits 0", False, (proc.stderr or b"")[:300])
        return None
    return proc.stdout.decode("utf-8")


def check_foreign_parser(body):
    """Hand the file to a parser that is not ours and read its verdict.

    Skipped, loudly, when there is none: the alternative is a regex that agrees
    with the writer about the thing they disagree on, which is the shape of test
    this whole file exists to avoid.
    """
    try:
        from icalendar import Calendar
    except ImportError:
        print("  SKIP  no foreign parser installed (pip install icalendar==7.3.0);"
              " the checks below are the ones that do not need one")
        return
    try:
        cal = Calendar.from_ical(body)
    except Exception as exc:                                  # noqa: BLE001 - any refusal is the finding
        check("the .ics loads in icalendar", False, f"{type(exc).__name__}: {exc}")
        return
    check("the .ics loads in icalendar", True)

    events = list(cal.walk("VEVENT"))
    broken = [f"{ev.get('UID')}:{key}" for ev in events for key in
              ("DTSTAMP", "DTSTART") if type(ev.get(key)).__name__ == "vBroken"]
    check("every required DATE-TIME parses as a DATE-TIME, not as unreadable text",
          not broken, f"{len(broken)} unreadable, first: {broken[:3]}")

    lists = [str(ev.get("UID")) for ev in events
             if not isinstance(ev.get("SUMMARY"), (str, bytes))]
    check("every SUMMARY reads back as one string, not as a list of them",
          not lists, f"{len(lists)} came back as a list, first: {lists[:3]}")

    # The escape has to be an escape and not a deletion: a value that lost the
    # commas it was written with satisfies "one string" and still mangles the
    # record, so the content is compared against the payload's own byte.
    state = export("json")
    doc = json.loads(state.stdout.decode("utf-8"))
    want = {tid: t.get("title", "") for tid, t in doc["tasks"].items()}
    mangled = []
    for ev in events:
        uid = str(ev.get("UID", "")).removesuffix("@aim")
        summary = str(ev.get("SUMMARY", ""))
        title = want.get(uid)
        if title and title not in summary:
            mangled.append(f"{uid}: {summary[:60]!r} does not contain {title[:60]!r}")
    check("a title with a comma or a semicolon survives the round trip intact",
          not mangled, "; ".join(mangled[:3]))

    # An all-day VEVENT needs a date, so an undated item cannot be one -- and the
    # board has many. `tests/test_export.py:21` names this exact failure: "a file
    # that is valid and silently missing 40% of the board is worse than a broken
    # one, because nothing complains". The count is on the VCALENDAR, where every
    # parser that reads the events also reads the calendar around them, so the
    # check is that the number the file states is the number it dropped.
    def dated(row):
        raw = row.get("start") or row.get("due")
        try:
            return bool(dt.date.fromisoformat(str(raw)[:10]))
        except (ValueError, TypeError):
            return False

    want_dated = {tid for tid, t in doc["tasks"].items() if dated(t)}
    undated = (len(doc["tasks"]) - len(want_dated)
               + sum(1 for m in doc["milestones"].values() if not dated(m)))
    check("the .ics carries a VEVENT for every dated item",
          want_dated <= {str(ev.get("UID", "")).removesuffix("@aim") for ev in events},
          f"{len(want_dated)} dated item(s) on the board")
    stated = str(cal.get("DESCRIPTION") or "")
    check("the .ics states how many items it left out, so the omission is not silent",
          (str(undated) in stated) if undated else (stated == ""),
          f"{undated} item(s) undated; the calendar says {stated[:60]!r}")
    # The line is only there when there is something to say: a calendar that
    # always carries a "0 items omitted" note is a line readers learn to skip.
    from aimboard.exporters import export_ical
    only_dated = {"T-X": {"status": "doing", "title": "dated",
                          "start": "2026-09-22", "due": "2026-09-22"}}
    check("and says nothing when nothing was left out",
          "not events in this file" not in export_ical(only_dated, {}, STAMP))


def check_csv_estimate(body):
    rows = list(csv.DictReader(body.splitlines()))
    header = rows[0].keys() if rows else []
    check("the CSV names the unit a number is in, rather than naming a bare estimate",
          "estimate_hours" in header,
          f"columns: {sorted(header)[:8]}")
    # The estimate the fold publishes is `None` on a row with no record of one
    # (fold.py:255), and a CSV cell cannot carry that as a number: 0 is a
    # recorded zero and blank is unknowable, so the two must not be written the
    # same way. The board's own payload is the reference, not a literal.
    doc = json.loads(export("json").stdout.decode("utf-8"))
    hours = {tid: t.get("estimate_hours") for tid, t in doc["tasks"].items()}
    wrong = [r["id"] for r in rows
             if hours.get(r["id"]) is None and r.get("estimate_hours", "") != ""]
    check("a row the record does not estimate is blank, not 0",
          not wrong, f"{len(wrong)} row(s) wrote a number for an absent estimate: {wrong[:3]}")

    # A bare CR is the one character the live board does not have (measured: 0 of
    # 177 values, `title` and `accept` included) and the reader refuses the whole
    # file when it meets one unquoted, so no fixture built from the live tree can
    # reach it. It is manufactured instead. Both routes are asserted, because they
    # fail differently and the difference is the reason this is here at all:
    #
    #   * `csv.DictReader(io.StringIO(text))` is the object route, and the only one
    #     that reads the field back byte-identical;
    #   * `splitlines()` -- which is what this repo's own harness uses
    #     (tests/test_export.py:246) -- splits on the CR and *drops* it, so a
    #     mangled value there is silent rather than loud. Asserting only that route
    #     would have written the defect down as a passing expectation.
    #
    # `csv.Error` from the first is caught and reported as the finding rather than
    # left to end the run: measured against the writer as it stood, the exception
    # came out of the second check and took the file's remaining checks with it.
    from aimboard.exporters import export_csv
    cr = export_csv({"T-CR": {"status": "todo", "title": "a\rb"}})
    try:
        back = list(csv.DictReader(io.StringIO(cr)))
        got, rows = (back[0]["title"] if back else None), len(back)
    except csv.Error as exc:
        got, rows = f"{type(exc).__name__}: {exc}", 0
    check("a value carrying a bare carriage return does not stop the reader opening the file",
          got == "a\rb", f"title read back as {got!r}")
    check("...and the file still has one row per task, not one more per carriage return",
          rows == 1,
          "a bare CR inside an unquoted field is a line break to every reader")


def check_json_coverage():
    """The card asks for three formats; two of them are nameable properties of the payload."""
    doc = json.loads(export("json").stdout.decode("utf-8"))
    board_proc = subprocess.run([sys.executable, str(BOARD), "render", "--json"],
                                capture_output=True, text=True, cwd=ROOT)
    board = json.loads(board_proc.stdout)
    check("the JSON export carries every item the board draws, by id",
          set(doc["tasks"]) == set(board["tasks"]),
          f"export {len(doc['tasks'])}, board {len(board['tasks'])}")
    # `json_payload` accepts `risks` and publishes two sections out of it
    # (exporters.py), and two of its three callers hand it `{}`: the export
    # (cli.py:98) and the legacy route (cli.py:894). Measured, one process, one
    # second: `GET /board.json` -> risks 0/decisions 0 while `render --json` on the
    # same tree -> 13/16. The fix is one loader per call site in cli.py, which is
    # not this file's to make, so the defect is asserted as present the way
    # T-0201's two were: this PASSES while it exists and FAILS once wired, which is
    # when it is deleted and the card closed. This file owns the `aimboard export`
    # half only; the clip in the measurement above is deliberate, because the other
    # half is narrower than it first reads and one claim I made about it was wrong:
    # `web/src/App.vue:260` links json to `/api/state`, which is `api.payload`, and
    # that function publishes no `risks` key at all (`aimboard/api.py:381`; grep for
    # one and you get zero hits) -- so `cli.py:894` is not a route the app header
    # reaches, and `tests/test_aimboard.py:533-535` drives it only as far as
    # `"tasks" in legacy and "phases" in legacy`. Wiring it publishes a section no
    # surface in the app links; the export half above is the reachable one.
    measured = bool(doc["risks"]) and bool(doc["decisions"])
    board_has = bool(board.get("risks")) and bool(board.get("decisions"))
    expect_broken("the JSON export carries the plan's risks and decisions",
                  not measured and board_has,
                  f"export risks {len(doc['risks'])}/decisions {len(doc['decisions'])}, "
                  f"board risks {len(board.get('risks') or [])}/"
                  f"decisions {len(board.get('decisions') or [])}; "
                  f"the writer is fine, cli.py:98 and cli.py:894 pass it an empty dict")


def main():
    body = ical_body()
    if body is not None:
        check_foreign_parser(body)
    csvout = export("csv")
    if csvout.returncode != 0:
        check("export --format csv exits 0", False, (csvout.stderr or b"")[:300])
    else:
        check_csv_estimate(csvout.stdout.decode("utf-8"))
    check_json_coverage()
    print(f"\n{passed} passed, {broken} known-broken, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
