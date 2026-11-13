# Decisions

Newest first. Each entry: date, decision, reason.

- **2026-11-12: Code is written before the event.** The organizer approved writing code beforehand, as long as the final submission is made before the deadline. Reason: the user's statement. Consequence: the plan, README, and pitch say the code was prepared beforehand with the organizer's approval, not "built onsite."

- **2026-11-12: Scope is all of Calculus I and II, with a measured-coverage gate.** The user chose "check everything." Each topic needs its own verifier, enabled only after it passes positive and negative tests against the bank. Topics without an enabled verifier serve bank problems labeled "bank-verified, not Echo-checked." Reason: 90 verifiers across six answer formats may not all land by Friday, and the label keeps every claim honest. This voided the earlier substitution-only approval.

- **2026-11-12: Numeric comparisons use a relative tolerance.** |a - b| <= 1e-9 * max(|a|, |b|), with a 1e-12 absolute floor. Reason: a fixed absolute 1e-9 is too loose for tiny values and too strict for large ones. Tolerances never prove a key exact; exactness is always symbolic.
- **2026-11-12: Levels are described as rated by one tutor.** Reason: the bank levels were rated by one tutor, with no second rater.
- **2026-11-12: Definite integrals are in scope.** Reason: user choice, which roughly doubles the usable bank per level. Cost: a second checker route; definite keys are proven exact through an antiderivative F, as F(upper) - F(lower).
- **2026-11-12: The bank is the primary top-up and few-shot source.** Templates come after the bank. Reason: bank problems are pre-verified and level-rated.
- **2026-11-12: `echo/` is its own repo**, nested inside `math-problem-generator` and ignored by that parent repo. Reason: the hackathon repo must have `echo` as its root.
- **2026-11-12: Plan changes go through Codex review.** Approval is bound to the plan's SHA256. Reason: an independent check on the checker contract, which is the product's core claim.
