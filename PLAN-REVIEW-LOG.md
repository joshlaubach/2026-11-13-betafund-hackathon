# Plan review log

Roles: host/planner=claude, reviewer=codex (CLI default, effective gpt-6-sol / high / read-only). Plan: PLAN.md. Max rounds: 5. Review only; no build authorized.

## Round 1 - REVISE
Result: <review-artifacts>/claudex-mwvnxqqi/result.json (plan sha256 65429d07...)
Summary: The plan leaves material gaps in the promised three-problem output and in what a passing answer check proves.
- ECHO-01 (high): five drafts, first three pass; fewer than three could pass. Accepted; added generation guarantee with template top-up.
- ECHO-02 (high): checker predicate and domain undefined (2 log(x) vs 2/x for x<0). Accepted; added checker contract.
- ECHO-03 (medium): SymPy does not check topic/similarity/level. Accepted; added structure and level checks.
- ECHO-04 (medium): no safe input boundary for SymPy parsing. Accepted; restricted grammar, limits.
Limitations noted by reviewer: no code or tests exist to verify.

## Round 2 - REVISE
Result: <review-artifacts>/claudex-ql0hmji4/result.json (plan sha256 fde20d26...)
Summary: Prior four findings addressed; three gaps remain.
- ECHO-05 (medium): no comparison with the confirmed problem. Accepted; function-family match added.
- ECHO-06 (medium): simplification can hide extra singularities. Accepted; unsimplified singularity check added.
- ECHO-07 (medium): grammar cannot parse integral notation/domain. Accepted; structured integrand/variable/domain fields.

## Round 3 - REVISE
Result: <review-artifacts>/claudex-an30sgau/result.json (plan sha256 74bc5160...)
- ECHO-08 (high): key log(-x^2) for the integral of 2x/x^2 on x>0 passes derivative/singularity checks but is not real-valued. Accepted; real-validity check on log/sqrt arguments added.

## Round 4 - REVISE
Result: <review-artifacts>/claudex-cxch26co/result.json (plan sha256 18a336bf...)
- ECHO-09 (high): integrand x/sqrt(x^2) with domain all reals is undefined at 0, and key sqrt(x^2) shares the problem. Accepted; integrand validity check on the stated domain added before key checking.

## Round 5 - REVISE (round cap reached; NOT approved)
Result: <review-artifacts>/claudex-z5xwbcee/result.json (plan sha256 4da025cd...)
- ECHO-10 (medium): valid key sqrt(x^4) for the integral of 2x on all reals is rejected because the sqrt argument is zero at x=0. Host position: not changed. This is a false reject, the safe direction (a candidate is replaced, never a wrong key shown), and the generator controls key forms. Left open for the user; no sixth round run.
Final plan hash 4da025cd... is unapproved.

## Review 2 (new session, rounds reset) - Round 1 - REVISE
Triggered by a second /codex-review after docs/verified_problems.json was added. Reviewer also inspected the substitution entries in that file.
Result: <review-artifacts>/claudex-8v8jc063/result.json (plan sha256 4da025cd...)
- ECHO-11 (high): tan poles not covered by domain checks. Accepted; single continuous-domain rule.
- ECHO-12 (medium): domain input/rendering unspecified. Accepted; typed interval.
- ECHO-10 (medium): sqrt zero rule false-rejects sqrt(x^4). Accepted this time (reversing my round-5 position): the new continuous-domain rule removes the special case, so fixing it is a simplification.
Note: plan does not yet reflect docs/verified_problems.json; pending user decision.

## Review 2 - Round 2 - REVISE
Result: <review-artifacts>/claudex-okoe4ebv/result.json (plan sha256 66dde41c...)
- ECHO-13 (high): SymPy cancellation can hide a hole like (x-1)/(x-1) in a drafted key. Accepted; source-tree check before simplification.
- ECHO-14 (medium): "largest interval containing x=1" may not exist or be representable. Accepted; fixed default interval list.

## Review 2 - Round 3 - REVISE
Result: <review-artifacts>/claudex-u17941ta/result.json (plan sha256 b4c2889f...)
- ECHO-15 (high): fractional powers such as (-1)^(1/2) make a key complex while derivative checks pass. Accepted; separate real-valuedness proof.
## Review 2 - Round 4 - REVISE
Result: <review-artifacts>/claudex-xvl84fez/result.json (plan sha256 a3085871...)
- ECHO-16 (high): mpmath tolerance cannot prove an exact definite key. Accepted; antiderivative-based exact proof.
- ECHO-17 (medium): bank entry C410-06 is improper and fails the closed-interval rule. Accepted; bank adapter filters improper/divergent entries.
- ECHO-18 (medium): checker contract still indefinite-only; bank data exceeds the endpoint grammar. Accepted; two schemas, two routes, adapter.

