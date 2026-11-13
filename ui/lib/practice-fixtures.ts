// Fixed results for fixture mode (NEXT_PUBLIC_FIXTURES=1), so practice checks are deterministic in tests.
import type { PracticeVerdict } from "./practice-types";

export const FIXTURE_CHECKED_AT = "2026-11-13T14:41:07.000Z";

export const FIXTURE_EVIDENCE = "compared at 10 sample points by numeric evaluation";
export const FIXTURE_UNABLE_EVIDENCE = "no comparison was made";

export const FIXTURE_EXPLANATIONS: Record<PracticeVerdict, string> = {
  correct: "SymPy found this answer equal to the key.",
  incorrect: "SymPy found this answer is not equal to the key.",
  unable_to_verify: "Echo could not read this answer as a math expression, so it makes no claim about it.",
};
