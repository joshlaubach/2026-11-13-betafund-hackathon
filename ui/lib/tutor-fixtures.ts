// Deterministic tutor replies for NEXT_PUBLIC_FIXTURES=1. No network, no AI.
import type { TutorContext, TutorResponse } from "./tutor-types";

const HINT_REPLY = "**Hint:** look at the outer function first.";
const WORKED_REPLY =
  "A worked example from Echo's problem bank (CR38; bank-verified, not Echo-checked): Find $f'(x)$ for $f(x)=\\sin(x^2+1)$.\n\n" +
  "1. Outer function: $\\sin(u)$.\n2. Multiply by $u'=2x$.";
const UNAVAILABLE = "The tutor is unavailable.";

// A message containing "fail" is checked first, so the error path can always be reached.
export function fixtureTutorReply(message: string, _context: TutorContext | null): TutorResponse {
  const lower = message.toLowerCase();
  if (lower.includes("fail")) return { status: "error", error: UNAVAILABLE };
  if (lower.includes("hint")) {
    return {
      status: "ok",
      reply: HINT_REPLY,
      sources: [],
      actions: [
        { id: "show_next_step", label: "Show the next step", params: {} },
        { id: "check_my_answer", label: "Check my answer", params: {} },
        { id: "worked_example", label: "Show a worked example", params: {} },
      ],
      grounded: false,
      engine: "scripted",
    };
  }
  return {
    status: "ok",
    reply: WORKED_REPLY,
    sources: [
      {
        topic: "chain_rule",
        topic_title: "Chain rule",
        problem_id: "CR38",
        level: 2,
        statement: "Find $f'(x)$ for $f(x)=\\sin(x^2+1)$.",
      },
    ],
    actions: [
      { id: "show_hint", label: "Show a hint", params: {} },
      { id: "harder_problem", label: "Try a harder problem", params: { topic: "chain_rule", level: 3 } },
      { id: "practice_set", label: "Practice 3 similar problems", params: { topic: "chain_rule", level: 2, count: 3 } },
    ],
    grounded: true,
    engine: "scripted",
  };
}
