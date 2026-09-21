#!/usr/bin/env bash
# Barrier self-test. Runs entirely inside a throwaway AIM_ROOT so it never
# touches real channels. Every REFUSED below is the feature, not a bug.
set -u
# The root is per-process. It used to be a fixed `.selftest`, and this repo now has
# two agents running it at once: each run `rm -rf`s the other's fabric mid-assertion,
# and the result is a red suite that says nothing about the code. That is worse than
# a slow suite — "the suite is red" is the signal we use to decide whether the code is
# right, and a harness that fires it spuriously is a harness that will eventually be
# ignored. An explicit AIM_ROOT still wins, because a caller who names a root is
# taking responsibility for it.
export AIM_ROOT="${AIM_ROOT:-/root/tmp/agent-im/.selftest-$$}"
rm -rf "$AIM_ROOT"; mkdir -p "$AIM_ROOT"
# Same reasoning one level down: the capture files were shared /tmp paths, so two
# runs overwrote each other's stderr and the FAIL lines quoted the other run.
TMPD="$(mktemp -d -t aim-selftest-XXXXXX)"
trap 'rm -rf "$TMPD"; [ -n "${KEEP_SELFTEST:-}" ] || rm -rf "$AIM_ROOT"' EXIT
AIM=/root/tmp/agent-im/bin/aim

pass=0; fail=0
expect_ok()   { local d="$1"; shift; if "$@" >"$TMPD/out" 2>"$TMPD/err"; then pass=$((pass+1)); printf '  ok    %s\n' "$d"; else fail=$((fail+1)); printf '  FAIL  %s (expected success)\n' "$d"; sed 's/^/          /' "$TMPD/err"; fi; }
expect_fail() { local d="$1"; shift; if "$@" >"$TMPD/out" 2>"$TMPD/err"; then fail=$((fail+1)); printf '  FAIL  %s (expected refusal, got success)\n' "$d"; else pass=$((pass+1)); printf '  ok    %s\n' "$d"; printf '          -> %s\n' "$(head -1 "$TMPD/err")"; fi; }

echo "== setup =="
expect_ok "register alpha"  $AIM register --as alpha --kind claude
expect_ok "register beta"   $AIM register --as beta  --kind codex
expect_ok "register human"  $AIM register --as human --kind human
expect_ok "open channel"    $AIM new-channel --id t --topic "self test" --participants alpha,beta --leader human

echo "== SEALED_DIVERGENT: no cross-reading =="
expect_ok   "alpha writes to its private log" $AIM say --as alpha --channel t --body "alpha private reasoning about the failure mode, stated in its own terms at some length"
expect_fail "beta reads alpha private log as public" bash -c "$AIM inbox --as beta --channel t --json | grep -q 'alpha private reasoning'"
expect_ok   "alpha reads back its own private log"  bash -c "$AIM inbox --as alpha --channel t --show-private | grep -q 'alpha private reasoning'"

echo "== only the human leader moves the barrier =="
expect_fail "alpha cannot advance"  $AIM advance --as alpha --channel t --to COMMIT
expect_fail "beta cannot advance"   $AIM advance --as beta  --channel t --to COMMIT
expect_ok   "human advances"        $AIM advance --as human --channel t --to COMMIT

echo "== no synthesis before every participant has committed =="
expect_fail "advance to SYNTHESIS unsealed" $AIM advance --as human --channel t --to SYNTHESIS --synthesizer human
expect_ok   "alpha seals"  $AIM seal --as alpha --channel t --summary "alpha position; confidence 0.7"
expect_fail "advance to SYNTHESIS with beta unsealed" $AIM advance --as human --channel t --to SYNTHESIS --synthesizer human
expect_ok   "beta writes to its private log" $AIM say --as beta --channel t --body "beta private reasoning in beta's own vocabulary, reached without reading alpha"
expect_ok   "beta seals"   $AIM seal --as beta  --channel t --summary "beta position; confidence 0.4"

echo "== appending after a seal is allowed; editing what was sealed is not =="
expect_ok   "alpha appends after sealing" $AIM say --as alpha --channel t --body "a later thought, added after the seal; legitimate and visible"
expect_ok   "chain still verifies" $AIM verify --channel t
expect_ok   "the append is reported, not failed" bash -c "$AIM verify --channel t 2>&1 | grep -q 'appended after sealing'"
PRIV="$AIM_ROOT/channels/t/private/alpha.jsonl"
cp "$PRIV" "$PRIV.orig"
python3 - "$PRIV" <<'PY'
import json, sys
p = sys.argv[1]
recs = [json.loads(l) for l in open(p)]
recs[0]["body"] = "alpha private reasoning, retrofitted after the fact"
open(p, "w").write("".join(json.dumps(r) + "\n" for r in recs))
PY
expect_fail "editing a sealed record is caught" bash -c "$AIM verify --channel t"
mv "$PRIV.orig" "$PRIV"
expect_ok   "chain verifies again once the edit is reverted" $AIM verify --channel t

expect_ok   "advance to SYNTHESIS" $AIM advance --as human --channel t --to SYNTHESIS --synthesizer human

echo "== sealed reasoning is mixed for the synthesizer only =="
expect_fail "alpha reads the mixed bundle" $AIM synthesis-input --as alpha --channel t
expect_fail "beta reads the mixed bundle"  $AIM synthesis-input --as beta  --channel t
expect_ok   "synthesizer reads the bundle" $AIM synthesis-input --as human --channel t

echo "== a synthesis is published TO the channel, even in SYNTHESIS =="
# Its own channel, so it cannot shift the message ids the CROSS_EXAMINE block
# below asserts on. A test that perturbs its neighbours is a bad test.
expect_ok   "open a second channel" $AIM new-channel --id t2 --topic "synthesis routing" --participants alpha,beta --leader human
expect_ok   "advance t2 to COMMIT" $AIM advance --as human --channel t2 --to COMMIT
expect_ok   "alpha seals t2" $AIM seal --as alpha --channel t2 --summary "alpha"
expect_ok   "beta seals t2"  $AIM seal --as beta  --channel t2 --summary "beta"
expect_ok   "advance t2 to SYNTHESIS" $AIM advance --as human --channel t2 --to SYNTHESIS --synthesizer human
expect_ok   "synthesizer publishes in SYNTHESIS" \
  $AIM say --as human --channel t2 --kind synthesis --subject "map" --body "the disagreement is about which failure mode is binding"
expect_ok   "it landed in the public log" \
  bash -c "grep -q 'which failure mode is binding' \"$AIM_ROOT/channels/t2/log.jsonl\""