## Review 2 - Round 5 - REVISE (round cap reached; NOT approved)
Result: <review-artifacts>/claudex-cb1o_rh9/result.json (plan sha256 5bbbb656...)
- ECHO-19 (medium): stale structured-input bullet; pi not whitelisted in the grammar. Accepted and applied after the cap.
- ECHO-20 (medium): candidates need not match the confirmed definite/indefinite type. Accepted and applied after the cap.
The edits for ECHO-19 and ECHO-20 were made after the cap and have NOT been reviewed. Final plan is unapproved.

## Review 3 (new session, rounds reset) started at user request
Covers the post-cap edits (ECHO-19, ECHO-20, relative tolerance rule).

### Review 3 - Round 1 - REVISE
Result: <review-artifacts>/claudex-pbvnl41k/result.json (plan sha256 f1cc01ab...)
- ECHO-21 (high): negative powers hide holes. Accepted.
- ECHO-22 (medium): identity substitution passes the topic check. Accepted.
- ECHO-23 (medium): bank LaTeX and `**` syntax not convertible. Accepted.
- ECHO-24 (medium): 9^(9^9) and uncontained resource use. Accepted.
- ECHO-25 (medium): definite bounds not required finite/real/ordered. Accepted.

### Review 3 - Round 2 - REVISE
Result: <review-artifacts>/claudex-ji2rpyh6/result.json (plan sha256 47c9d181...)
- ECHO-26 (medium): x^2 still fits the template with g=x^3. Accepted; rewritten rule.
- ECHO-27 (medium): excluding linear g rejects bank C410-22 and C410-34. Accepted; composition-node test.
- ECHO-28 (medium): no distinctness check on drafts. Accepted; dedupe and reject equivalents.
- ECHO-29 (low): strict lower<upper rejects valid reversed bounds. Accepted.

### Review 3 - Round 3 - REVISE
Result: <review-artifacts>/claudex-j7t9ydyw/result.json (plan sha256 794967f0...)
- ECHO-30 (medium): (x+1-1)^2 bypasses the structural test. Accepted; normalize first.
- ECHO-31 (medium): f and g have no schema or parsing path. Accepted; typed fields.
- ECHO-32 (medium): bank entry C410-16 (not a substitution problem) could enter test pool. Accepted; apply substitution rule in adapter.

### Review 3 - Round 4 - REVISE
Result: <review-artifacts>/claudex-usd2f9k5/result.json (plan sha256 8cc5a42e...)
- ECHO-33 (medium): bank has no (f, g) pairs for the adapter to check. Accepted; adapter derives and validates pairs.
- ECHO-34 (medium): canceled term x^2 + sin(x+1) - sin(x+1) passes. Accepted; whole-integrand normalization and g correspondence.

### Review 3 - Round 5 - APPROVED
Result: <review-artifacts>/claudex-afxdpdmz/result.json
Approved plan sha256: d28283a81ab2e67418888fc6529bd81348e210b356bdc8b847d11969acc4dbc8 (runner `check` confirmed it matches the current PLAN.md).
Zero findings. Reviewer limitations: no checker or application code exists to inspect; no tests run. Approval covers the plan text only, bound to that hash; any later edit to PLAN.md requires re-review.

User decisions applied before round 4: include definite integrals (indefinite plus definite from the bank); levels were rated by one tutor. Plan gained a "Problem bank" section.

User change after the cap: replaced the absolute 1e-9 numeric tolerance with a relative tolerance rule (1e-9 relative, 1e-12 absolute floor), applied to the spot check and the definite cross-check. Unreviewed.

## Scope change: all of Calculus I and II (user decision: check everything)
PLAN.md was rewritten from integration-by-substitution-only to all 90 bank topics. This VOIDS the approval of sha256 d28283a8... (that approved text is kept outside the repo). The previous integral checker contract is retained as the 'Integral route'. New: scope, per-topic verifier architecture with a bank-based gate (positive and negative tests), measured coverage, bank-verified fallback labels, and an all-topic nearest-neighbor level check. The new plan is UNREVIEWED until a new review session approves it.

### Review 4 (all-calculus scope) - Round 1 - REVISE
Result: claudex-h909zxaq (plan sha256 cc4d8223...). ECHO-35 to ECHO-40 (3 high, 3 medium) all verified against the bank and accepted: bank audit, grammar extension, confirmed answer type, enum handling, short pools, coverage denominator.

