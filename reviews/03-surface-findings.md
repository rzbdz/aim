# 03 — Surface findings from exercising the tool as a user

**Author:** `codex-orangement`, the orchestrator seat (T-0218).
**Measured at:** fabric `5b78a89+dirty`, bundle `5b78a89+dirty`, `stale: false`, 2026-09-22T07:50Z.
**Method:** run every documented command as a new member would, from the docs outward.
Two of the three findings below are *documentation-versus-environment* defects: the tool
is fine and the instruction does not run.

---

## F1 — The first command in `AGENTS.md` does not exist

    $ aimboard serve --port 8777 --refresh 0 --allow-write --as human
    zsh: command not found: aimboard

`AGENTS.md` §"Infrastructure: one port, and it is 8777" opens with exactly that line, at
line 9. It appears again at lines 13, 27 and 38, and `README.md:425-430` gives five more
`aimboard ...` examples. **`aimboard` is not on `PATH`.** Only `aim` is:

    /usr/local/bin/aim -> /root/tmp/agent-im/bin/aim

The working spelling exists and is used by the running system — `README.md:374` says
`bin/aimboard.py render`, and the board actually serving 8777 is

    59830 python3 -u bin/aimboard.py serve --port 8777 --refresh 0 --allow-write --as human

So the zero-dependency claim holds only for someone who already knows the long form. A new
session reading `AGENTS.md` top to bottom gets `command not found` on the first
instruction it is given, and the fix is ambiguous: install the entry point, or correct
eleven call sites. `README.md:252` states the convention — *"`cd /root/tmp/agent-im` # `aim`
is on PATH"* — so the environment is the thing that is out of step, and one symlink closes
it.

**Severity:** low mechanically, high for onboarding. This is the same wound as
`reviews/01` **D4**: the fabric's first contact with a new member fails, and it fails in
the one place designed to make first contact work.

## F2 — A second board is live on 8799, seven minutes after it was declared gone

`channels/hello/tasks.jsonl`, T-0196, `codex`, 2026-09-22T07:37:15Z:

> "**The second board is gone.** 8799 was serving a bundle from before `/api/revision`
> existed and answered `/api/revision` with index.html and HTTP 200 — the exact lie the 404
> rule exists to stop. Killed; one listener remains (8777)."

    $ ps -eo pid,lstart,args | grep '[a]imboard.py serve'
     59830  Tue Sep 22 15:34:03 2026  ... --port 8777 --refresh 0 --allow-write --as human
     88004  Tue Sep 22 15:44:50 2026  ... --port 8799 --refresh 20 --allow-write

15:44:50 local is **07:44:50Z — 7m35s after the claim**. `AGENTS.md` forbids this in
terms: *"Do not start a second board on another port for convenience"*, *"A test run does
not get its own port"*, and the port table lists only 8777 and 8788. T-0196's own earlier
comment says 8799 *"died again today (third time) and is not being restarted."* It is the
fourth.

**The cause is locatable and it is not carelessness:** seven probe scripts under `web/`
still hardcode the retired port —

    probe-t0183d.mjs, probe-viewer-codex.mjs, probe-tmp.mjs, probe-attn2.mjs,
    probe-owner-filter.mjs, probe-promise-codex.mjs, probe-attn-filter.mjs
    all: http://127.0.0.1:8799

So every probe run needs a board on 8799, and one gets started. The rule in `AGENTS.md`
cannot hold while the tools that are run against it point elsewhere; this is the
`design/12` §1.1 shape (two authorities, one key) applied to a port number.

**What saved it this time:** both listeners currently answer `fabric 5b78a89+dirty`,
`bundle 5b78a89+dirty`, `stale: false`. They agree *by luck of timing*, which is precisely
the accident `AGENTS.md` says already cost real time twice today. I am not reporting a
divergence; I am reporting that the guard is off, and that a claim of "one listener
remains" is now falsified in the record. A card's comment asserting a state that is no
longer true is how a reader stops trusting cards.

## F3 — `aim verify` says `chain BROKEN` when no chain is broken

    $ aim verify --channel hello
    TAMPER seal claude-session1: carries no private-log commitment, so the sealed reasoning cannot be verified at all
    TAMPER seal codex: carries no private-log commitment, so the sealed reasoning cannot be verified at all
    chain BROKEN
    $ echo $?
    1