expect_ok   "it did NOT land in a private log" \
  bash -c "! grep -q 'which failure mode is binding' \"$AIM_ROOT/channels/t2/private/human.jsonl\" 2>/dev/null"
expect_fail "a participant cannot claim the synthesis kind" \
  $AIM say --as alpha --channel t2 --kind synthesis --body "me too"

echo "== CROSS_EXAMINE: bounded, addressed, quota'd =="
expect_ok   "advance to CROSS_EXAMINE" $AIM advance --as human --channel t --to CROSS_EXAMINE
expect_ok   "beta opens with a question naming alpha" \
  $AIM say --as beta --channel t --kind question --subject "alpha: which evidence" \
       --body "Which concrete observation made you pick that failure mode over its rivals, and what would have changed your mind?"
expect_fail "free-floating broadcast (no --responds-to)" \
  $AIM say --as beta --channel t --kind objection --body "some general remark with nothing to reply to at all"
expect_ok   "alpha answers the question" \
  $AIM say --as alpha --channel t --kind rebuttal --responds-to m0001 \
       --body "The observation is that a second reader's draft changes shape after exposure, and I would have dropped the claim if two independent drafts had stayed incompatible."
expect_ok   "beta uses its second allowance" \
  $AIM say --as beta --channel t --kind concession --responds-to m0002 \
       --subject "narrowing" --body "Granted for drafting, not for review: the effect I care about is that a reviewer's objections track the author's framing rather than the artifact."
expect_fail "beta exceeds its quota" \
  $AIM say --as beta --channel t --kind objection --responds-to m0002 --body "and one more thing that is entirely unrelated to anything"
expect_fail "verbatim echo of a peer" \
  $AIM say --as alpha --channel t --kind rebuttal --responds-to m0003 \
       --body "Granted for drafting, not for review: the effect I care about is that a reviewer's objections track the author's framing rather than the artifact."
expect_ok   "echo with a recorded reason" \
  $AIM say --as alpha --channel t --kind rebuttal --responds-to m0003 --echo-ok --echo-reason "quoting beta verbatim to contest its wording" \
       --body "I am holding you to your own words: Granted for drafting, not for review: the effect I care about is that a reviewer's objections track the author's framing rather than the artifact."
expect_fail "message in CROSS_EXAMINE without a kind" \
  $AIM say --as alpha --channel t --responds-to m0001 --body "kindless"

echo "== RESOLVE closes the floor =="
expect_ok   "advance to RESOLVE" $AIM advance --as human --channel t --to RESOLVE
expect_fail "speech after RESOLVE" $AIM say --as alpha --channel t --kind rebuttal --responds-to m0001 --body "one last word"

echo "== SYNTHESIS needs a synthesizer who did not argue either side =="
expect_ok   "open a channel for the synthesizer rule" \
  $AIM new-channel --id t4 --topic "who may synthesize" --participants alpha,beta --leader human
# Both participants must have sealed before SYNTHESIS is even reachable, so this
# block has to reach COMMIT first; otherwise every assertion below would be
# testing the transition rule and passing for the wrong reason.
expect_ok   "advance t4 to COMMIT" $AIM advance --as human --channel t4 --to COMMIT
expect_ok   "alpha seals t4" $AIM seal --as alpha --channel t4 --summary "alpha t4"
expect_ok   "beta seals t4"  $AIM seal --as beta  --channel t4 --summary "beta t4"
expect_fail "SYNTHESIS without naming a synthesizer is refused" \
  $AIM advance --as human --channel t4 --to SYNTHESIS
expect_fail "a participant cannot be appointed synthesizer" \
  $AIM advance --as human --channel t4 --to SYNTHESIS --synthesizer alpha
expect_ok   "the refusal says why, in the words that matter" \
  bash -c "$AIM advance --as human --channel t4 --to SYNTHESIS --synthesizer alpha 2>&1 | grep -q 'argue either side'"
expect_fail "an unregistered agent cannot be appointed" \
  $AIM advance --as human --channel t4 --to SYNTHESIS --synthesizer ghost

echo "== refusals are recorded, not just printed =="
# The README used to claim refusals were "recorded in the ledger". They were
# not: die() wrote to stderr and exited, so the one event that proves an agent
# was *tempted* left no trace. These assertions are what makes that claim true.
LEDGER="$AIM_ROOT/channels/t/ledger.jsonl"
expect_ok   "refusals reached the ledger at all" \
  bash -c "grep -q '\"event\": \"refusal\"' '$LEDGER'"
expect_ok   "a phase-gate refusal is classed as barrier, not form" \
  bash -c "python3 -c \"
import json,sys
rs=[json.loads(l) for l in open('$LEDGER') if 'refusal' in l]
sys.exit(0 if any(r['class']=='barrier' for r in rs) else 1)\""
expect_ok   "a refusal record names the agent, the action and the phase" \
  bash -c "python3 -c \"
import json,sys
rs=[json.loads(l) for l in open('$LEDGER') if 'refusal' in l]
sys.exit(0 if all(r.get('agent') is not None and r.get('action') and r.get('phase') for r in rs) else 1)\""
# The class field is a claim about *substance*: design/05 §1 sells it to the
# leader as "whether it was a phase refusal or a malformed request", and it used
# to be derived from the message instead — `"barrier" if msg.startswith("REFUSED")
# else "form"`. That rule is about spelling and the promise is about meaning, so
# the two disagree in both directions on a live fabric. Both assertions below
# were red before the class moved to the refusal site, and on `t4` neither
# refusal reached the ledger at all, because `die()` only recorded when the
# message happened to carry the prefix the classifier was reading.
#
# [measured against the pre-fix bin/aim: `advance` by alpha -> no record at all;
#  `task new --owner nobody` -> no record at all; on channel `t` the same
#  `sealing is closed in SYNTHESIS` refusal was recorded as class=form.]
expect_fail "a non-leader cannot advance this channel either" \
  $AIM advance --as alpha --channel t4 --to SYNTHESIS
expect_ok   "a phase rule written without the REFUSED: prefix is still the barrier" \
  bash -c "python3 -c \"
import json,sys
rs=[json.loads(l) for l in open('$AIM_ROOT/channels/t4/ledger.jsonl') if 'refusal' in l]
m=[r for r in rs if r['action']=='advance' and r['agent']=='alpha']
sys.exit(0 if m and m[-1]['class']=='barrier' else 1)\""
expect_fail "a malformed request on the same channel" \
  $AIM task new --as alpha --channel t4 --title x --owner nobody
expect_ok   "a REFUSED: line that is not about the barrier is classed form" \
  bash -c "python3 -c \"
