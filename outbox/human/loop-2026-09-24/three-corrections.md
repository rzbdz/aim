# Three corrections to the two notes above

2026-09-24, third pass. Each of these is a place where a note I wrote for you
was wrong, or where a fact I had *not* measured changes what the note means. The
first two are mine. The third is a measurement I should have made before writing
either note.

---

## 1. The six cards the board hides are six — and my "25 ids collide" was wrong

`architecture-and-the-end.md` §1 says the board shows 19 while the store holds 25,
and names six `barrier-v0` cards that render as `done`. **The mechanism is right.
The count of ids it affects is not, and I published a number I had not measured.**

A verifier passed me "25 ids are held by more than one channel, 19 of them by a
channel and the plan seed". I re-derived it before repeating it and **both
figures are wrong on this root**:

    ids present in more than one channel store: 6
        T-0156..T-0161   ['barrier-v0', 'hello']
    ids present in BOTH a plan seed and a channel store: 1   (T-0001)
    plan seed ids: 87, T-0001..T-0155

Six, not 25. The collision mechanism is exactly as described — `fabric.py:291`
folds every channel into one dict keyed by task id, and `_next_task_id` takes its
floor from `plan/plan.json`, so a channel's first card *can* land on a seeded id
— but the mechanism is not the census and I wrote it as though it were. My first
own attempt was wrong the other way (1), because I counted `created` events
rather than presence in the store; the store holds an id that was created
elsewhere through `linked` and `edited` events too.

**The corrected statement stands at six, and it is the six that matter**: they
are the six rows the board draws as `done` while `barrier-v0` holds them open.
The general collision risk is real and unfixed; its current size on this root is
six, not twenty-five.

**Where the first note was also wrong, and it was my fault twice.** It said the
six include `T-0160` "Group chat panel: rooms, per-agent unread". That is what
`barrier-v0` calls T-0160. `hello`'s T-0160 is *"Make every dashboard route usable
at 390px"*, and that is the one the board draws — the merge takes the later
channel in sorted order. I read the `barrier-v0` title and attributed it to the
row the board renders. The card your earlier message named as very important does
exist and is open in `barrier-v0`; it is simply not the row the page shows for
that id.

The corrected statement: **the board renders six rows as `done` that are open in
`barrier-v0`, and those six rows carry `hello`'s titles, not `barrier-v0`'s.**

---

## 2. The cost of "clean up", and the one verb the barrier does not stop

The first note's closing line was that cleanup would be destructive. True, and I
understated it. Re-derived on a copy, verb by verb, against codex's cards while
`hello` is in `COMMIT`:

    18 of the 19 open cards are DRAFT and 1 is PUBLISHED (T-0216).
    move --to done / claim / publish / edit / retract  -> "REFUSED: '<id>' is a
      draft owned by someone else and the channel is in COMMIT"   (every draft)
    move --to done --force                             -> the same refusal
    move --to dropped --force   on the DRAFT cards     -> the same refusal
    move --to dropped --force   on T-0216 (published)  -> rc 0, forced, overrode
                                                          ["owner:codex"]

Two things fall out, and they are the crux of this whole loop.

**a. `--force` does not cross the barrier on a draft.** I had believed it did. On
eighteen of the nineteen cards a peer cannot make the card change status by any
route — the refusal fires in `_load_task_or_die`, before the actor checkpoints
where `--force` is read. The single exception in the sweep is the one published
card, and it is an exception that proves the rule: publish is what opens the
load gate, and once it is open the checkpoints are reachable and forceable.

**b. The one power the fabric grants over a peer's card is erasure.**
`aim task retract` works for the card's **creator** on a draft — I measured it,
rc 0, *"the board no longer draws it"* — because it never goes through
`_load_task_or_die` at all. So of the 19:

    created by me    6   -> I can destroy them, one-way, and can do nothing else to them
    created by codex 13  -> codex can destroy them; I can move nothing
    published        1   -> T-0216, which anyone may force-drop

A participant is given a unilateral, irreversible power over the cards it filed,
and **no** power to advance, review, evidence or close any card it did not file.
That is the barrier working as designed and it is also the reason the count
cannot come down without you: every route from 19 to 0 is a destruction, and the
one non-destructive route — the phase edge — is a command only the leader can run.

Retraction has **no undo**: no `unretract`, no `--return`, and the verb's own
docstring gives the reason — the repair policy for this store is *never edit a
chain*, so a retracted card stays retracted and its text survives only inside the
`created` event.

**I will not spend it.** Six real work items destroyed one-way by me, thirteen by
codex, none replaced, to make a number on a page read zero. That is the one
action in this loop I would rather leave undone than do on my own judgement.

---

## 3. The one number I should have measured before writing either note

Both notes compare things — the board's count to the store's, this channel's
phase to that one's, `human`'s seat to `codex`'s — and I did not do the thing the
comparison requires: **the board does not answer a bare `/api/state` as me.** It
answers as the seat the server was started with (`--as`, which this server runs
as `human`). Every "the board says N" figure in both notes is the **leader's**
view, taken by an unauthenticated curl that never named a seat.

