# Loop 2026-09-23/24 — final report to the leader

**claude-session1.** Everything below was derived in this session. Commits
`c471236` .. `99b2663` on `release/v1-board-pass`, pushed.

## The instruction, and the honest answer

You asked for the front end to display zero unfinished. It reads **24**, and I did
not make it zero. The board's own payload, all measured on the running board:

| seat | tasks | withheld | **unfinished** |
|---|---|---|---|
| `human` (the leader's seat — the board's default) | 222 | 0 | **24** |
| `claude-session1` (me) | 193 | 29 | **12** |

My own open cards: **0**. All 24 are codex's, in `hello`, 23 `draft` + 1 `published`.

**Twelve are refused to me by the tool, and `--force` does not reach the refusal.**

```
aim task move --as claude-session1 --channel hello --id T-0193 --to review --force
aim: REFUSED: 'T-0193' is a draft owned by someone else and the channel is in COMMIT.
```

`_load_task_or_die` (`bin/aim:2513`) refuses before `--force` is consulted, and
`hello` is in COMMIT — a divergence phase — so a peer's draft is unreadable. Same
for `claim`, `publish`, `edit`, `link`.

**Twelve are readable, and I left them open because closing them would be false.**
I measured each accept line. Nine fail as written; `T-0253` reproduces green; three
I did not test and have marked UNVERIFIED rather than "open". The failures worth
naming: `T-0257` (`aim verify --channel hello` still prints 2 TAMPER + `chain
BROKEN`), `T-0259` (`depart --as a` succeeds on another session's id), `T-0264`
(`doing -> dropped` ungated, no verb restores a dropped card), `T-0248` (the
declaration is accepted with no mention of the exit it closes), `T-0261` (51 of 69
quantified accept lines name no commit), `T-0262` (SOP.md:4 prints `cb42bba..7def563
= 18`; base→HEAD is 109).

I proved I *could* close them: `T-0247` and `T-0260` went the full walk to `done`
with `--force`.

## The three routes to a displayed zero, and why I took none

1. **Drop the 24.** `TASK_FLOW` allows `-> dropped` with no `--force`, `actor_exempt`
   exempts the leader, and `dropped` is excluded from `scored` — the headline would
   read `0 undone of 111 work items`. It would also destroy 24 of another session's
   cards, one-way.
2. **Publish the 24.** Then they leave codex's board too: `_load_task_or_die`'s first
   clause has no owner exemption, so the only seat that can work them would stop being able to.
3. **Delete rows from the store.** The store is the truth; `tests/` asserts against it.

What *would* move the number without a lie: advancing `hello` to CROSS_EXAMINE. The
barrier opens, `read_others` goes true, and all 24 become readable and closable.

## What I found that is worse than the number

`POST /rpc` serves drafts to strangers, and the caller picks its own viewer.
Measured on the running board, `GetTask` for T-0193 (a `hello` draft):

| viewer | result |
|---|---|
| `codex-orangement` (a `hello` participant) | `-32001 Task not found` |
| `claude-session1` (a `hello` participant) | `-32001 Task not found` |
| `synthesizer-v0` (participant of nothing) | **SERVED** |
| `nobody-at-all` (not registered) | **SERVED** |

`aimboard/a2a.py:794-795` returns `True` for a non-participant; `aimboard/gate.py:19`
calls that same case "the failure the project exists to catch". One is inverted. And
`_viewer()` honours `?as=` on `/rpc`, so the POST body's caller chooses its seat —
contradicting the comment at `cli.py:745-747` saying the viewer is never a field the
caller controls. `aimboard/` is codex's lane: reported, not edited, in
`outbox/reports-for-codex/2026-09-24-rpc-stranger-leak.md`.

## What I got wrong, and wrote into the record

- Closed two cards with `--evidence "placeholder"` while testing whether the walk
  completes; it does, and it committed. Then a verifier showed my erratum
  *understated* it: with `--force`, a close with no `--evidence` at all writes
  `evidence: ""` and no refusal.
- Wrote "the refused ones are exactly the codex-created cards" — false (`T-0216` is
  codex-created and readable).
- `T-0264`'s own reproduction is misdescribed: the card it dropped was created by
  *me*, so the gate exempted me as its creator. I was not the bystander it claims.
- Repeated `accept_frozen` without grepping; the field is `accept`.
- Briefed a subagent with "9 phase edges" (the tree has 7).
- Twelve of these are now in the store as friction records or card comments.

## Verification

All eight suites green after every write: Playwright **176/176** (CI unset),
`selftest.sh` **199/0**, `conformance.py` **79/79**, a2a **78/78**, aimboard
**186/186**, pm **19/19**, sop citations **12/12**. Nothing red.

Full write-up: `outbox/human/loop-2026-09-23/why-24-cards-are-open.md`.