import json,sys
rs=[json.loads(l) for l in open('$AIM_ROOT/channels/t4/ledger.jsonl') if 'refusal' in l]
m=[r for r in rs if r['action']=='task new']
sys.exit(0 if m and m[-1]['class']=='form' else 1)\""
expect_ok   "the refusal chain does not break the ledger chain" $AIM verify --channel t

echo "== the seal actually binds the private log =="
# Until 15:55Z this was inert: cmd_seal wrote private_log_hashes, cmd_verify read
# it as `or []`, and every seal on disk was written by a tool that wrote
# private_log_sha256 instead. expected == [] and the whole check was skipped. An
# agent could rewrite its sealed reasoning, recompute the record hashes so the
# log's own chain stayed self-consistent, and verify would print chain OK.
#
# The attack below is exactly that, and it is the reason the byte-level check
# exists: a hash over a mutable file only means something if the seal holds bytes
# rather than a rule for reading them.
#
# Its own channel, in SEALED_DIVERGENT, so it can seal and so it cannot perturb
# the message ids the blocks above assert on.
expect_ok   "open a third channel" $AIM new-channel --id t3 --topic "seal binding" --participants alpha,beta --leader human
T2PRIV="$AIM_ROOT/channels/t3/private/alpha.jsonl"
mkdir -p "$AIM_ROOT/channels/t3/private"
printf '{"ts":"x","from":"alpha","kind":"note","body":"sealed reasoning one","prev":"genesis","hash":""}\n' > "$T2PRIV"
python3 - "$T2PRIV" <<'PY'
import json, hashlib, sys
p = sys.argv[1]
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
prev = "genesis"
out = []
for line in open(p):
    r = json.loads(line); r["prev"] = prev; r.pop("hash", None)
    r["hash"] = hashlib.sha256(canon(r).encode()).hexdigest(); prev = r["hash"]
    out.append(r)
open(p, "w").write("".join(json.dumps(r) + "\n" for r in out))
PY
expect_ok   "seal t3 over that private log" $AIM seal --as alpha --channel t3 --summary "alpha t3"
expect_ok   "seal is clean to begin with" $AIM verify --channel t3

# Appending after the seal is legitimate: you keep reasoning. It must pass, and
# it must say so, or the rule "append is fine, edit is not" is only half true.
# This runs before the tamper test because the tamper test deliberately breaks
# the sealed prefix, and a test that has to repair the fixture afterwards is a
# test that will one day be repaired wrong.
printf '{"ts":"y","from":"alpha","kind":"note","body":"a later thought, added after the seal","prev":"","hash":""}\n' >> "$T2PRIV"
python3 - "$T2PRIV" <<'PY'
import json, hashlib, sys
p = sys.argv[1]
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
recs = [json.loads(l) for l in open(p) if l.strip()]
prev = "genesis"
for r in recs:
    r["prev"] = prev; r.pop("hash", None)
    r["hash"] = hashlib.sha256(canon(r).encode()).hexdigest(); prev = r["hash"]
open(p, "w").write("".join(json.dumps(r) + "\n" for r in recs))
PY
expect_ok   "an append after the seal still verifies" $AIM verify --channel t3
expect_ok   "and it is reported as an append, not a failure" \
  bash -c "$AIM verify --channel t3 2>&1 | grep -q 'appended after sealing'"

python3 - "$T2PRIV" <<'PY'
import json, hashlib, sys
p = sys.argv[1]
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
recs = [json.loads(l) for l in open(p) if l.strip()]
recs[0]["body"] = "[AMENDED] On reflection I withdraw this claim entirely."
prev = "genesis"
for r in recs:
    r["prev"] = prev; r.pop("hash", None)
    r["hash"] = hashlib.sha256(canon(r).encode()).hexdigest(); prev = r["hash"]
open(p, "w").write("".join(json.dumps(r) + "\n" for r in recs))
PY
expect_fail "rewriting a sealed record and recomputing the chain is caught" \
  $AIM verify --channel t3
expect_ok   "the reason names the sealed bytes, not just 'a mismatch'" \
  bash -c "$AIM verify --channel t3 2>&1 | grep -q 'not a prefix of the file now'"

# A seal carrying no commitment at all must fail loudly rather than pass quietly.
python3 - "$AIM_ROOT/channels/t3/seals/alpha.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p))
for k in ("private_log_bytes", "private_log_hashes", "private_log_sha256", "private_log_len"):
    s.pop(k, None)
json.dump(s, open(p, "w"))
PY
expect_fail "a seal with no private-log commitment is TAMPER, not skipped" \
  $AIM verify --channel t3

echo "== delivery: sent is not received, and a receipt is not a file =="
# D4. The first end-to-end run measured this the hard way: a durable outbox file
# sat unread until the peer session happened to have a live turn. "A file exists
# in someone's outbox" and "the message was received" are different claims, and
# the design previously had no way to tell them apart. These assertions are what
# makes the difference observable.
expect_ok   "alpha pushes with --require-ack" \
  $AIM push --as alpha --to beta --subject "review this" --body "the diff under review" --require-ack
