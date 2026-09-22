# 20 — Briefing for every worker in the claude-session1 lane

Read this first. It is the same brief for all lanes; your task prompt names your
lane and your files.

## What this workspace is

`/root/tmp/agent-im`. A file-first communication fabric for AI agents: transport is
the filesystem, protocol is the Python CLI `bin/aim`, and the dashboard is Vue 3 +
Vite + Element Plus + ECharts in `web/`, fed by the JSON API in `aimboard/`.

Read `CLAUDE.md`, then `README.md`. The house style is the thing to imitate: every
claim names the evidence, measured numbers are read out of the source or the payload
rather than estimated, and a comment that says *why* a decision was made is worth
more than one that says *what* the line does.

## The one rule that overrides everything

**More than one agent is editing this tree right now.** A worker that edits a file
outside its lane does not produce a merge conflict — it silently overwrites a peer's
in-flight change, and the result is one broken file that passes both peers' tests.

So:

- **Edit only the files your prompt names.** Not one line outside them.
- If your fix genuinely needs a change in a file you do not hold, do **not** edit it.
  Write the exact change (unified diff or the precise `file:line` plus old/new text)
  into a section of your report, and say which card needs it. The lane that holds the
  file applies it.
- **Never run `git add`, `git commit`, `git stash`, `git checkout`, or any command
  that rewrites the working tree.** The tree is dirty with several hands' unfinished
  work; one `git add -A` already swallowed another lane's file today (that is card
  T-0238).
- **Never run `npm run build`** — it rewrites `web/dist` for everyone. If you need to
  prove your Vue changes compile, build into a private directory outside the repo:
  `cd /root/tmp/agent-im/web && npx vite build --outDir /tmp/<your-lane>-dist --emptyOutDir`.
- **Never write to `bin/aim`, `aimboard/cli.py`, `aimboard/a2a.py`,
  `aimboard/fold.py`, `aimboard/gate.py`, `aimboard/fabric.py`,
  `web/src/main.js`, `web/src/panes/ChatPane.vue`, `web/src/panes/ItemsPane.vue`,
  `web/src/panes/ReportsPane.vue`, `web/src/panes/KanbanPane.vue`,
  `tests/selftest.sh`, `tests/test_a2a_reference_client.py`, `README.md`,
  `design/07-a2a-alignment.md`, `design/14-a2a-gaps.md`, or `plan/plan.json`.
  Those are another session's lanes. Several cards need exactly those files; for
  those cards the deliverable is a patch, not an edit.

## How to run anything

A live board is up on `http://127.0.0.1:8777` (read-only for us; do not restart it).
`aim` is on PATH. `AIM_ROOT` relocates all fabric state, so any experiment that
mutates the fabric must run against a throwaway root:

    AIM_ROOT=$(mktemp -d) aim new-channel --as tester --id t --topic "..."

`tests/test_room_gate.py` is the model for that shape: build a throwaway root, drive
the CLI as a subprocess, assert on what came back, print a table a reader can check.

If you need to run the test suite, take the shared lock first — several sessions run
tests on this box at once:

    flock /tmp/aimtests.lock -c 'your command'

## What "done" means for your card

The card's own `accept:` line is the contract. A card is not done because the code
looks right; it is done when you can name the observation that shows it.

Your report must contain, in this order:

1. **Card id and status you are leaving it in** (`done` / `review` / `ready`).
2. **Files you changed**, exact paths.
3. **What you changed and why** — the defect, then the fix, in two or three
   sentences. If you found that the card's premise was *wrong*, say that plainly and
   show the reading that convinced you; a refuted card reported honestly is worth
   more here than a card closed by an edit that did not address it.
4. **The evidence.** The exact command you ran and the exact output, trimmed to the
   lines that matter. "It works" is not evidence. A number with no command under it
   is not evidence.
5. **What you could NOT verify, and why.** Say it explicitly. An unverified claim
   marked as unverified costs nothing; an unverified claim presented as verified
   corrupts the board.
6. **Any change you needed in a file you do not hold** — as a diff.

Do not move the card yourself unless your prompt says you may; the lead lane does
that from your report, so the store's history and the code's history stay in step.
