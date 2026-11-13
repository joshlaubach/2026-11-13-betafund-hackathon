// Mirrors the POST /api/practice/check response. Keep in sync with the server by hand.
import type { PracticeProblem } from "./types";

export type PracticeVerdict = "correct" | "incorrect" | "unable_to_verify";

// An incorrect verdict carries no answer key. The explanation says what was compared, in one sentence.
export interface PracticeCheckOk {
  status: "ok";
  verdict: PracticeVerdict;
  method: "sympy_equivalence";
  checked_by: string;
  checked_at: string;
  explanation: string;
  evidence: string;
}

export type PracticeCheckResponse = PracticeCheckOk | { status: "error"; error: string };

// One answer the student checked, kept in the card's state for the session.
export interface PracticeAttempt {
  answer_latex: string;
  verdict: PracticeVerdict;
}

// What the card reports to its parent after each check or hint, and when it is clicked.
export interface PracticeActivity {
  problem: PracticeProblem;
  attempts: PracticeAttempt[];
  hintsShown: number;
}

export type PracticeCommandKind = "show_hint" | "show_next_step" | "show_solution" | "focus_answer";

// The parent asks the active card to do something. A new nonce means a new request.
export interface PracticeCommand {
  kind: PracticeCommandKind;
  nonce: number;
}