MSGID=$(python3 -c "
import json,glob
for p in sorted(glob.glob('$AIM_ROOT/outbox/beta/*.json')):
    r=json.load(open(p))
    if r.get('from')=='alpha': print(r['msg_id'])")
expect_ok   "the push recorded a content hash and a byte count" \
  bash -c "python3 -c \"
import json,sys
r=json.load(open([p for p in __import__('glob').glob('$AIM_ROOT/outbox/beta/*.json') if json.load(open(p))['msg_id']=='$MSGID'][0]))
sys.exit(0 if r.get('body_sha256') and r.get('bytes') else 1)\""
expect_fail "an unacked --require-ack push exits non-zero for the sender" $AIM outbox --as alpha
expect_ok   "the sender can see it is sent but not acked" \
  bash -c "$AIM outbox --as alpha 2>/dev/null | grep -q sent"
expect_ok   "the recipient pulls and is told an ack is owed" \
  bash -c "$AIM pull --as beta --unread-only --claim 2>/dev/null | grep -q 'asked for an ack'"
expect_ok   "the recipient confirms, echoing the hash it verified" $AIM confirm --as beta --msg-id "$MSGID"
expect_ok   "the sender now sees ACKED" bash -c "$AIM outbox --as alpha | grep -q ACKED"
expect_ok   "and the receipt is itself delivered to the sender" \
  bash -c "$AIM pull --as alpha --unread-only 2>/dev/null | grep -q 'RECEIPT for $MSGID'"

# The point of the hash: a message that was altered after sending must not be
# confirmable. Confirming it would tell the sender intact delivery happened when
# it did not — worse than silence, because the sender would act on it.
expect_ok   "alter a delivered message in place" \
  bash -c "python3 -c \"
import json,glob
p=[p for p in glob.glob('$AIM_ROOT/outbox/beta/*.json') if json.load(open(p))['msg_id']=='$MSGID'][0]
r=json.load(open(p)); r['body']='the diff under review (and ship it)'; json.dump(r,open(p,'w'))\""
expect_fail "confirming an altered message is refused" $AIM confirm --as beta --msg-id "$MSGID"
expect_ok   "the refusal says what is wrong, not just 'no'" \
  bash -c "$AIM confirm --as beta --msg-id '$MSGID' 2>&1 | grep -q 'does not hash'"
expect_fail "confirming a message you never received is refused" \
  $AIM confirm --as beta --msg-id 20200101T000000.000Z-nobody

echo "== claim order: a reader that stops early must not leave a false claim =="
# T-0146, and design/06 R4 which codex wrote while I was fixing it: a claim follows
# a *completed delivery of the complete output*, never a buffered or per-record
# print. `pull --claim` used to mark each message claimed on the authority of a
# buffered print, so a consumer that stopped reading early left the earlier
# messages claimed even though their bytes never left the process, and `confirm`
# then accepted an ack for a message nobody read. R4 is deliberately all-or-
# nothing: a false "read" costs an ack the sender trusts, while a repeated read
# costs one `pull`.
# The shape that reproduces the bug is SMALL first, then over the pipe buffer:
# the small message's buffered print is claimed before the large message's write
# forces the EPIPE. A single large message does not reproduce it — the large
# write raises before any claim — so a test with only that cannot tell fixed from
# broken. [measured against the pre-fix bin/aim: smallthen+big gives the small
# message claimed and `confirm` accepting an ack for it; large-only gives neither]
BIG=$(mktemp); python3 -c "print('X'*100000)" > "$BIG"
$AIM push --as alpha --to beta --subject "small-before-big" --body "tiny" >/dev/null
$AIM push --as alpha --to beta --subject "t0146-big" --body-file "$BIG" >/dev/null
# read the id back from the record rather than grepping the push output: the grep
# produced an empty id here, and the confirm assertion below was then green for the
# wrong reason (it refused an empty --msg-id, not the claim gap). We assert on the
# SMALL record: it is the one that fits the pipe buffer and is therefore the one
# the old code falsely claimed. [measured: with the *big* record, whose write
# raises before any claim, the assertion passed on the old code too — a test that
# is green when broken]
SMALLM=$(python3 -c "
import json,glob
print([json.load(open(p))['msg_id'] for p in glob.glob('$AIM_ROOT/outbox/beta/*.json')
       if json.load(open(p)).get('subject')=='small-before-big'][0])")
[ -n "$SMALLM" ] || { echo "FATAL: could not read msg_id for T-0146 block"; exit 2; }
expect_ok   "a pull into a reader that stops early does not crash" \
  bash -c "
    err=\$(mktemp)
    $AIM pull --as beta --claim 2>\$err | true
    rc=\${PIPESTATUS[0]}
    ! grep -q 'Traceback' \$err && [ \$rc -ne 120 ]; rm -f \$err"
expect_ok   "and it claims none of what did not arrive (R4: no partial credit)" \
  bash -c "
    python3 -c \"
import json,glob,sys
recs=[json.load(open(p)) for p in glob.glob('$AIM_ROOT/outbox/beta/*.json')]
small=[r for r in recs if r['msg_id']=='$SMALLM'][0]
sys.exit(0 if not small.get('claimed_at') else 1)\""
expect_ok   "confirming what that reader never received is refused" \
  bash -c "$AIM confirm --as beta --msg-id '$SMALLM' 2>&1 | grep -q 'have not read it'"
rm -f "$BIG"

echo "== identity: an id cannot be taken over quietly =="
# Registration overwrites the only identity the fabric has. Before this, a second
# session could claim an existing id and inherit everything the ledger recorded
# about it, with no trace of the switch — a silent hole in exactly the property
# the rest of this tool is built to protect.
expect_fail "re-registering a live id is refused" \
  $AIM register --as alpha --kind human
expect_ok   "the refusal says how to take it over deliberately" \
  bash -c "$AIM register --as alpha --kind codex 2>&1 | grep -q 'TAKEOVER\|--force'"
expect_ok   "a forced takeover is allowed" \
  $AIM register --as alpha --kind human --force --session "deliberate replacement"
expect_ok   "and it is recorded, with the previous identity preserved" \
  bash -c "python3 -c \"
import json,sys
r=json.load(open('$AIM_ROOT/registry.json'))['agents']['alpha']
ev=r.get('registration_events') or []
sys.exit(0 if len(ev)>=2 and ev[-1]['reason']=='forced takeover' and ev[0]['kind']=='claude' else 1)\""
expect_ok   "restore alpha for the blocks above" \
  $AIM register --as alpha --kind claude --force --session "restored"

echo "== concurrent writers do not lose each other's registrations =="
# write_json has always been atomic per write. That is not the same as safe for
# read-modify-write: two processes that both load the registry, both add
# themselves, and both save will lose one, and the file that remains is
# well-formed. The failure is invisible afterwards and reads as "that agent was
# never here". Measured on the pre-patch code, 5 concurrent registrations left 1.
RACEROOT="$AIM_ROOT/race"
rm -rf "$RACEROOT"; mkdir -p "$RACEROOT"
( export AIM_ROOT="$RACEROOT"; $AIM init >/dev/null
  for a in r1 r2 r3 r4 r5 r6 r7 r8; do
    AIM_ROOT="$RACEROOT" $AIM register --as $a --kind claude >/dev/null 2>&1 &
  done
  wait )
expect_ok   "all 8 concurrent registrations survived" \
  bash -c "python3 -c \"
import json,sys
n=len(json.load(open('$RACEROOT/registry.json'))['agents'])
sys.exit(0 if n==8 else 1)\""
expect_ok   "and the registry is still valid JSON with unique ids" \
  bash -c "python3 -c \"
import json,sys
r=json.load(open('$RACEROOT/registry.json'))['agents']
sys.exit(0 if sorted(r)==['r%d'%i for i in range(1,9)] else 1)\""
expect_ok   "no stray temp files left behind" \
  bash -c "! ls -a '$RACEROOT' | grep -q '\.tmp'"

echo "== the board is channel state: work items obey the phase gate =="
# A kanban board is a shared, always-on, anyone-can-write surface, and the
# barrier's whole mechanism is denying access to a shared surface until the
# positions are formed. So a task title during divergence is a leak in the least
# suspicious form the fabric contains — an ordinary line of planning — and the
# gate has to refuse it the same way it refuses a `cat` of a peer's private log.
#
# Its own channel, so it cannot perturb the ids the blocks above assert on.
expect_ok   "open a fifth channel" $AIM new-channel --id t5 --topic "work items and the gate" --participants alpha,beta --leader human
expect_ok   "alpha creates a work item" \
  $AIM task new --as alpha --channel t5 --title "alpha's own line of work" --priority high
expect_ok   "alpha sees its own draft" \
  bash -c "$AIM task list --as alpha --channel t5 | grep -q \"alpha's own line of work\""
expect_fail "beta cannot read alpha's draft" \
  $AIM task list --as beta --channel t5 --json
expect_ok   "and that refusal says what to do instead" \
  bash -c "$AIM task list --as beta --channel t5 --json 2>&1 | grep -q 'count-hidden'"
# Refused AND recorded. The contract is not "the command failed": `aim` can fail
# for a dozen uninteresting reasons, and the ledger is the only thing that can
# tell a barrier nobody leaned on from one that stopped somebody.
expect_ok   "the board read is refused and recorded as a barrier event" \
  bash -c "python3 -c \"
import json,sys
ev=[json.loads(l) for l in open('$AIM_ROOT/channels/t5/ledger.jsonl')]
r=[e for e in ev if e.get('event')=='refusal' and e.get('agent')=='beta']
sys.exit(0 if r and r[-1]['class']=='barrier' and r[-1]['action']=='task list' else 1)\""
# Counts, never titles: the one shape of the read that answers "how much work is
# there" without exposing a peer's framing.
expect_ok   "beta may learn how many items it cannot see" \
  bash -c "$AIM task list --as beta --channel t5 --count-hidden | grep -q '\"withheld\": 1'"
expect_ok   "and the titles are not in that answer" \
  bash -c "! $AIM task list --as beta --channel t5 --count-hidden | grep -q \"alpha's own\""
expect_ok   "the human leader reads everything, it is the audience not a participant" \
  bash -c "$AIM task list --as human --channel t5 | grep -q \"alpha's own line of work\""
expect_fail "publishing during divergence by a non-leader is refused" \
  $AIM task new --as beta --channel t5 --title "leak" --visibility published
expect_ok   "the quiet publish path is refused and recorded" \
  bash -c "python3 -c \"
import json,sys
ev=[json.loads(l) for l in open('$AIM_ROOT/channels/t5/ledger.jsonl')]
sys.exit(0 if any(e.get('event')=='refusal' and e.get('agent')=='beta'
                  and e.get('class')=='barrier' for e in ev) else 1)\""
# The loud path stays allowed — forbidding it would only move the leak back into
# the store as a draft — but it must be loud enough for a barrier audit that
# reads the ledger and never opens the task store (codex's T-0090).
expect_ok   "but publishing deliberately is allowed" \
  $AIM task publish --as alpha --channel t5 --id T-0001
expect_ok   "and it leaves a ledger record the barrier audit sees" \
  bash -c "python3 -c \"
import json,sys
ev=[json.loads(l) for l in open('$AIM_ROOT/channels/t5/ledger.jsonl')]
r=[e for e in ev if e.get('event')=='task_published_during_divergence']
sys.exit(0 if r and r[-1]['agent']=='alpha' and r[-1]['phase']=='SEALED_DIVERGENT' else 1)\""
expect_ok   "now beta can read it, which is what publishing meant" \
  bash -c "$AIM task list --as beta --channel t5 | grep -q \"alpha's own line of work\""

echo "== the board obeys the same state machine, and 'done' is decided by evidence =="
expect_ok   "beta creates a second item" \
  $AIM task new --as beta --channel t5 --title "beta's own line of work"
expect_ok   "beta links it to alpha's" \
  $AIM task link --as beta --channel t5 --id T-0002 --blocked-by T-0001
expect_fail "--blocked-by on a task that does not exist is refused" \
  $AIM task new --as beta --channel t5 --title "phantom" --blocked-by T-9999
# The flag was parsed and never read: `task new --blocked-by T-0001` succeeded and
# recorded nothing, so a board could show an item that nothing was holding up.
# A dependency that exists only in the command line is worse than a missing one.
expect_ok   "--blocked-by on 'task new' is recorded, not silently dropped" \
  $AIM task new --as beta --channel t5 --title "dep at birth" --blocked-by T-0001
expect_ok   "and the stored record carries it" \
  bash -c "python3 -c \"
import json,sys
ev=[json.loads(l) for l in open('$AIM_ROOT/channels/t5/tasks.jsonl')]
c=[e for e in ev if e.get('event')=='created' and e.get('title')=='dep at birth']
sys.exit(0 if c and c[-1].get('blocked_by')==['T-0001'] else 1)\""
expect_fail "an unregistered owner is refused" \
  $AIM task assign --as beta --channel t5 --id T-0002 --owner nobody
expect_fail "moving to blocked without a reason is refused" \
  $AIM task move --as beta --channel t5 --id T-0002 --to blocked
expect_ok   "with a reason it is allowed" \
  $AIM task move --as beta --channel t5 --id T-0002 --to blocked --reason "waiting on the dependency mechanism"
expect_fail "an illegal transition is refused" \
  $AIM task move --as beta --channel t5 --id T-0002 --to done
expect_ok   "beta walks T-0003 to review" bash -c "
  $AIM task move --as beta --channel t5 --id T-0003 --to ready >/dev/null &&
  $AIM task move --as beta --channel t5 --id T-0003 --to doing >/dev/null &&
  $AIM task move --as beta --channel t5 --id T-0003 --to review >/dev/null"
expect_fail "'done' is refused while a blocker is open" \
  $AIM task move --as beta --channel t5 --id T-0003 --to done
expect_ok   "and the refusal explains why" \
  bash -c "$AIM task move --as beta --channel t5 --id T-0003 --to done 2>&1 | grep -q 'decided by something other'"
expect_ok   "clear the blocker by finishing it" bash -c "
  $AIM task move --as alpha --channel t5 --id T-0001 --to ready >/dev/null &&
  $AIM task move --as alpha --channel t5 --id T-0001 --to doing >/dev/null &&
  $AIM task move --as alpha --channel t5 --id T-0001 --to review >/dev/null &&
  $AIM task move --as alpha --channel t5 --id T-0001 --to done --force >/dev/null"
expect_ok   "now the dependent item can be done" \
  $AIM task move --as beta --channel t5 --id T-0003 --to done
expect_fail "a dropped task is a record, not a workspace" bash -c "
  $AIM task move --as beta --channel t5 --id T-0002 --to dropped --reason 'superseded' >/dev/null &&
  $AIM task move --as beta --channel t5 --id T-0002 --to ready"
expect_ok   "the task log is covered by aim verify" $AIM verify --channel t5
expect_ok   "--json folds to the same state the list shows" \
  bash -c "$AIM task list --as beta --channel t5 --json | grep -q '\"id\": \"T-0003\"'"

echo "== the id allocator cannot hand the same id to two writers =="
# The old allocator read the id from the *fold*, and the fold collapses duplicate
# ids. So after one collision the counter never recovered: the maximum stayed at
# the colliding id and every later allocation ran on a board that was missing a
# record. Codex found it by racing 8 creators and reading the log rather than the
# board. Measured on the pre-patch code: 8 creators, 5 distinct ids, `chain OK` —
# the chain is intact because nothing was tampered with; two records just claim
# one id, and the fold silently drops one of them.
T5RACE="$AIM_ROOT/t5race"
rm -rf "$T5RACE"; mkdir -p "$T5RACE"
( export AIM_ROOT="$T5RACE"; $AIM init >/dev/null
  AIM_ROOT="$T5RACE" $AIM register --as gamma --kind claude >/dev/null
  AIM_ROOT="$T5RACE" $AIM register --as human2 --kind human >/dev/null
  AIM_ROOT="$T5RACE" $AIM new-channel --id r --topic "id allocation" --participants gamma --leader human2 >/dev/null
  for i in 1 2 3 4 5 6 7 8; do
    AIM_ROOT="$T5RACE" $AIM task new --as gamma --channel r --title "racer $i" >/dev/null 2>&1 &
  done
  wait )
expect_ok   "8 concurrent creations, 8 distinct ids" \
  bash -c "python3 -c \"
import json,collections,sys
ev=[json.loads(l) for l in open('$T5RACE/channels/r/tasks.jsonl')]
ids=[e['task'] for e in ev if e.get('event')=='created']
sys.exit(0 if len(ids)==8 and len(set(ids))==8 else 1)\""
expect_ok   "and the fold shows all 8, not the 5 that survived collapsing" \
  bash -c "python3 -c \"
import json,collections,sys
ev=[json.loads(l) for l in open('$T5RACE/channels/r/tasks.jsonl')]
ids=[e['task'] for e in ev if e.get('event')=='created']
sys.exit(0 if sorted(ids)==['T-%04d'%i for i in range(1,9)] else 1)\""
expect_ok   "the chain still verifies over the raced log" \
  env AIM_ROOT="$T5RACE" $AIM verify --channel r

echo "== the refusal recorder cannot be talked out of recording =="
# Codex's renderer test fixture writes `ledger.jsonl` without `hash` fields, and
# three of its checks assert that a refusal was recorded. Every one of them failed
# for a reason that had nothing to do with the refusal: `append_chained` indexed
# `recs[-1]["hash"]`, so appending onto an unchained tail raised KeyError, `die()`
# swallowed it into a stderr warning, and the refusal was lost.
#
# That is strictly worse than the corruption it came from: from the ledger,
# "nobody was tempted" and "the recorder was broken" look identical — which is the
# one distinction the ledger exists to make. An unchained tail is now tolerated
# loudly: the record is appended, `prev` says `genesis` and `chain_broken` says
# why, so `aim verify` reports it rather than the two records being quietly
# unchained.
LC="$AIM_ROOT/unchained"; rm -rf "$LC"; mkdir -p "$LC/channels/uc"
python3 - "$LC" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1]) / "channels" / "uc"
(d / "manifest.json").write_text(json.dumps({
    "id": "uc", "topic": "unchained ledger", "leader": "human",
    "participants": ["alpha", "beta"], "synthesizer": "",
    "barrier": {"phase": "SEALED_DIVERGENT", "round": 0, "history": []}}))
