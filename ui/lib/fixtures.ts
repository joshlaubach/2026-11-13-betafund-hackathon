// Fake data for design work and for running the page without the Python server.
// Labels here are copied from core/worksheet_types.py so the page shows the same words.
import type {
  AskResponse,
  ClarifyResponse,
  GradedItem,
  GradeMethod,
  GradeReason,
  GradeResponse,
  PracticeProblem,
  ProblemsResponse,
  ReadResponse,
  WorksheetItem,
  WorksheetReading,
} from "./types";

export const LABELS = {
  bank_key: "Marked against a verified bank answer, compared by SymPy",
  sympy_computed: "Marked by Echo's checker: SymPy computed the answer itself",
  ai_ladder: "AI-graded: independent AI solves agree. SymPy only compared answers; the AI's answer is unchecked. Not verified by Echo",
  ai_solve_sympy: "AI-graded: an AI solved it and SymPy compared the two answers. SymPy did not check the AI's answer. Not verified by Echo",
  ai_judgment: "AI-graded: AI judgment only. Not verified by Echo",
  not_graded: "Not marked: Echo was not confident it read this part correctly",
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

// A part for the reason rows below. Its statement and answer are plain text, not LaTeX.
function reasonItem(number: number, partLabel: string, statement: string, answer: string): WorksheetItem {
  return {
    number, part_label: partLabel, statement_latex: statement,
    student_answer_latex: answer, final_answers_latex: [answer], explanation_text: "",
    context_latex: DRONE_CONTEXT, topic_guess: null, confidence: "high", notes: "",
  };
}

// One unsure row for a reason. Its explanation is the wording the server sends for that case.
function reasonRow(
  number: number,
  partLabel: string,
  statement: string,
  answer: string,
  method: GradeMethod,
  reason: GradeReason,
  explanation: string,
): GradedItem {
  return {
    regraded: false,
    changed_on_regrade: false,
    item: reasonItem(number, partLabel, statement, answer),
    grade: {
      verdict: "unsure", method, label: LABELS[method], reference_answer_latex: null,
      explanation, bank_topic: null, bank_id: null, reason,
    },
  };
}

// Fixture mode shows one row of each reason, so every reason line and Regrade case is visible.
const REASON_ROWS: GradedItem[] = [
  reasonRow(5, "e", "Find the total distance.", "3", "not_graded", "reading",
    "The writing for this part was faint or unclear, so Echo did not mark it. Compare the reading with the photo, then try a clearer photo."),
  reasonRow(6, "f", "Describe the shape of the velocity.", "a curve", "ai_judgment", "format",
    "the student's answer could not be read by SymPy, so this mark is unsure."),
  reasonRow(7, "g", "Find the slope at the end.", "2", "ai_ladder", "disagreement",
    "The three AI solves gave 2, 3, and 4; no two agree, so this mark is unsure."),
  reasonRow(8, "h", "Explain the velocity trend.", "rising", "ai_judgment", "no_verdict",
    "the AI judge could not give a verdict, so this mark is unsure."),
  reasonRow(9, "i", "Find the antiderivative of 3.", "3x", "sympy_computed", "rule",
    "answers differ by a constant; check for + C"),
  reasonRow(10, "j", "Find the slope of the curve at x = 1.", "5", "sympy_computed", "disagreement",
    "SymPy computed 2, and the AI cross-check gave 3, so this mark is unsure."),
];

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
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[0], grade: { verdict: "correct", method: "sympy_computed", label: LABELS.sympy_computed, reference_answer_latex: "0", explanation: "The student's answer 0 matches SymPy's computed answer 0 at 10 sample points, checked by SymPy. An independent AI solve agreed with SymPy's answer.", bank_topic: null, bank_id: null, reason: null } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[1], grade: { verdict: "incorrect", method: "sympy_computed", label: LABELS.sympy_computed, reference_answer_latex: "4 + e^{-5}", explanation: "The student's answer 6 - e^{5} does not match SymPy's computed answer 4 + e^{-5}: SymPy found different values at a sample point.", bank_topic: null, bank_id: null, reason: null } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[2], grade: { verdict: "correct", method: "sympy_computed", label: LABELS.sympy_computed, reference_answer_latex: "e^{- t}; 1", explanation: "v'(t): SymPy computes e^{- t}; the student wrote e^{-t}. v'(0): SymPy computes 1; the student wrote 1. An independent AI solve agreed with SymPy's answer.", bank_topic: null, bank_id: null, reason: null } },
    { regraded: false, changed_on_regrade: false, item: fixtureRead.reading!.items[3], grade: { verdict: "correct", method: "ai_ladder", label: LABELS.ai_ladder, reference_answer_latex: "1", explanation: "The student's answer 1 matches the agreed AI answer 1 at 10 sample points, checked by SymPy. 2 of 2 independent AI solves agree.", bank_topic: null, bank_id: null, reason: null } },
    ...REASON_ROWS,
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

