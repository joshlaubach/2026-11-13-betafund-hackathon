// Practice answer checks: one deterministic SymPy comparison per answer. Fixture mode never calls the server.
import { ApiError } from "./api";
import { FIXTURE_CHECKED_AT, FIXTURE_EVIDENCE, FIXTURE_EXPLANATIONS, FIXTURE_UNABLE_EVIDENCE } from "./practice-fixtures";
import type { PracticeCheckOk, PracticeCheckResponse, PracticeVerdict } from "./practice-types";
import type { Mode, PracticeProblem } from "./types";

// Mirrors the request helpers in api.ts, which do not export them. Keep the two in step by hand.
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const USE_FIXTURES = process.env.NEXT_PUBLIC_FIXTURES === "1";
const FIXTURE_DELAY_MS = 700;

function pause<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), FIXTURE_DELAY_MS));
}

// Bank problems are checked by id. Echo-generated problems carry their key instead.
export function practiceCheckBody(topic: string, problem: PracticeProblem, answer: string): Record<string, string> {
  if (problem.id) return { topic, problem_id: problem.id, answer_latex: answer };
  return { topic, problem_id: "", answer_latex: answer, reference_latex: problem.answer_latex };
}

async function postCheck(body: Record<string, string>): Promise<PracticeCheckResponse> {
  let response: Response;
  try {
    response = await fetch(`${BASE}/api/practice/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Could not reach the Echo server. Check that it is running on port 8000.");
  }
  if (!response.ok) throw new ApiError(`The server answered with an error (HTTP ${response.status}).`);
  return (await response.json()) as PracticeCheckResponse;
}

// Spaces are ignored on both sides. A question mark means the answer is not a readable expression.
function fixtureVerdict(problem: PracticeProblem, answer: string): PracticeVerdict {
  if (answer.includes("?")) return "unable_to_verify";
  const squashed = answer.replace(/\s/g, "");
  return squashed === problem.answer_latex.replace(/\s/g, "") ? "correct" : "incorrect";
}

function fixtureCheck(problem: PracticeProblem, answer: string): PracticeCheckOk {
  const verdict = fixtureVerdict(problem, answer);
  return {
    status: "ok",
    verdict,
    method: "sympy_equivalence",
    checked_by: "SymPy",
    checked_at: FIXTURE_CHECKED_AT,
    explanation: FIXTURE_EXPLANATIONS[verdict],
    evidence: verdict === "unable_to_verify" ? FIXTURE_UNABLE_EVIDENCE : FIXTURE_EVIDENCE,
  };
}

// The mode is accepted for parity with the other API calls. The check contract does not send it.
export function checkPracticeAnswer(
  topic: string,
  problem: PracticeProblem,
  answer: string,
  mode: Mode,
): Promise<PracticeCheckResponse> {
  void mode;
  if (USE_FIXTURES) return pause(fixtureCheck(problem, answer));
  return postCheck(practiceCheckBody(topic, problem, answer));
}