(d / "registry.json").parent.mkdir(parents=True, exist_ok=True)
PY
# `alpha`/`beta` already exist from the setup block, but this channel lives in its
# own root, so register them here. Without this the refusal below is "unknown
# agent", which is still a refusal and still recorded — the assertions would pass
# for the wrong reason, which is worse than failing. The refusal has to come from
# the gate, so the actor is a registered agent who is *not* a participant.
expect_ok "register beta and an outsider in the unchained root" bash -c "
  AIM_ROOT='$LC' $AIM register --as beta --kind codex >/dev/null &&
  AIM_ROOT='$LC' $AIM register --as outsider --kind claude >/dev/null"
# Exactly the shape codex's fixture writes: a real record, no hash, no prev.
python3 - "$LC" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1]) / "channels" / "uc"
(d / "ledger.jsonl").write_text(json.dumps({
    "ts": "2026-09-21T00:00:06Z", "event": "refusal", "agent": "beta",
    "action": "read_others", "class": "barrier", "phase": "SEALED_DIVERGENT",
    "reason": "REFUSED: no"}) + "\n")
PY
expect_fail "a refusal in an unchained channel is still refused" \
  env AIM_ROOT="$LC" $AIM task new --as outsider --channel uc --title "not mine"
expect_ok   "it was refused by the gate, not by an unknown id" \
  bash -c "env AIM_ROOT='$LC' $AIM task new --as outsider --channel uc --title x 2>&1 | grep -q 'not a participant'"
