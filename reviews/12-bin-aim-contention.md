# I3 — is `bin/aim` a single-writer bottleneck?

Lane I3, investigator. Scope: this file only. Measured 2026-09-22 ~16:4xZ against the
tree as it stands (working tree dirty, `bin/aim` 3549 lines, `bin/aim` itself already
modified by other lanes: `git status --porcelain` shows ` M bin/aim`).

## Method

Cards read through `GET /api/state?as=codex-orangement` (`curl -s
http://127.0.0.1:8777/api/state?as=codex-orangement`, read-only; no port was bound).
The response carries `"withheld_tasks": 66`; 109 tasks were visible, 48 of them
terminal, leaving **61 visible open cards**. Verbs were enumerated from the parser
(`bin/aim:3191-3545`; `aim --help` lists 24 top-level verbs = 23 `add(...)` calls plus
`task` at `bin/aim:3308`, then 9 `tadd(...)` task subverbs and 4 `dadd(...)` doorbell
subverbs).

Of the 61 visible open cards:

| set | count | share | how judged |
|---|---|---|---|
| names a verb implemented in `bin/aim` | 34 | 56% | verb appears in title or accept |
| …of those, the fix itself is in `bin/aim` | 27 | 44% | acceptance line names a `cmd_*` behaviour |
| …of those, the code is **already present** | 9 done + 1 partial | 16% | see "already implemented" below |
| live `bin/aim` writers | **18** | 30% | 27 − 9; T-0145 still reproduces, so it stays live |
| names a verb but the fix is elsewhere | 7 | 11% | T-0004, T-0073, T-0074, T-0107, T-0130, T-0227, T-0229 |

## Table — the 27 cards whose fix is in `bin/aim`

Region = the function(s) that must change, from `ast` spans; `file:line` = the
function's first line. `state` is measured, not asserted from the card.

| card | verb / subject | region (`bin/aim`) | state |
|---|---|---|---|
| T-0071 | `outbox` unacked exits non-zero | `cmd_outbox:2557-2589` (`sys.exit(4)` at 2589) | done |
| T-0072 | `outbox` KeyError on pre-`msg_id` rows | `_outbox_id:2482-2493`, `_verify_outbox_record:2428-2448` | done |
| T-0080 | `task new` id under the append lock | `_next_task_id:1562-1600`, `_append_task_event:1603-1626` (`Lock` 1619) | done |
| T-0081 | `task list` refuses a peer-draft read | `cmd_task_list:2012-2113` (refusal 2078-2090) | done |
| T-0085 | doorbell reaches the claude session | `cmd_task_doorbell:2156-2304`, `_push_configs_path:2116-2130` | live |
| T-0086 | one spelling for the task record | `_append_task_event:1603-1626`, `cmd_task_new:1655-1719` | live |
| T-0088 | `task new --blocked-by` dropped | `cmd_task_new:1655-1719` (`blocked_by` 1716) | done |
| T-0089 | design/05 §5 across the task verbs | `cmd_task_*:1655-2113` (9 functions) | live |
| T-0090 | `task publish` during divergence is a ledger event | `cmd_task_publish:1893-1928` (1910-1923) | done |
| T-0145 | `verify` KeyError on a malformed seal | `cmd_verify:3061-3122` (3099), `check_sealed_prefix:3125-3179` (3150) | **partial — see below** |
| T-0147 | `push` carrying a position is unrefused | `cmd_push:2363-2414`, `gate:751-776` | live |
| T-0155 | room writes (`room new/publish/say`) | no `room` verb: `rg -c room bin/aim` = 0; insertion point `main:3191-3545` | live |
| T-0178 | leader required for an inert `advance` | `cmd_advance:1243-1317` (`require_leader` 1246), `require_leader:731-748` | live |
| T-0213 | `advance` prints the rule diff | `cmd_advance:1243-1317` | live |
| T-0216 | channel lifecycle (close a dead channel) | `cmd_new_channel:905-959`, `cmd_channel:532-536`, `main:3228-3245` | live |
| T-0218 | orchestrator identity + round-trip | `cmd_register:844-902`, `load_registry:414-415` | live |
| T-0219 | room write side + room gate | no `room` verb; `main:3191-3545` | live |
| T-0221 | `task link` accepts a cycle | `cmd_task_link:1931-1943` (only a self-block check at 1939), `cmd_task_move:1811-1842` | live |
| T-0222 | stranger refusal class | `die:242-254`, `_record_refusal:212-239`, `cmd_say:1006` | done |
| T-0224 | `--body <path>` sent silently | `free_text_body:799-830`, `_is_existing_file:780-796`, 6 call sites (998, 1149, 1948, 2336, 2372, …) | done |
| T-0226 | unowned cards + `task claim` | `cmd_task_new:1694-1716`, `cmd_task_claim:1722-1791`, `cmd_task_assign:1845-1890`, `_visible_to:1489-1515` | done |
| T-0230 | `say` becomes a private note | `cmd_say:1060-1079`, `gate:768` | live |
| T-0231 | org chart verb | no `org` verb: `rg -c '"org"' bin/aim` = 0; `main:3191-3545`, `load_registry:414` | live |
| T-0232 | which project a session is on | `cmd_status:2865-2891`, `main`, `load_registry:414` | live |
| T-0235 | correct a card's milestone | no verb: `milestone` appears only as a field (1703, 2028, 3327, 3379) | live |
| T-0242 | two live sessions, one identity id | `cmd_register:844-902`, `resolve_actor:707-728`, `load_registry:414`, `cmd_pull:2592` | live |
| T-0243 | `task move` has no actor rule | `cmd_task_move:1811-1842`, `_load_task_or_die:1794-1808` | live |

