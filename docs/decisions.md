# Decisions

Newest first. Each entry: date, decision, reason.

- **2026-11-12: Mark a finished worksheet, with SymPy before AI.** The reader separates the questions, final answers, and shared setup. Grading checks an eligible bank match first, then asks SymPy to compute a reference for supported forms. AI handles the rest. Reason: show when a mark rests on a computed answer and when it rests on AI.
- **2026-11-12: Use a small, blind model ladder.** Two models solve without the student's answer. A third breaks a disagreement; a judge handles answers that cannot be compared as math. A SymPy cross-check uses one blind solve and can only confirm the mark or make it unsure. Reason: avoid treating an AI answer as verified or letting an AI override a computed result.
- **2026-11-12: Do not mark a low-confidence read.** Live and fake grading return “Not marked” when the reader flags a part as unclear. Reason: an uncertain transcription should not look like a checked answer. Replay grading has a separate path; see known issues.
- **2026-11-12: Strip photo metadata on upload.** The server runs image bytes through the metadata stripper before reading or hashing. Echo does not write image bytes into its replay files. Reason: remove location and other photo metadata from supported images before the model sees them.
- **2026-11-12: Keep the demo API on localhost.** Compose binds both ports to `127.0.0.1`; the API checks Host, write Origin, and body size. Reason: the API has no login and the profile endpoint trusts client-supplied marks.
- **2026-11-12: Plan a correction step after reading.** A typed clarification flow is planned, with voice optional. It is not on the current page. Reason: a bad transcription can spoil every later mark, and the current page only asks the user to compare the reading with the photo.

- **2026-11-12: Reuse `app/` from the author's existing AI math tutor, and disclose it.** The folder holds per-topic verifiers, a safe parser, a sandbox, and offline samplers, so the build becomes an adapter and a gate around existing code instead of new verifiers. The README says where it came from. Open question: confirm with the organizer that "written beforehand" covers reusing code from an existing product, not just code written for this event. Recommended direction: tighten the code to the approved plan's limits rather than amend the plan.

- **2026-11-12: Code is written before the event.** The organizer approved writing code beforehand, as long as the final submission is made before the deadline. Reason: the user's statement. Consequence: the plan, README, and pitch say the code was prepared beforehand with the organizer's approval, not "built onsite."

- **2026-11-12: Scope is all of Calculus I and II, with a measured-coverage gate.** The user chose "check everything." Each topic needs its own verifier, enabled only after it passes positive and negative tests against the bank. Topics without an enabled verifier serve bank problems labeled "bank-verified, not Echo-checked." Reason: 90 verifiers across six answer formats may not all land by Friday, and the label keeps every claim honest. This voided the earlier substitution-only approval.

- **2026-11-12: Numeric comparisons use a relative tolerance.** |a - b| <= 1e-9 * max(|a|, |b|), with a 1e-12 absolute floor. Reason: a fixed absolute 1e-9 is too loose for tiny values and too strict for large ones. Tolerances never prove a key exact; exactness is always symbolic.
- **2026-11-12: Levels are described as rated by one tutor.** Reason: the bank levels were rated by one tutor, with no second rater.
- **2026-11-12: Definite integrals are in scope.** Reason: user choice, which roughly doubles the usable bank per level. Cost: a second checker route; definite keys are proven exact through an antiderivative F, as F(upper) - F(lower).
- **2026-11-12: The bank is the primary top-up and few-shot source.** Templates come after the bank. Reason: bank problems are pre-verified and level-rated.
- **2026-11-12: `echo/` is its own repo**, nested inside `math-problem-generator` and ignored by that parent repo. Reason: the hackathon repo must have `echo` as its root.
- **2026-11-12: Plan changes go through Codex review.** Approval is bound to the plan's SHA256. Reason: an independent check on the checker contract, which is the product's core claim.