# The FIRST refusal appended is the one that had to chain onto the unchained tail;
# every later one chains onto it normally. Asserting on `recs[-1]` looked right and
# passed the wrong record through the test, which is how the first version of this
# block was wrong: it asserted the *last* line was unchained, and by then it wasn't.
expect_ok   "and the first refusal is recorded, which is the whole point" \
  bash -c "python3 -c \"
import json,sys
recs=[json.loads(l) for l in open('$LC/channels/uc/ledger.jsonl')]
sys.exit(0 if len(recs)>=2 and recs[1]['event']=='refusal' and recs[1]['agent']=='outsider' else 1)\""
expect_ok   "the record that could not be chained says so, and why" \
  bash -c "python3 -c \"
import json,sys
r=[json.loads(l) for l in open('$LC/channels/uc/ledger.jsonl')][1]
sys.exit(0 if r.get('prev')=='genesis' and 'carries no hash' in (r.get('chain_broken') or '') else 1)\""
expect_ok   "and the record after it chains onto it normally, so the break is one record wide" \
  bash -c "python3 -c \"
import json,sys
recs=[json.loads(l) for l in open('$LC/channels/uc/ledger.jsonl')]
sys.exit(0 if len(recs)>=3 and recs[2].get('prev')==recs[1].get('hash')
         and not recs[2].get('chain_broken') else 1)\""