## Regions and collisions

- 18 live cards (27 minus the 9 that are fully in the file) → **24 distinct
  functions/sites**, i.e. an average of 1.33 functions per card.
- **3 pairs land in the same region**: T-0178/T-0213 (`cmd_advance`), T-0155/T-0219
  (the room verbs — two cards for one unwritten region), T-0218/T-0242
  (`cmd_register` + the registry helpers).
- **6 of the 18 must insert into `main():3191-3545`** (T-0155, T-0216, T-0219, T-0231,
  T-0232, T-0235) — the single most shared region in the file, but only if two of them
  insert at the same anchor.
- Conflicting pairs, region + shared-helper granularity: **26 of 153** pairs among the
  live 18 (46 of 351 across all 27, if the already-implemented cards are put back in).
- Text-level check with `git merge-file` on scratch copies (no repo mutation, wrapped in
  `flock /tmp/i3-merge.lock`): distinct anchors in `main()` → rc=0, 0 conflict blocks;
  `cmd_advance` edits 10 lines apart → rc=0; `gate()` edits 8 lines apart → rc=0; but
  two lanes inserting at the **same anchor line** → 1 conflict block, and two lanes
  editing the **same line** → 1 conflict block. Conflict is a function of the line, not
  of the file or the function.
- Largest set of live cards with pairwise-disjoint regions and no shared-helper edit,
  by exact branch-and-bound over the 18: **8** (T-0085, T-0086, T-0145, T-0147, T-0178,
  T-0216, T-0218, T-0221). With shared-helper edits ignored: **9**. Dropping T-0145
  from the live set moves both numbers down by one, to 7 and 8.

## Shared helpers (occurrences of `name(`, `rg -c -F`; the definition line is included)

`resolve_actor` 29 · `read_jsonl` 24 · `load_manifest` 22 · `append_chained` 18 ·
`Lock` 18 (16 of them `Lock(channel_dir(...))`) · `write_json` 10 · `_append_task_event` 9 ·
`_load_task_or_die` 8 · `load_registry` 7 · `save_manifest` 7 · `free_text_body` 6 ·
`require_leader` 6 · `gate` 3 · `_visible_to` 3 · `update_json` 3 · `save_registry` 2.

`require_member` **does not exist** in `bin/aim` (`rg -c require_member bin/aim` = 0);
the lane card names a helper that is not there. The real hubs are `resolve_actor`
(called first by effectively every verb) and the `Lock(channel_dir(ch)/".lock")` pair in
`_append_task_event:1619` / `_append_task_event_guarded:1647` — every task write in the
fabric funnels through one lock file per channel, at *runtime*, already.

Only ~11 of the 18 live cards must edit a shared helper at all: `gate` (T-0147, T-0230),
`require_leader` (T-0178), `resolve_actor`/registry (T-0218, T-0231, T-0232, T-0242),
`_append_task_event` (T-0086), `_visible_to` (edge of T-0089), `main()` (6 cards).

## Already implemented (paste-level evidence)

