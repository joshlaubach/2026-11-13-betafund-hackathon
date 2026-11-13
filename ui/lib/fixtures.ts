// Fake data for design work and for running the page without the Python server.
// Labels here are copied from core/worksheet_types.py so the page shows the same words.
import type { GradeResponse, ProblemsResponse, ReadResponse } from "./types";

export const LABELS = {
  bank_key: "Marked against a verified bank answer, compared by SymPy",
  sympy_computed: "Marked by Echo's checker: SymPy computed the answer itself",
  ai_ladder: "AI-graded: independent AI solves agree. SymPy only compared answers; the AI's answer is unchecked. Not verified by Echo",
  ai_solve_sympy: "AI-graded: an AI solved it and SymPy compared the two answers. SymPy did not check the AI's answer. Not verified by Echo",
  ai_judgment: "AI-graded: AI judgment only. Not verified by Echo",
} as const;

const DISCLAIMER =
  "AI can make mistakes, so marks that are not verified may be wrong. Use Regrade or check any mark you are unsure about.";

const DRONE_CONTEXT = "A drone has velocity v(t) = 1 - e^{-t}.";

export const fixtureRead: ReadResponse = {
  status: "ok",
  source: "FAKE (scripted reading, no model call)",
  label: "FAKE (scripted reading, no model call)",
  error: null,
  reading: {
    notes: "",
    shared_context: DRONE_CONTEXT,
    items: [
      {
        number: 1, part_label: "a", statement_latex: "Compute $v(0)$.",
        student_answer_latex: "v(0) = 1 - e^{0} = 0. The drone starts at rest.",
        final_answers_latex: ["v(0) = 0"], explanation_text: "The drone starts at rest.",
        context_latex: DRONE_CONTEXT, topic_guess: null, confidence: "high", notes: "",
      },
      {
        number: 2, part_label: "b", statement_latex: "Compute $\int_0^5 v(t)\,dt$.",
        student_answer_latex: "\int_0^5 v(t)\,dt = 6 - e^{5}. The total distance is 6 - e^{5}.",
        final_answers_latex: ["6 - e^{5}"], explanation_text: "The total distance is 6 - e^{5}.",
        context_latex: DRONE_CONTEXT, topic_guess: null, confidence: "high", notes: "",
      },
      {
        number: 3, part_label: "c", statement_latex: "Find $v'(t)$. Compute $v'(0)$.",
        student_answer_latex: "v'(t) = e^{-t}, so v'(0) = 1. The acceleration starts at 1.",
        final_answers_latex: ["v'(t) = e^{-t}", "v'(0) = 1"], explanation_text: "The acceleration starts at 1.",
        context_latex: DRONE_CONTEXT, topic_guess: null, confidence: "high", notes: "",
      },
      {
        number: 4, part_label: "d", statement_latex: "Find $\lim_{t \to \infty} v(t)$.",
        student_answer_latex: "1. The velocity levels off at 1.",
        final_answers_latex: ["1"], explanation_text: "The velocity levels off at 1.",
        context_latex: DRONE_CONTEXT, topic_guess: "algebraic", confidence: "medium", notes: "",
      },
    ],
  },
};

export const fixtureGrade: GradeResponse = {
  disclaimer: DISCLAIMER,
  unplaced: 3,
  summary: { solid: 0, shaky: 1, weak: 2, not_enough_data: 0, problems_seen: 4, verified_marks: 3, ai_marks: 1 },
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
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[0], grade: { verdict: "correct", method: "sympy_computed", label: LABELS.sympy_computed, reference_answer_latex: "0", explanation: "The student's answer 0 matches SymPy's computed answer 0 at 10 sample points, checked by SymPy. An independent AI solve agreed with SymPy's answer.", bank_topic: null, bank_id: null } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[1], grade: { verdict: "incorrect", method: "sympy_computed", label: LABELS.sympy_computed, reference_answer_latex: "4 + e^{-5}", explanation: "The student's answer 6 - e^{5} does not match SymPy's computed answer 4 + e^{-5}: SymPy found different values at a sample point.", bank_topic: null, bank_id: null } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[2], grade: { verdict: "correct", method: "sympy_computed", label: LABELS.sympy_computed, reference_answer_latex: "e^{- t}; 1", explanation: "v'(t): SymPy computes e^{- t}; the student wrote e^{-t}. v'(0): SymPy computes 1; the student wrote 1. An independent AI solve agreed with SymPy's answer.", bank_topic: null, bank_id: null } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[3], grade: { verdict: "correct", method: "ai_ladder", label: LABELS.ai_ladder, reference_answer_latex: "1", explanation: "The student's answer 1 matches the agreed AI answer 1 at 10 sample points, checked by SymPy. 2 of 2 independent AI solves agree.", bank_topic: null, bank_id: null } },
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