I checked the chains independently, recomputing every `hash` as
`sha256_hex(canonical(rec minus "hash"))` and walking every `prev` link, over all four
chained files in `hello`:

    log.jsonl       1 record   OK — every hash and prev link verifies
    ledger.jsonl   31 records  OK — every hash and prev link verifies
    tasks.jsonl   197 records  OK — every hash and prev link verifies
    friction.jsonl  2 records  OK — every hash and prev link verifies

**231 records, none broken.** So the verdict line is false: nothing about a chain is
broken. What is actually wrong is two seals that carry no commitment —
`seals/claude-session1.json` has `"private_log_sha256": ""` and `seals/codex.json` has an
empty `private_log_hashes` — because they were written before the fix, which `bin/aim`'s
own comment states outright: *"the version that shipped did exactly that for every seal
written before 15:55Z."*

**This is a narrower claim than "the decision is wrong", and I want to be exact about
which part I am attacking.** `README` §4.8 and `check_sealed_prefix`'s docstring both
choose TAMPER over silence, with a reason: *"silently declaring an unverifiable seal
intact is the failure this function exists to prevent."* That reason is sound and I am
not arguing against it. Two things are still wrong:

1. **`TAMPER` is an accusation, and it is aimed at the wrong party.** Neither participant
   tampered with anything. The tool failed to record a commitment, and the tool then
   reports the participant's seal as TAMPER. The verdict that is neither "intact" nor
   "tampered" is **unverifiable**, and this repository uses exactly that third value
   everywhere else — `/api/revision` returns `stale: null` for "the bundle recorded
   nothing", with the comment *"unknown is not equal"*.
2. **The final line reports the intact half as broken.** `chain BROKEN` is printed when
   `ok` is False, and `ok` covers the log, ledger, tasks, push, friction chains **and** the
   seals. A reader sees `chain BROKEN` and concludes the hash-chained record was altered.
   It was not; it verified 231 for 231. There is no way to tell "two seals unverifiable"
   from "the ledger was rewritten" in that output.

**The in-repo precedent disagrees with the prose, in the same file.** `_verify_outbox_record`:

> "Two generations of records exist. D4 added `bytes`/`body_sha256`; anything written
> before that carries no hash, so a checker that asks 'do the bytes hash to the recorded
> value?' answers `no` for every old message and reports intact mail as damaged. Silence
> there is a safety *feature* — an unsigned message has not been shown to be corrupt, and
> crying wolf about it would make the real `DAMAGED` line mean nothing."

That is the same situation, decided the opposite way. One of the two is wrong, and the
outbox reasoning is the one that matches `/api/revision`'s three-valued staleness.

**Proposed fix, which keeps the documented reason intact:** fail as loudly as it does now,
but split the verdict three ways —

    chain OK
    chain BROKEN          -- only when a hash or prev link fails
    chain UNVERIFIABLE    -- n seal(s) carry no commitment; exit 1

Exit 1 on the third, so an unverifiable seal is never silently intact. The leader then
gets a true sentence: the record is intact and two seals from before 15:55Z cannot be
checked.

**Incidental:** `aim verify --help` prints no description at all — only `usage:` and the
options. Every other verb carries one, and this is the verb whose output a reader is most
likely to have to interpret.

---

## What held up, tested this pass

Recording these with the same weight, because a review that only lists wounds is a
campaign:

- **`aim doctor` — 9/9.** "all 40 python sources parse", "aimboard imports cleanly", the
  entry points start, `aim` on PATH parses. It found nothing because it is well built.
- **`aim tension --as codex-orangement --channel hello` refuses, correctly and in one
  clear sentence:** *"the tension report is visible to the leader ('human') and the
  synthesizer only. It is a summary of the other side's reasoning. Reading it before
  CROSS_EXAMINE is exposure by another name."* That is the best refusal message in the
  tool and it names the *reason*, not just the rule.
- **`aimboard export --as codex-orangement` respects the gate:** `83 item(s), 73 withheld`,
  matching `/api/state` exactly for the same viewer. The export path and the API path
  agree, which is not guaranteed by construction.
- **`aim card --as codex-orangement` emits a real A2C AgentCard** with
  `streaming: false`, `pushNotifications: true` and two extensions that honestly declare
  what A2A cannot express. It does not fake a capability.
- **T-0184 (the task drawer bricking the board) is fixed in the served bundle.**
  Measured, all three surfaces: `#/attention`, `#/items`, `#/kanban` → `drawer=1,
  panel=true, navWorks=true, pageerrors=0`. The DOM does carry a pre-mounted
  `.el-overlay` before any click, but it computes `display: none` and the centre of the
  viewport is `el-card__header`, so nothing is blocked. Worth a regression test rather
  than a memory.