// A count (streak pools ask for one) gets the scripted problems first, padded with distinct bank-style ones up to it.
export function fixtureProblemsFor(count?: number): PracticeProblem[] {
  const problems = [...fixtureProblems.problems];
  for (let k = problems.length; count !== undefined && problems.length < count; k++) {
    problems.push({
      statement: `Find $f'(x)$ for $f(x) = ${k + 1}x^{2} + ${k}$.`,
      answer_latex: `${2 * (k + 1)} x`,
      steps: [],
      origin: "bank_fallback",
      label: "bank-verified, not Echo-checked",
      level: 2,
      id: `PRF${k}`,
    });
  }
  return problems;
}

// A photo whose every part comes back "Not marked". Chosen by a file name containing UNMARKED_FILE_TAG.
export const UNMARKED_FILE_TAG = "greek";
export const UNMARKED_NOTES =
  "The photo shows a list of Greek letters, not calculus problems, so no part could be read as a problem.";
const UNMARKED_EXPLANATION =
  "The writing for this part was faint or unclear, so Echo did not mark it. Compare the reading with the photo, then try a clearer photo.";

export const fixtureReadUnmarked: ReadResponse = {
  status: "ok",
  source: "FAKE (scripted reading, no model call)",
  label: "FAKE (scripted reading, no model call)",
  error: null,
  reading: {
    notes: UNMARKED_NOTES,
    shared_context: "",
    items: [
      {
        number: 1, part_label: "a", statement_latex: "alpha beta gamma",
        student_answer_latex: null, final_answers_latex: [], explanation_text: "",
        context_latex: "", topic_guess: null, confidence: "low", notes: "",
      },
      {
        number: 2, part_label: "b", statement_latex: "delta epsilon zeta",
        student_answer_latex: null, final_answers_latex: [], explanation_text: "",
        context_latex: "", topic_guess: null, confidence: "low", notes: "",
      },
    ],
  },
};

export const fixtureGradeUnmarked: GradeResponse = {
  disclaimer: DISCLAIMER,
  unplaced: 0,
  summary: { solid: 0, shaky: 0, weak: 0, not_enough_data: 0, problems_seen: 2, verified_marks: 0, ai_marks: 0 },
  skills: [],
  recommendations: [],
  graded: fixtureReadUnmarked.reading!.items.map((item) => ({
    regraded: false,
    changed_on_regrade: false,
    item,
    grade: {
      verdict: "unsure",
      method: "not_graded",
      label: LABELS.not_graded,
      reference_answer_latex: null,
      explanation: UNMARKED_EXPLANATION,
      bank_topic: null,
      bank_id: null,
      reason: "reading",
    },
  })),
};

// Fixture mode understands a few phrases. Anything else is shown as plain text, with a note.
const CLARIFY_PHRASES: Record<string, string> = {
  "derivative of x squared": "\\frac{d}{dx}\\left(x^{2}\\right)",
};
const FIXTURE_CLARIFY_NOTE = "scripted: fixture mode understands only a few phrases";
const CORRECTED_REFERENCE = "2x";

export function fixtureClarify(text: string): ClarifyResponse {
  const latex = CLARIFY_PHRASES[text.trim().toLowerCase()];
  if (latex) return { status: "ok", latex, notes: "" };
  const plain = text.replace(/[{}\\]/g, "");
  return { status: "ok", latex: "\\text{" + plain + "}", notes: FIXTURE_CLARIFY_NOTE };
}

// Ask Echo in fixture mode: a scripted note that shows the question, so a test can see it.
export function fixtureAsk(question: string): AskResponse {
  return {
    status: "ok",
    answer: `Echo's note on this part: scripted reply to "${question}". Nothing here changes the mark.`,
  };
}

// A corrected row gets a verified-looking mark: SymPy computes the reference, so the method is
// sympy_computed. The fixture's reference is 2x, and the student's answer is compared with it.
function fixtureCorrectedGrade(item: WorksheetItem): GradedItem {
  const answer = (item.final_answers_latex.join("; ") || item.student_answer_latex || "").trim();
  const matches = answer.replace(/\s/g, "") === CORRECTED_REFERENCE;
  const verdict = matches ? "correct" : "incorrect";
  const comparison = matches ? "matches" : "does not match";
  return {
    regraded: false,
    changed_on_regrade: false,
    item,
    grade: {
      verdict,
      method: "sympy_computed",
      label: LABELS.sympy_computed,
      reference_answer_latex: CORRECTED_REFERENCE,
      explanation: `The student's answer ${answer} ${comparison} SymPy's computed answer ${CORRECTED_REFERENCE}, checked by SymPy. The statement was confirmed by you.`,
      bank_topic: null,
      bank_id: null,
      reason: null,
    },
  };
}

// The grade for a reading that holds only corrected items, as the server returns it for one part.
export function fixtureGradeCorrected(reading: WorksheetReading): GradeResponse {
  return {
    ...fixtureGrade,
    graded: reading.items.map((item) => fixtureCorrectedGrade(item)),
  };
}
