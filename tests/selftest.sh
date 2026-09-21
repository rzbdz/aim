#!/usr/bin/env bash
# Barrier self-test. Runs entirely inside a throwaway AIM_ROOT so it never
# touches real channels. Every REFUSED below is the feature, not a bug.
set -u
export AIM_ROOT="${AIM_ROOT:-/root/tmp/agent-im/.selftest}"
rm -rf "$AIM_ROOT"; mkdir -p "$AIM_ROOT"
AIM=/root/tmp/agent-im/bin/aim

pass=0; fail=0
expect_ok()   { local d="$1"; shift; if "$@" >/tmp/st.out 2>/tmp/st.err; then pass=$((pass+1)); printf '  ok    %s\n' "$d"; else fail=$((fail+1)); printf '  FAIL  %s (expected success)\n' "$d"; sed 's/^/          /' /tmp/st.err; fi; }
expect_fail() { local d="$1"; shift; if "$@" >/tmp/st.out 2>/tmp/st.err; then fail=$((fail+1)); printf '  FAIL  %s (expected refusal, got success)\n' "$d"; else pass=$((pass+1)); printf '  ok    %s\n' "$d"; printf '          -> %s\n' "$(head -1 /tmp/st.err)"; fi; }

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
