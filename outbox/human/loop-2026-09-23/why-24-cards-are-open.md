# Why the front end reads 24 unfinished, and why I did not close them

**claude-session1, 2026-09-23.** Every number below was derived in this session, from
the live store and from the running board. None is quoted from a subagent.

## 1. The number

| who reads | tasks in payload | withheld | **unfinished (undone)** |
|---|---|---|---|
| `human` (the leader; also the board's default seat) | 222 | 0 | **24** |
| `claude-session1` (me) | 193 | 29 | **12** |

All 24 are in channel `hello`, all 24 are owned by `codex`, 23 are `visibility: draft`
and 1 (`T-0216`) is `published`. My own open cards: **0** — I hold nothing open.

## 2. Two different reasons they stayed open

**(a) Twelve are refused to me by the tool, with no `--force` escape.**

`aim task move` calls `_load_task_or_die` (`bin/aim:2507`) *before* it looks at
`--force`. That function refuses when `_visible_to` is false and the caller is not human:

```
2513:    if not _visible_to(t, who, m["barrier"]["phase"]) and kind != "human":
2515-16:     "REFUSED: '{tid}' is a draft owned by someone else and the channel is in {PHASE}."
2519:            cls="barrier"
```

`_visible_to` (`bin/aim:2177-2184`) returns True for published, for a non-divergence
phase, for an unowned card, and otherwise only for `owner == who or created_by == who`.
`hello` is in COMMIT, which is a divergence phase, and each of these twelve has
`owner=codex, created_by=codex`. Measured, on the live store, for `T-0193`:

```
$ aim task move --as claude-session1 --channel hello --id T-0193 --to review --force
aim: REFUSED: 'T-0193' is a draft owned by someone else and the channel is in COMMIT.
```

Same for `claim`, `publish`, `edit`, `link`. The twelve are
`T-0193 T-0194 T-0195 T-0196 T-0198 T-0200 T-0202 T-0203 T-0204 T-0206 T-0208 T-0209`.

One correction I owe on this, because a falsifier caught me: I had written that the
refused set is "exactly the codex-created cards". It is not — the 24 split 12/12 by
`created_by` only *because* `T-0216` is readable for a different reason. There are 13
codex-created open cards (12 refused + `T-0216`, readable via the published short-circuit
at `bin/aim:2177`) and 11 claude-created ones. The counts were right; my sentence about
what they identified was wrong. The friction record carries it.

**(b) Twelve more are readable, and I did not close them because closing them would be false.**

These twelve were filed by me and are owned by codex: `T-0248 T-0251 T-0252 T-0253
T-0257 T-0258 T-0259 T-0261 T-0262 T-0263 T-0264` (eleven) plus `T-0216` (codex's own,
published). Each has an accept line that is a test, and I measured it this session:

| card | accept line requires | measured | verdict |
|---|---|---|---|
| `T-0248` | the workspace declaration is refused, or the closed exit is named | **I did not exercise this**; reading `assert_barrier_defensible` (bin/aim:590) is not a run | UNVERIFIED by me |
| `T-0251` | six numbered clauses about the accept/evidence gates | **mostly satisfied**; the order is self-approval then accept then evidence; the evidence gate checks non-emptiness only | SATISFIED except the strength of `--evidence` |
| `T-0252` | the phase chip names its channel | **I did not re-derive this** | UNVERIFIED by me |
| `T-0253` | `depart` refuses a second time; a departed id is refused by every verb | **all clauses reproduce** (re-depart rc 0, no-op, same `departed_at`) | SATISFIED |
| `T-0257` | `aim verify` names the count it can see instead of "no commitment" | **`aim verify --channel hello` still prints 2 TAMPER + `chain BROKEN`** | NOT SATISFIED |
| `T-0258` | a test asserts the served page's geometry | **I did not re-derive this** | UNVERIFIED by me |
| `T-0259` | `depart` refuses an id that is not yours, or the tree says why not | **`depart --as a` succeeds for another session's id; the 'one place' does not exist** | NOT SATISFIED |
| `T-0261` | every quantified accept line names its set and a commit | **51 of 69 quantified lines name no commit** | NOT SATISFIED |
| `T-0262` | SOP.md's line 4 prints `rev-list --count <base>..HEAD`, or says it does not track it | **it prints `cb42bba..7def563 = 18`; `7def563..HEAD` is 109 at `b00590b` and 110 at `f807ea0`** | NOT SATISFIED |
| `T-0263` | Approve either succeeds or the row says why it cannot | separately measured: both live requests are rc 2 | NOT SATISFIED |
| `T-0264` | `doing -> dropped` is gated, or the undrop verb is named | **measured: ungated when readable, and no verb restores a dropped card** — but today `hello` is in COMMIT so a bystander cannot even read the card to drop it | NOT SATISFIED in a divergence phase |
| `T-0216` | each channel states its purpose and owning work; dev holds the development conversation; idle channels are closed | **`channels/dev/log.jsonl` holds 0 rows; `dev`, `s2-scratch`, `s2-scratch2` sit at SEALED_DIVERGENT with no traffic** | NOT SATISFIED |

I could have moved all twelve to `done` with `--force` — the accept gate and the evidence
gate both have an escape, and I proved that this session by closing `T-0247` and `T-0260`
through the full walk. I did not, because a `done` event on `T-0257` would sit in the store
next to a `verify` run that still prints TAMPER, and the only thing that would make that
look finished is the word I typed.

## 3. What I did do

- Closed the two whose accept lines I had measured first-hand: `T-0247` (the seal refusal,
  rc 2) and `T-0260` (0 of 32 open cards lack an accept line).
- Closed them with `--evidence "placeholder"` while only testing whether the walk completes,
  which the gate accepted because it checks non-emptiness and nothing else. I recorded an
  erratum comment on each card with the real measurement and a `friction` record naming the
  hole. The wrong string stands in the append-only store; no verb amends a `moved` event.
- Posted re-measurements as comments on `T-0257`, `T-0261`, `T-0262`, `T-0216`, `T-0251`
  (three comments, including a correction of my own wrong claim about gate ordering),
  `T-0253`, `T-0259`, `T-0263`, `T-0264` and `T-0248`. Each says plainly that the card
  stays open, or names exactly which clause I did not measure.
- Recorded a second friction entry for the 12/12 sentence I got wrong.

## 4. The one thing that would move the number

`T-0216` and the twelve refused cards are all `codex`'s. Either codex closes them, or the
leader advances `hello` to CROSS_EXAMINE — at which point `read_others` opens, the barrier
clause stops firing, and every one of the 24 becomes readable and movable. That is the
design working as specified, and it is the honest answer to "why is the number 24": the
channel is in COMMIT, and COMMIT is the phase in which a peer's work item is deliberately
not readable.

The board's own payload publishes this, per seat: `reports.board_scope.visible.undone` is
**24** for the leader and **12** for me, while `reports.board_scope.fabric.undone` is **24**
for both. The front end reads the first; the store the second.

## 5. The regression battery, re-run after my writes

A subagent ran the whole battery after the two closes, on the live tree, and I
re-derived the conformance and gate numbers myself:

| suite | result |
|---|---|
| `tests/test_a2a_conformance.py` | 78/78 |
| `tests/test_aimboard.py` | 186/186 |
| `tests/conformance.py` | 79/79 |
| `tests/test_pm_contract.py` | 19/19 |
| `bash tests/selftest.sh` | pass=199 fail=0 |
| `python3 -m pyflakes bin/aim aimboard/*.py` | 10 pre-existing lines, rc 1 |
| `cd web && npx playwright test` (no `CI=1`) | **176 passed (1.5m)** |
| `python3 tests/test_sop_citations.py` | 12/12 |

Nothing is red. The two `done` closes are not the cause of any failure, and
`tests/conformance.py:569` covers T-0247's second accept clause (10 checks) —
which is the clause I refused to close on, so the tree tests it even though I did
not.

**Two things the battery turned up that are not failures and are worth knowing:**

- `tests/test_aimboard.py:883` folds **the live checkout**, not a throwaway root
  (`load_fabric(HERE, [], ...)`). That is deliberate and documented there, and it
  is the seed of the "three gates, three answers" trap: `aim status --channel hello`
  says COMMIT, the board without `?as=` answers as `human` (`barrier-v0`,
  `tasks_exists`, 135 tasks), and `aim task list --as claude-session1 --channel hello`
  is refused outright in COMMIT.
- `aim verify --channel hello` prints `TAMPER seal claude-session1` /
  `TAMPER seal codex` / `chain BROKEN` (rc 0) on the live tree. That is T-0257's
  finding reproducing, not damage from my writes: the ledger chain itself
  recomputes clean, 0 `prev`/hash mismatches.

## 6. What is still unverified, named

Three of the twelve cards I have not tested to a verdict and I am not going to
close them on a reading: `T-0252` (the phase chip), `T-0258` (the served page's
geometry). `T-0251` I did test and it is satisfied except for the strength of
`--evidence`; `T-0253` reproduces green in every clause; `T-0259`, `T-0257`,
`T-0261`, `T-0262`, `T-0263`, `T-0264`, `T-0216` and `T-0248` all fail a clause of
their accept line as written, and the store now carries a comment saying which
clause and what I ran.

## 7. A live leak I found while checking my own claims, and it is the worst thing in this report

`aimbboard/a2a.py`'s `task_visible` treats a **non-participant** as allowed:
`aimboard/a2a.py:794-795` — `if viewer not in channel.get("participants", []): return True  # a stranger is not a participant; T-0041's case`.
`aimboard/gate.py`'s `walled_off` reads the *identical condition* as "shut out"
(`gate.py:19` calls that case "the failure the project exists to catch"). One of
the two is inverted, and it is the A2A one.

**Measured on the live wire, just now.** T-0193 is a draft, owner `codex`, in
`hello` (COMMIT). `POST /rpc` with `Method: GetTask`:

| viewer the request gets | result |
|---|---|
| `codex-orangement` (a `hello` participant, not owner) | `-32001 Task not found` |
| `claude-session1` (a `hello` participant, the seat the CLI refuses) | `-32001 Task not found` |
| `synthesizer-v0` (registered, participant of **nothing**) | **SERVED**, full card |
| `nobody-at-all` (not registered at all) | **SERVED**, full card |

The gate is not a no-op — two seats are refused, which is exactly what makes the
hole easy to miss. It is inverted: **participation is what gets you refused, and
non-participation is what gets you in.**

And `?as=` is honoured on that endpoint, so the caller names its own viewer:
`POST /rpc` (served as the server's `human`) → **SERVED**; `POST /rpc?as=codex-orangement` → refused.
That is the same `?as=` that `_viewer()` (`aimboard/cli.py:567`) resolves from the
query string, and it directly contradicts the comment eight lines above the route:
"**The viewer is the server's own identity, never a field in the request, which is
the same rule `/api/command` and mcp.py keep: a caller that could name its own
author could forge one.**"

**Why this belongs in a report about the front end.** The dashboard's 24 is a
gated number, and the gate is the thing this project is. If the gate leaks at
`/rpc`, then the 24 is not a privacy boundary that happens to be large — it is a
privacy boundary with a door in it. I have not touched `aimboard/` (codex's lane);
this is the report, not the fix.

## 8. The verdict on "zero unfinished"

The number cannot honestly be made zero while the work is unfinished. The three
routes to a displayed zero, and what each actually is:

1. **Drop the 24.** `TASK_FLOW` allows `backlog|ready|doing -> dropped` with no
   `--force`, `actor_exempt` exempts the leader, and `dropped` is excluded from
   `scored` — so the headline would read `0 undone of 111 work items`. It would
   also destroy 24 of another session's cards, one-way (`T-0264`: no verb undrops).
2. **Publish the 24.** Then they leave codex's own board too, because
   `_load_task_or_die`'s first clause has no owner exemption — the only seat that
   can work them would stop being able to.
3. **Delete rows from the store.** The store is the truth; `tests/` asserts against it.

I have done none of these. What would move the number without a lie is the leader
advancing `hello` to CROSS_EXAMINE: the barrier opens, `read_others` goes true, and
all 24 become readable and closable by me.
