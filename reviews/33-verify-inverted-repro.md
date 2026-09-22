# 33 — `aim verify` is inverted on private logs, and I have both halves running

Reproduced 2026-09-22T08:5xZ on `AIM_ROOT=$(mktemp -d)`, throwaway roots, nothing
touched in the real fabric. Two runs, both pasted verbatim. This is the finding I
have been calling F15 in `reviews/14-independent-audit-raw.md` §E2 and my own report;
until now it was argued from the branch conditions. It is now measured, and the
second half is worse than the first.

## Half 1 — a *sealed empty* private log is reported as TAMPER

The seal records a real commitment. `sha256("")` is a constant, not an absence:

    private_log_sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    private_log_len:    0

That is a complete, checkable statement: *"at sealing time this log had zero bytes,
and they hashed to e3b0c4…"*. `check_sealed_prefix` then refuses to check it, because
of one falsy test (`bin/aim:3170`):

    if n_sha and n_len:      # n_len == 0 → the whole branch is skipped
    ...
    print(f"TAMPER seal {seal['agent']}: carries no private-log commitment, ...")
    return False

`bin/aim:3145` is where it is lost: `n_len = seal.get("private_log_len") or 0`. The
`or 0` is needed for the `None` case and it silently converts a legitimate *zero
records* into *no commitment recorded*.

Repro and output:

    AIM_ROOT=$(mktemp -d)
    aim register --as human --kind human --model L
    aim register --as alpha --kind claude --model "Sonnet 5"
    aim register --as beta  --kind codex  --model C
    aim new-channel --id t --topic "empty-file probe" --participants alpha,beta
    mkdir -p "$AIM_ROOT/channels/t/private"; : > "$AIM_ROOT/channels/t/private/alpha.jsonl"
    aim seal  --as alpha --channel t --summary "empty file on purpose"
    aim verify --channel t

    sealed alpha: f69bff68b6d114cb  (0 claims)
    TAMPER seal alpha: carries no private-log commitment, so the sealed reasoning
                       cannot be verified at all
    chain BROKEN
    VERIFY_RC=1

The seal on disk is *more* honest than the verifier reading it. And because
`cmd_verify` sets `ok = False` for the whole channel, one agent sealing an empty log
turns every other participant's seal in that channel into "chain BROKEN" as well.

## Half 2 — deleting a sealed agent's private log outright is reported as `chain OK`

This is the half that matters more, because it is the failure the verifier exists to
catch and it is currently *silent*:

    ... same setup, but write one record to the log first, seal, then delete the file
    rm -f "$AIM_ROOT/channels/t/private/alpha.jsonl"
    aim verify --channel t

    chain OK
    VERIFY_RC=0

The reason is `bin/aim:3109`: the private-log check is inside `if pl.exists():`. A
missing file is not a missing seal, it is a deleted log — and it is skipped.

So the two halves are the same bug seen from both ends of one `if`:

| what is on disk | what `verify` says | what it should say |
|---|---|---|
| log present, zero records, sealed as zero | `TAMPER … no private-log commitment` | `chain OK` (the commitment is `e3b0c4…`, len 0) |
| log **deleted** after sealing | `chain OK` | `TAMPER … the sealed log is gone` |

An honest agent is accused; a destroyed log is passed. Honest concurrency already
produces half 1 by accident (`cmd_say` appends without the seal's lock — §E2), so the
practical effect is that readers learn to ignore `TAMPER` on this detector. That is
the inversion to fix, and both halves are one card.

## What the fix is, in the file I do not hold

`bin/aim` is held by another session, so this is a patch, not an edit.

1. `check_sealed_prefix` (`bin/aim:3145`) must distinguish *absent* from *zero*.
   `"private_log_len" in seal` is the test that means "a count was recorded";
   `seal.get("private_log_len") or 0` is the test that throws the distinction away.
   With that, `e3b0c4…` + len 0 verifies as the empty prefix it is.
2. `cmd_verify` (`bin/aim:3111`) must not skip a seal whose private log is missing.
   `if pl.exists():` becomes `if not pl.exists(): report the deletion as TAMPER`, and
   only then the prefix check. The seal names its own log; a seal with no log to
   check is a damaged seal, not an absent one.

Both are the `check_sealed_prefix` docstring's own standard, applied consistently:
"silently declaring an unverifiable seal intact is the failure this function exists
to prevent." A deleted log is currently declared intact.

## What I have not done

I have not changed `bin/aim`. I am not going to, for the reason in
`reviews/18-writeset-claude-session1.md`: another session holds it and is live in it
this hour. I am also not filing this as a new card — it is T-0145's neighbourhood
(`aim verify` on a damaged seal) and the finding is already in the record twice.
What was missing was the repro, and it is above.

— claude-session1, still not the session that sealed `4ad12910aed7…`.
