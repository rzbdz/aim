# Adversarial review: the task store and its verbs

Card: T-0197. Acceptance: *at least one measured defect, or an explicit statement
that the kill_if survived.* Seven defects follow, each with the command that
produces it. Revision measured: `dafa296+dirty`, `bin/aim` 585 insertions / 90
deletions against HEAD, bundle `stale: true` — so where a finding depends on the
uncommitted hand I say so.

Everything here is reproducible from a fresh `AIM_ROOT` except D4-D7, which are
about the live fabric and say so.

## D1. A move has no actor rule at all

    AIM_ROOT=$T bin/aim task move --as other --channel ch --id T-0001 --to review
    T-0001: doing -> review                      # rc=0, and T-0001 belongs to `owner`

`cmd_task_move` checks four things and none of them is who is moving: the card is
visible to the actor through the barrier, the transition is in `TASK_FLOW`, `done`
has no open blockers, `blocked/dropped` carry `--reason`. So any participant can
push any card into `review`, and — worse, because it is the direction that
inflates the board — a card's own owner can approve their own work:

    AIM_ROOT=$T bin/aim task move --as owner --channel ch --id T-0001 --to done
    T-0001: review -> done                       # rc=0; the author approved the artifact

Entering `review` is the author's claim that the artifact exists; leaving it is
someone else's verdict. The tool enforces neither. `bin/aim` states the right
principle for `done` one branch down — *"Done is the one status that has to be
decided by something other than the person asserting it"* — and applies it only to
blockers, never to people. Filed as T-0243; pinned by
`tests/test_move_actor_rule.py` (commit `dafa296`), four expected failures.

## D2. The ledger cannot answer "did the author submit this?"

A `moved` event carries `actor`, `from`, `to`, `reason` — and no `owner`. So the
one question review exists to answer is unanswerable from the record without
re-folding the whole card. The state is derivable (`created.owner`), which is
exactly why it should be recorded: a ledger that has to be recomputed is a ledger
that gets recomputed wrongly.

## D3. A forced move is indistinguishable from an ordinary one

    AIM_ROOT=$T bin/aim task move --as other --channel ch --id T-0001 --to doing --force
    T-0001: review -> doing                      # reason: "", no `forced` flag

`--force` exists for "the state machine says no but I mean it". The record keeps
neither the fact that it was forced nor why, so a forced edge in the graph cannot
be found later, and the reason for it is gone.

## D4. The majority of the board cannot be moved at all

    bin/aim task move --as codex --channel hello --id T-0072 --to doing
    aim: no such task: T-0072

while the board draws T-0072 as a card in `ready`, with an owner, a milestone and
an acceptance sentence. It lives in `plan/dogfood.json` / `plan/plan.json` and has
no store record. Measured on the live board: `seed_only: 87` of 164 cards, versus
`recorded: 88`. So `aim task move`, `comment`, `assign` and `claim` refuse on more
than half the board, and no seed can ever contribute to `reports.throughput`. Two
authorities, and the unreachable one is the larger. T-0210 is the importer; until
it lands this is the ceiling on how fast the project can close anything.

## D5. A birth-visibility refusal names nothing actionable

    bin/aim task new --as codex --channel hello --title "..." --visibility published
    A task title states a position in the least suspicious form the fabric contains.
    Work items are born draft; `aim task publish` exposes one deliberately, and that
    act is recorded.

Four attempts, because the first sentence reads like a comment on the title and the
refusal never says `--visibility published is refused here`. The rule is right; the
message sends the reader to the wrong field. Small, and it cost a quarter of an
hour.

## D6. A draft owned by another identity is visible to the leader and reachable by nobody

T-0233, T-0234 and T-0240 are `draft`, owned by `human`, sitting in `review`. The
leader sees them on the board because the human's view is not gated; every agent is
refused:

    bin/aim task move --as codex --channel hello --id T-0233 --to done
    REFUSED: 'T-0233' is a draft owned by someone else and the channel is in COMMIT

There is no publish path available to an agent for another identity's draft, so
these three are frozen: they cannot be published, commented on, or closed except by
the leader in the dashboard. That is defensible as a custody rule and indefensible
as a work queue — a card the leader can see and act on is a card the team cannot.

## D7. The drawer's Record action made those three out of one

T-0035's promise is `T-0004`; the drawer's *Record this work item* button has been
clicked three times and produced T-0233, T-0234 and T-0240 — same title, same owner,
same acceptance, each a separate card with its own events. Filed as T-0244.

## kill_if

The card's kill_if is not satisfied. The negotiation between "a work item" and "a
promise in a plan" is implemented only as a merge in the renderer, and the store
treats the plan as an input that is never imported; the result is that a single
concept has two representations, one of which has no verbs.
