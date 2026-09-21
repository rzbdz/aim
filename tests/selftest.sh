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