### Review 4 - Round 2 - REVISE
Result: claudex-jiz6al0f (plan sha256 717eaeb9...). ECHO-41 (high, empty topic), ECHO-42 (high, tested vs counted), ECHO-43 (medium, unsupported confirmed problem), ECHO-44 (medium, stale CLAUDE.md and README). All accepted; CLAUDE.md, README.md, progress.md and decisions.md updated to the new scope.

### Review 4 - Round 3 - REVISE
Result: claudex-nzl3ugw0 (plan sha256 55dec596...). ECHO-45 to ECHO-49 (all medium) verified against the bank where they cite data, and accepted: both graph topics unsupported, level diversity min(3, L), one positive criterion, problem-only support predicate, product promise limited to AI-drafted problems.

### Review 4 - Round 4 - REVISE
Result: claudex-8m4sl1i2 (plan sha256 f1983b18...). ECHO-50 (high, set and interval-union comparison) and ECHO-51 (medium, integral-property topics) verified against the bank and accepted.

### Review 4 - Round 5 - REVISE (round cap reached; NOT approved)
Result: claudex-2jsq5bu3 (plan sha256 bc2c6772...). ECHO-52 (high): matching on topic, answer type and level lets a different skill through (motion MV01 acceleration vs MV02 speed; verified in the bank). Accepted and applied AFTER the cap: a per-topic task field, matched by drafts and bank fallback; topics without declared tasks are labeled and cannot be enabled. This edit is UNREVIEWED. The current plan is unapproved.

## Review 5 (new session, rounds reset) started at user request: keep going until approved
Covers ECHO-52 and the honesty change: the user reports the organizer approved writing code beforehand if the final submission is before the deadline, so the plan and README no longer say the code is built onsite.

### Review 5 - Round 1 - REVISE
Result: claudex-wz5wyeay (plan sha256 5bbf3ae7...). ECHO-53 (high, displayed text vs verified fields), ECHO-54 to ECHO-57 (medium: unparsed fallback, enum negative cases, set and interval mutations, audit vs integral-property topics). Verified against the bank where they cite data; all accepted.

### Review 5 - Round 2 - REVISE
Result: claudex-q3t78hb3 (plan sha256 9e740e1e...). ECHO-58 (medium, dedupe fields for every topic) and ECHO-59 (medium, servable pool distinct from audit-eligible). Both accepted.

### Review 5 - Round 3 - REVISE
Result: claudex-mmjikc77 (plan sha256 cb6fef95...). ECHO-60 (medium): coverage claims quoted N of 90 and implied bank fallback where the servable pool can be empty. Accepted; pitch, README, CLAUDE.md aligned.

### Review 5 - Round 4 - REVISE
Result: claudex-g5q702ye (plan sha256 70aded6b...). ECHO-61 (medium): unconditional fallback claims remained. Accepted; swept all fallback phrasing in PLAN.md and README.md.

### Review 5 - Round 5 - REVISE (round cap reached; NOT approved)
Result: claudex-izjla_h6 (plan sha256 ecd87b84...). ECHO-62 (medium): the unsupported-confirmed-problem path conditioned the notice on audit-eligible instead of servable entries. Accepted and applied after the cap, together with the same condition in the scope bullet (swept every 'eligible', 'unsupported', and 'none' phrase). UNREVIEWED.

## Review 6 (new session, rounds reset): keep going until approved

### Review 6 - Round 1 - REVISE
Result: claudex-w4mifuup (plan sha256 d159e956...). ECHO-63 (high, template keys unchecked), ECHO-64 (medium, bank top-ups skip family match), ECHO-65 (medium, equal bounds), ECHO-66 (low, level-estimate ties). All accepted.

### Review 6 - Round 3 - APPROVED (recorded below; round 2 follows for the record)
Result: <review-artifacts>/claudex-bzau5imw/result.json
Approved plan sha256: d8268f209cabfd5105b99a6aa71661d329873b94ec073a2423ded1b47b1177d0 (runner `check` confirmed it matches the current PLAN.md). Zero findings. Reviewer limitations: no verifier, audit, or gate code exists to inspect; no tests run. Approval covers the plan text only, bound to that hash; any later edit to PLAN.md requires re-review.

### Review 6 - Round 2 - REVISE
Result: claudex-srdf19q3 (plan sha256 7d3a3d9b...). ECHO-67 (high, disputed bank keys), ECHO-68 (medium, structure rule for disabled-topic fallback), ECHO-69 (medium, definite support needs a valid F). All accepted. While applying ECHO-67 I found two stray sentences left in the gate bullet from earlier rounds (a repeated parse-rate sentence and the old disagreement rule) and replaced them with the quarantine rule.