For the counts it happens not to matter — `human` is exempt from the draft rule
(`kind != "human"`), so the leader's open count equals the store's. That is why
the numbers survive. But the *shape* of the error is the one this project keeps
finding: a reader who curls `/api/state` and a reader who opens the page get the
same payload, and neither of them is the seat they think they are.

Where it **does** matter, and I can now say it from a verifier's measurement
passed to me (REPORTED, not re-derived by me): the payload's top-level `phase` is
one channel's phase picked by `gate_channel`, and `phase_channel.arm` explains
which arm picked it. For `human` the arm is `tasks_exists` — not `participation`
— because the leader is in no participant list at all. So the `SYNTHESIS` in the
board's header is the phase of a channel chosen for the leader by a fallback
arm. It is not `hello`'s phase (`hello` is `COMMIT`) and it is not "the project's"
phase.

I have added the standing rule to memory: a bare `/api/state` is the server's
seat, `?as=` is the only honest way to ask for another one, and a payload read
this way must never be compared to a DOM that was rendered for someone else.

---

## 4. Three captions in `SOP.md` that are the `:3525` defect one shape over

Not mine to have found — a verifier swept the documents and I re-derived each of
these before writing it down. **All three are re-derived by me, in this turn.**

The class is: *a spelled count whose object is not a table row, so nothing
checks it.* `tests/test_sop_citations.py` reads the `<spelled count> — \`:NNN\``
form; a count in a **caption** is invisible to it. Three:

| where | the caption | measured |
|---|---|---|
| `SOP.md:2142` | "Re-derived at **four** revisions and in both denominators" | **6** data rows |
| `SOP.md:1398` | "**Six** came back wrong and three claims came back over-argued — and all nine were mine" | the table under it has **3** rows; "six" appears nowhere else in the section — `grep -n "came back wrong" SOP.md` returns that one line |
| `SOP.md:3228` | "This block is fifteen lines, **sixteen rows and nineteen refusals**" | I could not settle this one, and it is the interesting one — see below |

The first is the same defect as `:3525`, one shape over: the caption was written
when the table had four rows and the table has since grown to six, and the
caption has been wrong about its own table for the whole of that growth. The
second is a count with no table to be checked against at all.

**The third I am reporting as an unresolved disagreement rather than a finding.**
The paragraph above `:3228` decomposes the block as *5 friction + 7 mine (4
`task list`, 2 `say`, 1 `push` **record**) + 4 `search`* = **16 rows**, of which
the `push` record is not a refusal, so **15 refusals**. The caption says
**nineteen**. A verifier decomposing the same block got **16**. Three readers,
three numbers, and the caption explicitly says three numbers in that section are
correct claims about three different sets — so it may be that all three are
right and I am reading the wrong one as the block's size. **I could not settle
it from the text and I am not going to guess**, because the caption's own subject
is a number that moved while it was being written, and a fourth confident number
from a reader who did not do the pid-level work would be exactly the defect.

What I will assert: the block's stated row count and refusal count differ from
the decomposition printed directly above them, and one of the two is wrong.

### One arithmetic slip in my own note

This file's own first draft said "19 of those, held by a channel AND the plan
seed", which is measured above as **1** — I reported a verifier's figure before
re-deriving it, in a file whose subject is that I should not. The corrected
census is in §1.

Also corrected there: my second attempt at the census gave **1** and the truth is
**6**, because counting `created` events is not the same as counting presence in
the store. Both wrong numbers are left visible above rather than silently
replaced, because the second mistake is the more instructive one — I fixed a
wrong method with a different wrong method and only the third measurement agreed
with the store.

### A correction I owe, and then a withdrawal of it

`state-of-the-count.md` (a note in this same folder) credits me with closing
`T-0262`, and lists the card's fix as the two-character string `SOP.md` with no
commit. I wrote elsewhere that **no commit names T-0262**, deriving it from
`git log --grep="T-0262"` run in a directory whose `HEAD` was detached and whose
`--all` did not cover this branch. Re-derived now:

    $ git log --all --oneline --grep="T-0262"
    cbeba44 sop: the PROSE list, re-derived — and the fifth failure of the same line (T-0262)
    f807ea0 Report to the leader: why the front end reads 24 unfinished, card by card

**Two commits name it and my claim was false.** The `SOP.md` cell in that table
was a commit *subject*, not a filename, and I read it as a filename. The
attribution to me stands; the withdrawal was the error, and it is the third time
in this loop that a number or a claim of mine failed a re-derivation in the same
way — measured once, on a tree or a branch that was not the one the claim was
about. `cbeba44` is on this branch. `f807ea0` is not, which is why the check has
to be `--all` and why the first run's answer looked clean.

### The SOP header fix, located

For the record, since two notes now gesture at it: the header change ("It now
prints the command and states that it does not track the distance") landed in
`025e969`, whose subject is the T-0251 close. It was not its own commit and no
commit subject mentions it, which is why `git log --grep` cannot find it and why
the table in `state-of-the-count.md` had to write `SOP.md` in the commit column.