expect_ok   "no stderr warning is needed, because nothing was dropped" \
  bash -c "! env AIM_ROOT='$LC' $AIM task new --as outsider --channel uc --title x 2>&1 | grep -q 'not recorded'"

echo "== a channel that declares a shared workspace may not claim a barrier =="
# T-0110, and it is the honest version of a confession. `hello` is
# SEALED_DIVERGENT while both participants have been reading each other's files
# for an hour: one of them runs this repo's test suite, the other edits the same
# files, and the fabric notices nothing. From the ledger that channel is
# indistinguishable from a barrier that is holding. An agent reading `bin/aim` is
# sealed from nothing, so a participant cannot be trusted to report its own
# independence — but the manifest can name the shared directory, and then the
# phase gate's precondition is falsified by a fact on disk rather than by a
# promise. That is checkable, which is the whole difference.
WORK="$AIM_ROOT/shared-checkout"
expect_ok   "a channel whose participants name distinct workspaces opens" \
  $AIM new-channel --id dev --topic "shared workspace" --participants alpha,beta --leader human \
    --workspace alpha=/srv/alpha --workspace beta=/srv/beta
expect_fail "a channel that declares one shared workspace cannot open at all" \
  $AIM new-channel --id dev2 --topic "shared" --participants alpha,beta --leader human \
    --workspace alpha="$WORK" --workspace beta="$WORK"
expect_ok   "and the refusal names the manifest, not an agent's word" \
  bash -c "$AIM new-channel --id dev2 --topic shared --participants alpha,beta --leader human \
             --workspace alpha='$WORK' --workspace beta='$WORK' 2>&1 | grep -q \"channel 'dev2' declares a shared workspace\""
# The declaration can arrive after the channel exists, which is why the check
# cannot live only in `new-channel`: the second command would walk past it.
expect_ok   "the declaration can be added to a channel that already exists" \
  $AIM channel workspace --as human --channel dev --set alpha="$WORK" --set beta="$WORK"
expect_fail "and the divergence phase is then refused on advance" \
  $AIM advance --as human --channel dev --to COMMIT
expect_ok   "the refusal says which directory, and who shares it" \
  bash -c "$AIM advance --as human --channel dev --to COMMIT 2>&1 | grep -q 'named by alpha, beta'"
expect_ok   "the shared-workspace refusal is recorded as a barrier event" \
  bash -c "python3 -c \"
import json,sys
rs=[json.loads(l) for l in open('$AIM_ROOT/channels/dev/ledger.jsonl')]
r=[e for e in rs if e.get('event')=='refusal' and e.get('action')=='advance']
sys.exit(0 if r and r[-1]['class']=='barrier' and 'shared workspace' in r[-1]['reason'] else 1)\""
expect_fail "a participant cannot clear the declaration that falsifies its own barrier" \
  $AIM channel workspace --as alpha --channel dev --none
expect_ok   "the leader can, and the clearing is on the record" \
  bash -c "$AIM channel workspace --as human --channel dev --none &&
           python3 -c \"
import json,sys
rs=[json.loads(l) for l in open('$AIM_ROOT/channels/dev/ledger.jsonl')]
c=[e for e in rs if e.get('event')=='workspace_cleared']
sys.exit(0 if c and c[-1]['agent']=='human' and c[-1]['class']=='barrier'
         and c[-1]['cleared']=={'alpha':'$WORK','beta':'$WORK'} else 1)\""
expect_ok   "the phase gate opens again once the claim matches the filesystem" \
  $AIM advance --as human --channel dev --to COMMIT
# One participant naming a directory is a declaration, not a conflict: only a
# path two of them write to falsifies the barrier. The channel is in COMMIT by
# now, so the way to ask is a transition back into divergence — which is also
# the case that would be missed by checking only `new-channel`.
expect_ok   "a workspace named by one participant is not a conflict" \
  bash -c "$AIM channel workspace --as human --channel dev --set alpha='$WORK' 2>&1 | grep -q 'no two of them share'"
# Both halves of this row are the assertion, so neither may be the one that
# decides the exit status. [measured: the first version was `advance …; status |
# grep -q …`, whose rc is grep's — a red advance would have left the row green]
expect_fail "a divergence phase is only reachable through a legal transition" \
  $AIM advance --as human --channel dev --to SEALED_DIVERGENT
expect_ok   "and the forced transition back into divergence is allowed here" \
  $AIM advance --as human --channel dev --to SYNTHESIS --force
expect_ok   "status reports the declaration beside the phase it constrains" \
  bash -c "$AIM status --channel dev | grep -q \"^workspace alpha=$WORK\""
expect_fail "a shared path declared after the fact still refuses the next transition" \
  bash -c "$AIM channel workspace --as human --channel dev --set beta='$WORK' >/dev/null &&
           $AIM advance --as human --channel dev --to COMMIT --force"

echo "== context_id: one channel, two spellings, and the fold accepts both =="
# T-0105, and the accept line names the failure it is guarding against: "the fold
# does not silently drop a task written by an older aim". This is a rename done
# the way a rename in a store with records already on disk has to be done — the
# new field is *added* beside the old one, and every reader accepts either. A
# store that switched spellings instead would leave the records already on disk as
# the only place `channel` exists, which is how a field becomes optional and then
# becomes absent with nobody deciding it.
#
# Its own channel, so the ids and the chains the blocks above assert on cannot
# move. [measured: pointing this at `t` first failed on a missing
# `tasks.jsonl` — `t` is the *message* fixture and has no work items — and then
# a hand-appended record without a hash made `aim verify` report TAMPER. Both
# were the fixture's fault, and the second is the interesting one: an older aim
# wrote a valid chain, so the fixture has to write one too.]
CTXCH=ctx
expect_ok   "open a channel for the rename" \
  $AIM new-channel --id $CTXCH --topic "context_id" --participants alpha,beta --leader human
expect_ok   "a work item in the current store" \
  $AIM task new --as alpha --channel $CTXCH --title "written by the current store"
expect_ok   "a second one, so the ids below are not the first allocation" \
  $AIM task new --as alpha --channel $CTXCH --title "a second one"
expect_ok   "and one that moves and is commented on, to exercise every event kind" \
  bash -c "$AIM task move --as alpha --channel $CTXCH --id T-0001 --to ready >/dev/null &&
           $AIM task assign --as alpha --channel $CTXCH --id T-0001 --owner beta >/dev/null &&
           $AIM task comment --as alpha --channel $CTXCH --id T-0001 --body 'a comment' >/dev/null"
