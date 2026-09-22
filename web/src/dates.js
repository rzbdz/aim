/**
 * Every date this board renders, and the zone it says it rendered it in.
 *
 * `design/17-org-and-project.md` §4, verbatim: "**Every rendered date names its
 * timezone.** A date without a zone is a statement the reader cannot audit, which
 * is this project's recurring defect in miniature. The store's timestamps are
 * ISO-8601 UTC (`...Z`), and `aimboard/fold.py` labels its own bucket grid
 * `"timezone": "UTC"` — that label must not be dropped when a value crosses into
 * a view." And, on the calendar: "**The calendar in which dates *mean* something
 * is `plan/plan.json`.** Its `"timezone": "Asia/Shanghai"` is the single source".
 *
 * Before this file the browser did the opposite in four ways at once, all of them
 * measurable in the tree:
 *
 *   `App.vue:193`, `ChatPane.vue:424`  `.replace('T',' ').slice(0,19)` on a `Z`
 *                                      string -- a UTC clock time with the `Z`
 *                                      thrown away, so the page printed an
 *                                      instant in a zone it did not name;
 *   `OverviewPane.vue:536,704,714`     `.slice(0,10)` / `.slice(0,16)`, the same
 *                                      thing with fewer digits;
 *   `BarrierPane.vue:542,615`          `el-table-column prop="ts"` -- the raw
 *                                      string, printed whole, still unnamed;
 *   `GanttPane.vue:575-576`            `getMonth()/getDate()` on a plan date,
 *                                      which is *browser-local*: measured on this
 *                                      machine, `lo = 2026-09-21` at `+3d` labels
 *                                      `9/24` under `Asia/Shanghai` and `9/23`
 *                                      under `America/New_York`. The horizon is a
 *                                      run of calendar dates, so that label was a
 *                                      different axis for every reader.
 *
 * Two kinds of value, two answers, and the difference is the whole rule:
 *
 *  - **A bare date** (`as_of`, a task's `start`/`due`, a milestone's `due`) is not
 *    an instant. There is nothing to convert and converting one would be inventing
 *    an instant the record does not hold. It is read in the calendar that gives it
 *    meaning -- see `CALENDAR_ZONE` -- and a reader who needs the zone is told it.
 *  - **An instant** (`ts`, `at`, `sealed[].ts`, `generated_at`) is a point in
 *    time. It is rendered *as the store wrote it*, in UTC, with the zone printed
 *    beside it rather than converted under the reader's feet: the store is the
 *    authority for the byte, `bin/aim verify` compares that byte, and a renderer
 *    that silently shifted it by the reader's offset would be the second answer
 *    this project keeps finding. `stamp()` is that render, and it is the only one.
 *
 * Nothing here converts a date in order to display it differently. The two
 * functions either pass a date through unchanged or add the missing fact -- the
 * zone -- which is why adopting them moved no assertion in `web/tests/`: what a
 * reader reads is the same value as before, plus the zone it was always in.
 */

/**
 * The zone the store's instants are in, and the reason it is written down.
 *
 * `aimboard/fold.py:687` publishes its own bucket grid with `"timezone": "UTC"`
 * and `aimboard/primitives.py:101` mints every `ts` as `...Z`. This constant does
 * not compute anything -- it is the label `design/17` §4 says must not be dropped,
 * and it is spelled once so that a renderer cannot drop it in one place and keep
 * it in another.
 */
export const STORE_ZONE = 'UTC'

/**
 * The calendar a plan date means something in, and the honest caveat.
 *
 * This string is *read from* `plan/plan.json:5` (`"timezone": "Asia/Shanghai"`),
 * which `design/17` §4 names as the single source: "a due date, a milestone date
 * and an `idle_days` threshold are all read in that zone, so a task due 'today' is
 * due in the leader's day and not in UTC's."
 *
 * It is a copy, and a copy drifts -- the payload carries no key for it, so there
 * is nothing on this side to read it from. The fix belongs on the server (`/api/state`
 * publishing `state["plan_timezone"]`, the way it already publishes `as_of`); it is
 * not a second front-end constant, so this one is kept deliberately beside the
 * comment that says where it came from. A reader who catches this stale has a
 * citation, and `web/src/theme.js:35-39` remains the last word on date arithmetic:
 * the *comparison* `due < today()` is zone-free and stays that way.
 */
export const CALENDAR_ZONE = 'Asia/Shanghai'

/**
 * The reader's own zone, named explicitly.
 *
 * `Intl.DateTimeFormat().resolvedOptions().timeZone` is the browser's answer to
 * "which zone is this reader in", and it is preferred over a hardcoded one
 * wherever a render is about the *reader's* clock rather than the record's: the
 * chart axis, which a person reads against their own working day. A browser that
 * cannot answer (an old engine, a locked-down context) falls back to the store's
 * zone, which is a named zone and not `undefined` -- the one outcome that must not
 * happen here is a label that says nothing.
 */
const detectZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || STORE_ZONE
  } catch {
    return STORE_ZONE
  }
}
export const READER_ZONE = detectZone()

/**
 * The short name of a zone, as a reader writes it: `UTC`, `GMT+8`, `CST`.
 *
 * `short` rather than `long` because it goes beside a value in a table cell
 * (`2026-09-22 07:18:11 UTC`), and because `GMT+8` is a fact about an offset while
 * `China Standard Time` is a name that three different offsets share. When the
 * engine cannot answer, the IANA name is returned -- longer, and true.
 */
export function zoneAbbrev(zone = STORE_ZONE) {
  try {
    return new Intl.DateTimeFormat('en', { timeZoneName: 'short', timeZone: zone })
      .formatToParts(new Date()).find((p) => p.type === 'timeZoneName')?.value || zone
  } catch {
    return zone
  }
}

/** The zone as a reader would cite it in a bug report: the IANA name and its abbreviation. */
export const zoneLabel = (zone = STORE_ZONE) => {
  const short = zoneAbbrev(zone)
  return short === zone ? zone : `${zone} (${short})`
}

/**
 * `YYYY-MM-DD HH:MM:SS` in `zone`, with the zone appended.
 *
 * `formatToParts` and an explicit field order rather than `toLocaleString`: the
 * board sorts, diffs and eyeballs these strings beside the raw ones, so the shape
 * has to be the ISO-ish one the rest of this project prints, and a locale's own
 * order (`9/22/2026, 7:18:11 AM`) is a second spelling of the same fact. `hourCycle:
 * 'h23'` is the other half of that -- `24:00:00` for midnight is a string no
 * comparable value takes.
 */
export function stamp(iso, zone = STORE_ZONE) {
  const raw = String(iso || '')
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  // A value with no time component is a date, not an instant: midnight is an
  // invention, and `00:00:00` printed beside a zone is a claim about a moment the
  // record never recorded. `day()` is the render for those, and this refuses to
  // dress one up.
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return day(raw)
  let parts
  try {
    parts = new Intl.DateTimeFormat('en-CA', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hourCycle: 'h23', timeZone: zone,
    }).formatToParts(date)
  } catch {
    parts = new Intl.DateTimeFormat('en-CA', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hourCycle: 'h23', timeZone: STORE_ZONE,
    }).formatToParts(date)
    zone = STORE_ZONE
  }
  const at = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]))
  return `${at.year}-${at.month}-${at.day} ${at.hour}:${at.minute}:${at.second} ${zone}`
}

/**
 * A bare calendar date, printed as it was recorded: `YYYY-MM-DD`.
 *
 * No zone is appended, and that is a decision rather than an omission. A stored
 * date has no instant in it to be in a zone -- `2026-09-26` is the 26th in the
 * calendar the plan was written in, and stamping `UTC` beside it would be asserting
 * that it is not. The zone a bare date is *read* in is the plan's
 * (`CALENDAR_ZONE`), which every surface that draws one of these states once, at
 * the top of the block that draws them, rather than in each cell.
 *
 * It exists so that a caller has somewhere to go that is not a `slice(0, 10)`:
 * a slice of an ISO string happens to be a date today and stops being one the day
 * a value arrives with an offset (`+08:00`), which is the same defect as a
 * `replace('T',' ')` and one the record can produce.
 */
export function day(value) {
  const raw = String(value || '')
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw
  // A date-only value passes through untouched. Parsing it and re-formatting it
  // is where an off-by-one is born (`new Date('2026-09-21')` is UTC midnight, and
  // reading that back in a negative-offset zone gives the 20th), so it is not done.
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${dd}`
}

/**
 * The `M/D` the timeline's x-axis prints for a plan date `offset` days from `lo`.
 *
 * Arithmetic on the date string in UTC, deliberately, and this is a fix rather
 * than a formatting choice: the horizon is a run of calendar dates, so the day at
 * `lo + n` is `lo + n` in every zone, and the browser-local `getMonth()/getDate()`
 * this replaces answered a different question in each one (measured above:
 * `9/23` in New York against `9/24` in Shanghai for the same three-day offset).
 * Read the day back the way it was computed and the axis is one axis.
 */
export function axisDay(lo, offset) {
  const base = new Date(Date.parse(lo) + offset * 86400000)
  if (Number.isNaN(base.getTime())) return ''
  return `${base.getUTCMonth() + 1}/${base.getUTCDate()}`
}
