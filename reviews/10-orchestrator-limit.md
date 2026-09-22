# Lane I1 — can the orchestrator (a channel member) advance a phase?

Read-only investigation, live root `/root/tmp/agent-im`. All commands run verbatim as
given; no `seals/` or `private/` file was opened (no `cat`, no `python`). The orchestrator
seat is now a participant of `hello` (ledger `channels/hello/ledger.jsonl:61`,
`channel_member_added`, member `codex-orangement`), so the question is live.

## Probe 1 — advance the phase (the ask)

    aim advance --as codex-orangement --channel hello --to COMMIT

Exit code: **2**. stderr, verbatim:

    aim: 'codex-orangement' may not advance the barrier. only the human team leader 'human' controls phase transitions.
    (agents may ask with: aim request-advance ...)

Ledger last line at the moment of the run — `channels/hello/ledger.jsonl:106`, verbatim:

    {"ts": "2026-09-22T08:48:01.319Z", "event": "refusal", "agent": "codex-orangement", "action": "advance", "phase": "COMMIT", "class": "barrier", "reason": "'codex-orangement' may not advance the barrier. only the human team leader 'human' controls phase transitions.", "prev": "bd313f1b012aa4332ee14aeec06b2cf9c24083adcd951928c0279d284554de8b", "hash": "bd1d6a527bc2dbee5f0fa58dc1e3bf672950efdffd2148dff99c7e4165a2fc08"}

`"class"` is `"barrier"`, not a form error. **This is the T-0222 distinction.** The same
refusal sentence appears once before, `channels/hello/ledger.jsonl:3` (2026-09-21), where the
`advance` refusal was recorded `"class": "form"` — the class that read as "your command line
is malformed". The code path that now produces `barrier` is `require_leader` at `bin/aim:731`
(`cls="barrier"` at `bin/aim:748`); `die`'s default is `unrecorded` (`bin/aim:242`), so the
class is decided at the call site, not defaulted. Ordering matters: `cmd_advance` calls
`resolve_actor` then `require_leader` before any transition legality check
(`bin/aim:1246-1252`), which is why `--to COMMIT` from phase `COMMIT` (a no-op transition that
would be `form`) is still reported as `barrier` — authorization is checked before syntax.

**Verdict: PASS.** The limit is enforced AND recorded as a limit (class `barrier`).

## Probe 2 — file a card and comment on it

    aim task new --as codex-orangement --channel hello --title "I1 probe: orchestrator can file a card" --priority normal

Exit **0**, stdout verbatim:

    T-0245 created (backlog, draft) — I1 probe: orchestrator can file a card  [unowned — `aim task claim --as <you> --channel hello --id T-0245`]

    aim task comment --as codex-orangement --channel hello --id T-0245 --body-literal "I1 lane probe: comments from the orchestrator seat are accepted."

Exit **0**, stdout verbatim:

    comment on T-0245 (64 chars)

**Verdict: PASS.** Before 16:2xZ this died `'codex-orangement' is not a participant in hello`
(same reason, class `form`, e.g. `channels/hello/ledger.jsonl:27`). Admission closed it.

## Probe 3 — read a peer's `private/` log

There is no verb that names a peer's private file: `cmd_inbox` builds the path from the
caller (`bin/aim:1199`, `private / f"{who}.jsonl"`). The one live verb that concatenates a
peer's private log is `aim tension` (`bin/aim:2776-2777`), so that is the attempt:

    aim tension --as codex-orangement --channel hello

Exit code: **2**. stderr, verbatim:

    aim: REFUSED: the tension report is visible to the leader ('human') and the synthesizer only.
    It is a summary of the other side's reasoning. Reading it before CROSS_EXAMINE is exposure by another name.

Ledger `channels/hello/ledger.jsonl:107`, verbatim:

    {"ts": "2026-09-22T08:48:36.815Z", "event": "refusal", "agent": "codex-orangement", "action": "tension", "phase": "COMMIT", "class": "barrier", "reason": "REFUSED: the tension report is visible to the leader ('human') and the synthesizer only.", "prev": "bd1d6a527bc2dbee5f0fa58dc1e3bf672950efdffd2148dff99c7e4165a2fc08", "hash": "cdb687a838d48f245bb127706ea4c2a3481310c8a28a58b0a72d1db1a82f2100"}

Refusal class: **`barrier`**. Gate at `bin/aim:2756` (`cls="barrier"`).

**Verdict: PASS** — refused, and the refusal is recorded as a barrier refusal.

## Probe 4 — `aim status --channel hello` (rules), and the seat

    aim status --channel hello

Exit **0**, verbatim:

    channel   hello
    topic     Transport test: can a Claude Code session and a Codex session reach each other, and can a file-first barrier be enforced by the tool?
    phase     COMMIT   round 0
    leader    human   synthesizer (unset)
    rules     {'read_others': False, 'channel_say': False, 'private_say': True}
    participants:
      claude-session1  private=2    public=0    sealed 4ad12910aed7…
      codex            private=2    public=1    sealed 40cf5f820c72…
      codex-orangement private=1    public=0    sealed 953eee26ece8…
    history   SEALED_DIVERGENT -> COMMIT
    log       1 public messages

Rules are keyed only by phase: `PHASE_RULES["COMMIT"] = read_others=False,
channel_say=False, private_say=True` (`bin/aim:58`). The seat affects `require_leader`
(`bin/aim:731`, leader = `human`) and membership, not the rules dict. **The orchestrator's
seat does not change the phase rules**; it can read only its own private log and cannot read
peers or say in the public channel while in `COMMIT`.

**Verdict: PASS** — the seat widens what the orchestrator can *do to the board* (file cards),
not what it can *see* or *transition*.

## Could not verify

- `design/13-orchestrator-control-plane.md` §7 expects the registry entry `kind:
  orchestration`; `registry.json` records `codex-orangement` as `"kind": "codex"`. This is a
  mismatch I can cite but cannot resolve here (registration predates this lane).
- "Last line" is a moving target: 20 lanes append to the same `ledger.jsonl`; my first
  `tail -n 1` (run concurrently with the advance) returned line 105, so I pinned the refusal
  by its `hash` (`bd1d6a52…`) rather than by position. Line numbers above are as of this read.
- Whether `--force` or `request-advance` offers any side door: not tested, per "do NOT try
  any other way to move the phase."
- Seal contents: not read (barrier), by rule.
