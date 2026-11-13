// Mirrors core/worksheet_types.py and the dicts from core/entry.py. Keep in sync by hand.

export type Verdict = "correct" | "incorrect" | "unsure";
export type GradeMethod =
  | "bank_key"
  | "sympy_computed"
  | "ai_ladder"
  | "ai_solve_sympy"
  | "ai_judgment"
  | "not_graded";
export type SkillStatus = "solid" | "shaky" | "weak" | "not_enough_data";
// Why an unsure or not-marked grade is unsure. null for correct and incorrect grades.
export type GradeReason = "reading" | "format" | "disagreement" | "no_verdict" | "rule";
export type Mode = "live" | "replay" | "fake" | "bank";

export interface WorksheetItem {
  number: number;
  statement_latex: string;
  student_answer_latex: string | null;
  topic_guess: string | null;
  confidence: "low" | "medium" | "high";
  notes: string;
  part_label: string | null;
  context_latex: string;
  final_answers_latex: string[];
  explanation_text: string;
  // Optional so saved replays from before this field still load. The server always sends it.
  corrected_by_user?: boolean;
}

// Which part of a row the student clarified: the problem, or their answer.
export type ClarifyField = "problem" | "answer";

// What the page showed the student before a correction, kept so it is never silently overwritten.
export interface FirstRead {
  field: ClarifyField;
  text: string;
}

export type ClarifyResponse =
  | { status: "ok"; latex: string; notes: string }
  | { status: "error"; error: string };

// The row Ask Echo explains. Every field is a string; "" means none. Read-only: it never changes a mark.
export interface AskRow {
  statement_latex: string;
  student_answer_latex: string;
  reference_answer_latex: string;
  method: GradeMethod;
  verdict: Verdict;
  reason: string;
  explanation: string;
  label: string;
}

export type AskResponse = { status: "ok"; answer: string } | { status: "error"; error: string };

export interface WorksheetReading {
  items: WorksheetItem[];
  notes: string;
  shared_context: string;
}

export interface Grade {
  verdict: Verdict;
  method: GradeMethod;
  label: string;
  reference_answer_latex: string | null;
  explanation: string;
  bank_topic: string | null;
  bank_id: string | null;
  reason: GradeReason | null;
  // Whether the mark was verified, apart from what it says. Added by the server; absent in older saved grades.
  verification?: "verified" | "unverified" | "unavailable";
}

export interface GradedItem {
  item: WorksheetItem;
  grade: Grade;
  regraded: boolean;
  changed_on_regrade: boolean;
}

export interface TopicSkill {
  topic: string;
  title: string;
  course: string;
  unit: string;
  correct: number;
  incorrect: number;
  unsure: number;
  status: SkillStatus;
  verified_marks: number;
}

export interface Recommendation {
  rank: number;
  topic: string;
  title: string;
  status: SkillStatus;
  reason: string;
  suggested_level: number;
  echo_checked: boolean;
}

export interface Summary {
  solid: number;
  shaky: number;
  weak: number;
  not_enough_data: number;
  problems_seen: number;
  verified_marks: number;
  ai_marks: number;
}

export interface ReadResponse {
  status: "ok" | "error" | "unreadable";
  source: string;
  label: string;
  reading: WorksheetReading | null;
  error: string | null;
}

export interface GradeResponse {
  graded: GradedItem[];
  skills: TopicSkill[];
  unplaced: number;
  summary: Summary;
  recommendations: Recommendation[];
  disclaimer: string;
}

export interface CheckerReceipt {
  outcome: string;
  reason: string;
  true_answer: string;
  samples: [number, number, number][]; // x, checker value, key value
}

export interface PracticeProblem {
  statement: string;
  answer_latex: string;
  steps: string[];
  origin: "echo_checked" | "bank_fallback" | "replay_echo_checked";
  label: string;
  level?: number;
  id?: string;
  checker?: CheckerReceipt;
}

export interface ProblemsResponse {
  status: "ok" | "partial" | "unsupported" | "error";
  topic: string;
  level: number;
  mode_requested: string;
  mode_used: string;
  notes: string[];
  problems: PracticeProblem[];
  counts: { echo_checked: number; bank_fallback: number };
}
