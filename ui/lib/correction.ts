// Pure helpers for a student's correction to one row. No React and no network here.
import type { ClarifyField, FirstRead, WorksheetItem } from "./types";

// The part as it will be graded after the student confirms a clarified reading. Confidence is set
// to high because the student has checked it; the server never grades a low-confidence part.
export function correctItem(item: WorksheetItem, field: ClarifyField, latex: string): WorksheetItem {
  const clean = latex.replace(/\$/g, "").trim();
  if (field === "problem") {
    return { ...item, statement_latex: `$${clean}$`, confidence: "high", corrected_by_user: true };
  }
  // The grader compares final answers, so the corrected answer replaces them too.
  return {
    ...item,
    student_answer_latex: clean,
    final_answers_latex: [clean],
    confidence: "high",
    corrected_by_user: true,
  };
}

// What Echo first read for the field, shown as "Echo first read" beside the corrected row.
export function firstReadOf(item: WorksheetItem, field: ClarifyField): FirstRead {
  if (field === "problem") return { field, text: item.statement_latex };
  const answers = item.final_answers_latex.length > 0 ? item.final_answers_latex.join("; ") : item.student_answer_latex ?? "";
  return { field, text: answers };
}