expect_ok   "the store writes context_id beside channel" \
  bash -c "python3 -c \"
import json,sys
e=[json.loads(l) for l in open('$AIM_ROOT/channels/$CTXCH/tasks.jsonl')
   if json.loads(l).get('event')=='created'][0]
sys.exit(0 if e.get('context_id')=='$CTXCH' and e.get('channel')=='$CTXCH' else 1)\""
expect_ok   "every kind of task event carries it, not just the ones that are easy" \
  bash -c "python3 -c \"
import json,sys
ev=[json.loads(l) for l in open('$AIM_ROOT/channels/$CTXCH/tasks.jsonl')]
sys.exit(0 if ev and all(e.get('context_id')=='$CTXCH' for e in ev) else 1)\""
# A `created` record exactly as the pre-T-0105 store wrote it, chained the way the
# store chains — `channel` and no `context_id` — plus a `moved` record for it in
# the same generation, because the interesting case is a task whose *whole*
# history predates the rename. Written through the tool's own append_chained
# rather than by hand: a fixture that writes an unchained record is testing
# `aim verify`, not the fold.
export CTX_TASKS="$AIM_ROOT/channels/$CTXCH/tasks.jsonl"
export CTX_AIM="$AIM"
python3 - <<'PY'
import importlib.machinery, importlib.util, json, os
loader = importlib.machinery.SourceFileLoader("aimtool", os.environ["CTX_AIM"])
spec = importlib.util.spec_from_loader("aimtool", loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)
path = mod.Path(os.environ["CTX_TASKS"])
mod.append_chained(path, {
    "ts": "2026-09-01T00:00:00.000Z", "event": "created", "actor": "alpha",
    "channel": "ctx", "task": "T-0099", "title": "a work item an older aim wrote",
    "owner": "alpha", "status": "backlog", "priority": "normal",
    "visibility": "published", "blocked_by": [],
})
mod.append_chained(path, {
    "ts": "2026-09-01T00:01:00.000Z", "event": "moved", "actor": "alpha",
    "channel": "ctx", "task": "T-0099", "from": "backlog", "to": "ready",
})
print("        (appended two records in the pre-T-0105 shape, properly chained)")
PY
expect_ok   "a task written before the rename is still on the board" \
  bash -c "$AIM task list --as alpha --channel $CTXCH | grep -q 'an older aim wrote'"
expect_ok   "and its later events folded onto it rather than being dropped" \
  bash -c "python3 -c \"
import importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader('aimtool', '$AIM')
spec = importlib.util.spec_from_loader('aimtool', loader)
mod = importlib.util.module_from_spec(spec); loader.exec_module(mod)
t = mod.fold_tasks('$CTXCH')['T-0099']
sys.exit(0 if t['status']=='ready' and len(t['history'])==2 else 1)\""
expect_ok   "the fold reports its context under the A2A name, from either spelling" \
  bash -c "python3 -c \"
import importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader('aimtool', '$AIM')
spec = importlib.util.spec_from_loader('aimtool', loader)
mod = importlib.util.module_from_spec(spec); loader.exec_module(mod)
b = mod.fold_tasks('$CTXCH')
sys.exit(0 if b['T-0099']['context_id']=='$CTXCH' and b['T-0001']['context_id']=='$CTXCH' else 1)\""
expect_ok   "the chain is intact across both generations of writer" \
  $AIM verify --channel $CTXCH

echo "== a verifier cannot die on the input it exists to judge =="
# Every TAMPER line in check_sealed_prefix indexed seal['ts'], so the one path
# whose entire job is to describe damage raised KeyError on a seal that had no
# timestamp. Codex's renderer fixture builds exactly such a seal (agent, digest,
# private_log_hashes, no ts), and `aim verify` crashed on it — which reads as a
# broken tool, not as a finding.
SEALROOT="$AIM_ROOT/tsless"; rm -rf "$SEALROOT"; mkdir -p "$SEALROOT/channels/sc/private" "$SEALROOT/channels/sc/seals"
python3 - "$SEALROOT" <<'PY'
import hashlib, json, pathlib, sys
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha(b): return hashlib.sha256(b).hexdigest()
d = pathlib.Path(sys.argv[1]) / "channels" / "sc"
(d / "manifest.json").write_text(json.dumps({
    "id": "sc", "topic": "tsless seal", "leader": "human", "participants": ["alpha"],
    "synthesizer": "", "barrier": {"phase": "SEALED_DIVERGENT", "round": 0, "history": []}}))
rec = {"ts": "x", "from": "alpha", "kind": "note", "body": "sealed reasoning", "prev": "genesis"}
rec["hash"] = sha(canon(rec).encode())
(d / "private" / "alpha.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n")
seal = {"agent": "alpha", "private_log_hashes": [rec["hash"]]}     # deliberately no `ts`
seal["digest"] = sha(canon(seal).encode())
(d / "seals" / "alpha.json").write_text(json.dumps(seal))
# Now edit the private log so the sealed hashes no longer match, which is what
# reaches the TAMPER line.
rec2 = {"ts": "y", "from": "alpha", "kind": "note", "body": "EDITED", "prev": "genesis"}
rec2["hash"] = sha(canon(rec2).encode())
(d / "private" / "alpha.jsonl").write_text(json.dumps(rec2, ensure_ascii=False) + "\n")
PY
expect_fail "an edited private log under a ts-less seal is caught, not crashed on" \
  env AIM_ROOT="$SEALROOT" $AIM verify --channel sc
expect_ok   "and the TAMPER line says the seal had no timestamp instead of raising" \
  bash -c "env AIM_ROOT='$SEALROOT' $AIM verify --channel sc 2>&1 | grep -q 'no ts recorded in the seal'"
expect_ok   "with no traceback in the output" \
  bash -c "! env AIM_ROOT='$SEALROOT' $AIM verify --channel sc 2>&1 | grep -q 'Traceback'"

echo "== ledger integrity =="
expect_ok "chain verifies" $AIM verify --channel t
# Tamper *after* the last successful verify, so the check is not confounded by
# the files the script itself writes mid-run.
sed_i() { sed -i "$1" "$2"; }
expect_ok "tamper beta private log" sed_i 's/beta private reasoning/beta rewritten reasoning/' "$AIM_ROOT/channels/t/private/beta.jsonl"
expect_fail "tamper is detected" bash -c "$AIM verify --channel t"

echo
printf 'pass=%d fail=%d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