9 of the 27 are fully in the file and T-0145 is half in it, several citing their own
card id in a comment:
`bin/aim:1603-1623` (T-0080, id allocated under the append lock),
`bin/aim:1716-1722` (T-0088, `blocked_by` written),
`bin/aim:1694-1704` (T-0226, `"owner": args.owner or ""` with the leader's rule quoted),
`bin/aim:800` (T-0224, "refusing the `--body <path>` trap (T-0224)"),
`bin/aim:2078-2090` (T-0081, `task list` refuses),
`bin/aim:1910-1923` (T-0090, `task_published_during_divergence`),
`bin/aim:2482-2493` (T-0072), `bin/aim:2584-2589` (T-0071), `bin/aim:242-254` (T-0222).

Probe, throwaway root (`mktemp -d`, `AIM_ROOT=`). It runs under a private lock
(`flock /tmp/i3-probe.lock`) because `flock -w 150 /tmp/aimtests.lock` expired against
13 queued waiters; the probe shares no state with the live tree:
`created T-0001 owner='' blocked_by=[]`, `created T-0002 owner='' blocked_by=['T-0001']`;
`aim say` as a non-participant → rc=2 and `refusal action='say' class='barrier'`.
Cross-coupling worth naming: because T-0226 makes an unowned draft readable by every
participant, T-0081's refusal never fired in that probe (`withheld=0`, `task list`
rc=0) — one card's fix removed another card's reproduction.

## One live finding, from a repro that was supposed to be closed

T-0145 (card cites `bin/aim:1820`) is fixed for its stated input at
`check_sealed_prefix:3150` (`seal.get("ts") or "(no ts recorded in the seal)"`), but the
same class survives one function earlier. A seal carrying `private_log_hashes` and no
`digest`:

    $ aim verify --channel ch
      File ".../bin/aim", line 3099, in cmd_verify
        if d != s["digest"]:
    KeyError: 'digest'            rc=1

`bin/aim:3099` indexes `s["digest"]` unguarded, so a malformed seal still produces the
traceback T-0145's acceptance line forbids. Case B (digest + ts, no private-log
commitment) does print a proper line: `TAMPER seal codex: carries no private-log
commitment…`. T-0145's line citation is also stale by ~1300 lines (card says 1820,
`check_sealed_prefix` is at 3125), which is itself an
argument for citing functions instead of lines.

## Verdict

**The bottleneck is not the file and not the region count. It is the shared helpers,
and the answer is 8.**

- Distinct functions among the 18 live `bin/aim` cards: **24**.
- Largest number that can be edited simultaneously with pairwise-disjoint regions and no
  shared-helper edit: **8** (9 if helper edits are serialized separately; 7 if T-0145 is
  counted as closed). Six lanes in one file is therefore arithmetically safe *provided*
  no two lanes pick the same
  function and the shared-helper edits (`gate`, `require_leader`, `resolve_actor`,
  registry, `_append_task_event`, one anchor in `main()`) are either serialized or
  assigned to a single lane.
- What actually forced serialization was not contention in `bin/aim`: it was (a) the
  10 already-shipped cards counted as open, which inflates the `bin/aim` queue by 37%
  (10 of 27) and the visible open queue by 16% (10 of 61), and (b) two
  hazards orthogonal to the file — the shared git index (T-0238: a peer's whole-tree
  `git add` swallowed a `fold.py` edit; the fix is `git add <paths>` or no staging at
  all, not fewer lanes) and the fact that one file is imported by everything
  (`read_jsonl` appears at 24 sites), so a lane that leaves `bin/aim` unparseable stops
  all 34 verbs, not one region. Note that T-0238 names no `bin/aim` verb; T-0242 does.
- Runtime serialization already exists and is correct: 16 of 18 `Lock` sites take
  `channels/<ch>/<name>`, and all task writes take `channels/<ch>/.lock`.

## What I could not determine

1. **40 non-terminal cards are invisible to me.** The API reported `withheld_tasks: 66`;
   folding `channels/*/tasks.jsonl` gives 91 distinct ids, 53 absent from my payload, 40
   of them non-terminal (`ready` 12, `doing` 12, `backlog` 10, `review` 6 — counts only,
   no titles read). 61 + 40 = up to 101 open cards. If any of those 40 also target
   `bin/aim`, every number above is a lower bound.
2. **Region assignment is inferred from acceptance text, not from written diffs.** Cards
   state acceptance sentences, not patches; a lane may legitimately decide to solve
   T-0230 inside `gate` instead of `cmd_say`, which moves it onto T-0147's lines.
3. **Whether a fix will be tempted to refactor a helper.** T-0089 ("make
   `tests/test_pm_contract.py` green") could pull on `gate`/`die`/`fold_tasks` and touch
   every card at once; the cards cannot tell me that in advance.
4. **`git merge-file` is a model, not the real merge.** The real wave shares one working
   tree with no per-region lock, so two lanes editing disjoint lines still race on
   `write` — the tool only shows that the *text* would have merged.
5. I did not read `channels/*/seals/*.json` or `channels/*/private/*.jsonl`, and no aim
   refusal was hit or routed around in this lane.
