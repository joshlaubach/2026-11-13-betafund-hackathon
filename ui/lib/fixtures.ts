// Fake data for design work and for running the page without the Python server.
// Labels here are copied from core/worksheet_types.py so the page shows the same words.
import type { GradeResponse, ProblemsResponse, ReadResponse } from "./types";

export const LABELS = {
  bank_key: "Marked against a verified bank answer, compared by SymPy",
  ai_solve_sympy: "AI-graded: an independent AI solve, compared by SymPy. Not verified by Echo",
  ai_judgment: "AI-graded: AI judgment only. Not verified by Echo",
} as const;

const DISCLAIMER =
  "AI can make mistakes, so marks that are not verified may be wrong. Use Regrade or check any mark you are unsure about.";

export const fixtureRead: ReadResponse = {
  status: "ok",
  source: "FAKE (scripted reading, no model call)",
  label: "FAKE (scripted reading, no model call)",
  error: null,
  reading: {
    notes: "",
    items: [
      { number: 1, statement_latex: "Find $f'(x)$ for $f(x) = 3x^{4} + 2x$.", student_answer_latex: "12x^{3} + 2", topic_guess: "power_rule", confidence: "high", notes: "" },
      { number: 2, statement_latex: "Find $f'(x)$ for $f(x) = x^{5} - 4x^{2}$.", student_answer_latex: "5x^{4} - 4x", topic_guess: "power_rule", confidence: "high", notes: "" },
      { number: 3, statement_latex: "Evaluate $\\displaystyle \\lim_{x \\to 2} \\frac{x^{2}-4}{x-2}$.", student_answer_latex: "4", topic_guess: "algebraic", confidence: "medium", notes: "" },
      { number: 4, statement_latex: "Evaluate $\\displaystyle \\lim_{x \\to 3} \\frac{x^{2}-9}{x-3}$.", student_answer_latex: "0", topic_guess: "algebraic", confidence: "medium", notes: "" },
      { number: 5, statement_latex: "Find $\\frac{d}{dx}\\left[(2x+1)^{3}\\right]$.", student_answer_latex: "3(2x+1)^{2}", topic_guess: "chain_rule", confidence: "medium", notes: "" },
    ],
  },
};

export const fixtureGrade: GradeResponse = {
  disclaimer: DISCLAIMER,
  unplaced: 0,
  summary: { solid: 0, shaky: 1, weak: 2, not_enough_data: 0, problems_seen: 5, verified_marks: 2, ai_marks: 3 },
  skills: [
    { topic: "algebraic", title: "Limits by algebraic manipulation", course: "calc_i", unit: "c1_limits_continuity", correct: 1, incorrect: 1, unsure: 0, status: "shaky", verified_marks: 0 },
    { topic: "power_rule", title: "Power rule", course: "calc_i", unit: "c1_derivatives", correct: 1, incorrect: 1, unsure: 0, status: "shaky", verified_marks: 2 },
    { topic: "chain_rule", title: "Chain rule", course: "calc_i", unit: "c1_derivatives", correct: 0, incorrect: 1, unsure: 0, status: "weak", verified_marks: 0 },
  ],
  recommendations: [
    { rank: 1, topic: "chain_rule", title: "Chain rule", status: "weak", reason: "Got 0 of 1 problems right on this topic.", suggested_level: 1, echo_checked: false },
    { rank: 2, topic: "algebraic", title: "Limits by algebraic manipulation", status: "shaky", reason: "Got 1 of 2 problems right on this topic.", suggested_level: 2, echo_checked: false },
    { rank: 3, topic: "power_rule", title: "Power rule", status: "shaky", reason: "Got 1 of 2 problems right on this topic (2 verified marks).", suggested_level: 2, echo_checked: true },
  ],
  graded: [
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[0], grade: { verdict: "correct", method: "bank_key", label: LABELS.bank_key, reference_answer_latex: "12x^{3} + 2", explanation: "The student's answer equals the verified answer at 10 test points.", bank_topic: "power_rule", bank_id: "PR05" } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[1], grade: { verdict: "incorrect", method: "bank_key", label: LABELS.bank_key, reference_answer_latex: "5x^{4} - 8x", explanation: "At x = 0.3137 the verified answer is -2.50 but the student's answer gives -1.25.", bank_topic: "power_rule", bank_id: "PR09" } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[2], grade: { verdict: "correct", method: "ai_solve_sympy", label: LABELS.ai_solve_sympy, reference_answer_latex: "4", explanation: "An independent AI solve gave 4, and the student's answer is 4.", bank_topic: null, bank_id: null } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[3], grade: { verdict: "incorrect", method: "ai_solve_sympy", label: LABELS.ai_solve_sympy, reference_answer_latex: "6", explanation: "An independent AI solve gave 6, but the student wrote 0.", bank_topic: null, bank_id: null } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[4], grade: { verdict: "incorrect", method: "ai_judgment", label: LABELS.ai_judgment, reference_answer_latex: null, explanation: "The answer leaves out the factor 2 from the inner function.", bank_topic: null, bank_id: null } },
  ],
};

export const fixtureProblems: ProblemsResponse = {
  status: "ok",
  topic: "power_rule",
  level: 2,
  mode_requested: "fake",
  mode_used: "fake",
  notes: ["Scripted drafts, no model call."],
  counts: { echo_checked: 2, bank_fallback: 1 },
  problems: [
    {
      statement: "Find $f'(x)$ for $f(x) = 3x^{4} + 2x$.",
      answer_latex: "12 x^{3} + 2",
      steps: [],
      origin: "echo_checked",
      label: "Echo-checked: key verified by the checker",
      checker: {
        outcome: "accepted",
        reason: "the key matches the checker's derivative at 10 sample points",
        true_answer: "12*x**3 + 2",
        samples: [[0.3137, 2.37, 2.37], [0.7071, 6.24, 6.24], [1.2718, 27.0, 27.0], [1.9319, 88.7, 88.7]],
      },
    },
    {
      statement: "Find $f'(x)$ for $f(x) = 5x^{3} - x$.",
      answer_latex: "15 x^{2} - 1",
      steps: [],
      origin: "echo_checked",
      label: "Echo-checked: key verified by the checker",
      checker: {
        outcome: "accepted",
        reason: "the key matches the checker's derivative at 10 sample points",
        true_answer: "15*x**2 - 1",
        samples: [[0.3137, 0.476, 0.476], [0.7071, 6.5, 6.5], [1.2718, 23.3, 23.3], [1.9319, 54.9, 54.9]],
      },
    },
    {
      statement: "Find $f'(x)$ for $f(x) = x^{4} - 3x$.",
      answer_latex: "4 x^{3} - 3",
      steps: ["Bring the power down and lower it by one."],
      origin: "bank_fallback",
      label: "bank-verified, not Echo-checked",
      level: 2,
      id: "PR12",
    },
  ],
};
