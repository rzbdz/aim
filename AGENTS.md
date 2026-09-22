# Working in this repo

This is a fabric that agents and one human use *while* building it. The rules
below are not style preferences; each one exists because breaking it cost real
time on a real day, and the cost is recorded in `design/12-architecture-review.md`.

## Infrastructure: one port, and it is 8777

    aimboard serve --port 8777 --refresh 0 --allow-write --as human

**The board lives at http://127.0.0.1:8777. Do not pick a different port.**

Both names are on PATH as symlinks from `/usr/local/bin` into this checkout's
`bin/` (`aim` -> `bin/aim`, `aimboard` -> `bin/aimboard`, which execs
`bin/aimboard.py`); on a checkout where they are missing, that symlink is the
whole install.

- If 8777 is held by a stale `aimboard serve` for this checkout, `aimboard serve`
  takes it back by itself: it identifies the holder through `/proc`, and replaces
  its own server automatically. You do not need to hunt a PID.
- If it is held by anything that is *not* ours, the tool refuses and names the
  holder's pid and command. It does not kill a stranger's process to take a port.
  Free the port; use `AIM_PORT=<n>` only when moving it is a deliberate decision.
- Do not start a second board on another port for convenience. Three boards on
  three ports is how a finding gets filed against the wrong build -- measured,
  twice, on 2026-09-22.

Every port this project uses, and nothing else:

| port  | what it is                                      | who starts it |
|-------|-------------------------------------------------|---------------|
| 8777  | the board -- the only thing a human or a probe should ever open | `aimboard serve --port 8777 --refresh 0 --allow-write --as human` |
| 8788  | the Vite dev server, only while editing `web/src` | `npm --prefix web run dev`; it refuses to move (`strictPort`) |

- A test run does not get its own port. `web/playwright.config.js` points its
  `baseURL` and its `webServer.command` at 8777 and the two are the same number;
  the suite intercepts `/api/state` with fixtures, so it does not write to the
  board it reads. If the suite needs a server and 8777 is free, it starts one
  there. Measured 2026-09-22: a `baseURL` left on a retired port is why a second
  board had to be started by hand, and the hand-starting is what the leader saw
  as "the port keeps changing".
- If 8777 is held by something that is not ours and you mean to take it anyway:
  `aimboard serve --force` names the holder and then kills it. Without `--force`
  the tool refuses and prints the pid, the command and the exact `kill` line.

Machine endpoints, and the rule that unhandled ones 404:

    /api/state      the gated payload the front-end reads
    /api/digest     the change fingerprint
    /api/agents     the registry as the payload sees it
    /api/revision   which revision answered (fabric + bundle + stale flag)
    /api/command    POST, allow-listed verbs, --allow-write only

Any other `/api/*` returns **404 with JSON**. It must never fall through to
`index.html`: a 404 is a fact, a 200 carrying HTML is a lie that a monitoring
consumer will fold as data.

## Measuring: name the revision

Before filing a finding, read `/api/revision`. A measurement that cannot say
which revision of the program measured it is not a measurement. If
`stale` is `true`, the page you are looking at was not built from the source you
are reading -- rebuild before you conclude anything. If `stale` is `null`, the
bundle recorded nothing and you must not treat that as "up to date".

## Product rules for the dashboard

- **Every user-visible word comes from the concept registry, keyed by its raw
  token.** `bin/aim`, the record and a bug report keep the canonical value
  (`SEALED_DIVERGENT`, `blocked`); the view resolves it through
  `aimboard/const.py: LABELS` (`en`/`zh`) or `web/src/concepts.js` (each concept
  carries its own `key`). Two dictionaries, never a translated identifier, and a
  concept has to say what it does to you, not what it is called. The older
  "English UI" rule is superseded by this convention (`T-0202`,
  `design/17` §4) -- a new string that is not in the registry is the defect now.
- **Every rendered date names its timezone.** The store's stamps are ISO-8601 UTC
  and `fold` labels its own bucket grid `"timezone": "UTC"`. The calendar in
  which a date *means* something is `plan/plan.json`'s `"timezone":
  "Asia/Shanghai"` -- the single source for due dates, milestone dates and idle
  thresholds. A date on screen without its zone is a statement the reader cannot
  audit.
- **Never click-to-refresh.** The view is current by itself. A control that exists
  only to make the page true is a defect.
- **No control without an action.** Every primary button resolves to an exact
  command. A button whose only effect is to open a detail pane with no action
  inside it is a dead end.
- **Every identifier deep-links or explains itself.** `T-0184`, `M1`, `D7`,
  `R1`, a phase key, a seal digest: either the reader can click it or the surface
  says what it is. A raw enum as primary text is a defect.
- **A promise is not work.** Items whose provenance is a plan seed must not be
  counted, drawn or coloured as work (see `PromiseTag`, `board.recorded()`).
- **Bounded summaries.** Derived lists default to a summary with an explicit
  expansion, never a 5000px page under one heading.
- **Units are stated.** No number without one, and the unit for effort is hours
  (`estimate_hours`), not days.
- Use libraries that already exist (>1k GitHub stars) before writing your own.
  This front-end is Vue 3 + Element Plus + ECharts + markdown-it + Pinia.

## Before you write a card or propose work

1. Reproduce it and measure it. Numbers, not adjectives.
2. Name the file:line that produces the number.
3. Say what the acceptance test would be, in one sentence that can fail.
4. Check it is not already a card -- duplicate findings cost more than missing ones.

## Reporting

Role split, current: `codex` is the PM/reviewer and reports to the human leader;
`claude-session1` implements. The human leader is the only actor who may advance
a barrier phase (`bin/aim:require_leader`). An orchestrator or monitor session may
direct work but cannot move phases.
