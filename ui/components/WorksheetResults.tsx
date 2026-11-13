"use client";

import type { GradedItem, GradeMethod, GradeReason, Verdict } from "@/lib/types";
import { MathText, Tex } from "./Tex";

const VERDICT_WORDS: Record<Verdict, string> = {
  correct: "Correct",
  incorrect: "Incorrect",
  unsure: "Unsure",
};
const VERDICT_GLYPH: Record<Verdict, string> = { correct: "✓", incorrect: "✗", unsure: "?" };
// Verified marks come from the bank or from SymPy's own computation; AI marks may be regraded.
const VERIFIED_METHODS: readonly GradeMethod[] = ["bank_key", "sympy_computed"];
const AI_METHODS: readonly GradeMethod[] = ["ai_ladder", "ai_solve_sympy", "ai_judgment"];

// One short line under an unsure or not-marked row. "rule" has none: its explanation already names the fix.
const REASON_LINES: Partial<Record<GradeReason, string>> = {
  reading: "Echo could not read this part clearly. Retake a clearer photo of it.",
  format: "Echo could not compare the forms of the answers.",
  disagreement: "Independent AI solves disagreed. Check this one yourself or try Regrade.",
  no_verdict: "The AI gave no answer for this part. Try Regrade.",
};

const NOT_MARKED_FALLBACK =
  "It may not be a calculus worksheet, or the photo may be too unclear to read. Try a clearer, closer photo.";

interface Props {
  graded: GradedItem[];
  setup: string;
  notes: string;
  disclaimer: string;
  busyNumber: number | null;
  onRegrade: (item: GradedItem) => void;
}

interface RowProps {
  entry: GradedItem;
  busy: boolean;
  onRegrade: (item: GradedItem) => void;
}

// The student's final answers, or their whole written line when no final answer was read.
function studentAnswers(entry: GradedItem): string[] {
  const { item } = entry;
  if (item.final_answers_latex.length > 0) return item.final_answers_latex;
  return item.student_answer_latex ? [item.student_answer_latex] : [];
}

function MarkRow({ entry, busy, onRegrade }: RowProps) {
  const { item, grade } = entry;
  const verifiedMethod = VERIFIED_METHODS.includes(grade.method);
  // An unsure mark is never shown as verified, even when its method is a verified one.
  const verified = verifiedMethod && grade.verdict !== "unsure";
  const aiBased = AI_METHODS.includes(grade.method);
  const referenceHeading =
    grade.method === "bank_key" ? "Verified answer" : verifiedMethod ? "SymPy's answer" : "AI's answer";
  const tagText = verified
    ? "Verified mark"
    : grade.method === "not_graded"
      ? "Not marked"
      : verifiedMethod
        ? "Not verified"
        : "AI-graded";
  const answers = studentAnswers(entry);
  const reasonLine = grade.verdict === "unsure" && grade.reason ? REASON_LINES[grade.reason] : undefined;
  // Only AI-graded rows get the AI edge. A SymPy or unmarked row that is not verified keeps the plain edge.
  const edgeClass = verified ? "row-verified" : aiBased ? "row-ai" : "row-plain";
  // Regrade is offered for AI rows, and for unsure rows where no answer came back or the solves disagreed.
  const retryableUnsure =
    grade.verdict === "unsure" && (grade.reason === "no_verdict" || grade.reason === "disagreement");
  const offerRegrade = aiBased || retryableUnsure;
  return (
    <li className={`row ${edgeClass}`}>
      <div className="row-head">
        <span className={`verdict verdict-${grade.verdict}`}>
          <span aria-hidden="true">{VERDICT_GLYPH[grade.verdict]}</span> {VERDICT_WORDS[grade.verdict]}
        </span>
        {item.part_label && <span className="part-label">Part {item.part_label}</span>}
        <span className="source-tag">{tagText}</span>
      </div>
      <p className="statement">
        <MathText text={item.statement_latex} />
      </p>
      <dl className="answers">
        <div>
          <dt>Student&apos;s answer</dt>
          <dd>{answers.length > 0 ? answers.map((answer, index) => <Tex key={index} latex={answer} />) : "Nothing"}</dd>
        </div>
        {grade.reference_answer_latex && (
          <div>
            <dt>{referenceHeading}</dt>
            <dd>
              <Tex latex={grade.reference_answer_latex} />
            </dd>
          </div>
        )}
      </dl>
      {item.student_answer_latex && (
        <details className="working">
          <summary>Show the student&apos;s working</summary>
          <Tex latex={item.student_answer_latex} />
        </details>
      )}
      <p className="explain">{grade.explanation}</p>
      {reasonLine && <p className="explain">{reasonLine}</p>}
      <p className="label">{grade.label}</p>
      {item.explanation_text && (
        <p className="written">
          <span>Written explanation (not graded):</span> {item.explanation_text}
        </p>
      )}
      {entry.changed_on_regrade && (
        <p className="changed" role="status">
          This mark changed when regraded. Treat it with extra care.
        </p>
      )}
      {offerRegrade && (
        <button className="quiet" onClick={() => onRegrade(entry)} disabled={busy}>
          {busy ? "Regrading…" : "Regrade"}
        </button>
      )}
    </li>
  );
}

// True only when there is at least one item and every item is "Not marked".
function allNotMarked(graded: GradedItem[]): boolean {
  return graded.length > 0 && graded.every((entry) => entry.grade.method === "not_graded");
}

function NotMarkedBanner({ notes }: { notes: string }) {
  const reason = notes.trim() || NOT_MARKED_FALLBACK;
  return (
    <p className="disclaimer banner" role="status">
      Echo could not mark anything on this photo. {reason}
    </p>
  );
}

export function WorksheetResults({ graded, setup, notes, disclaimer, busyNumber, onRegrade }: Props) {
  const rows = (
    <ol className="rows">
      {graded.map((entry) => (
        <MarkRow
          key={entry.item.number}
          entry={entry}
          busy={busyNumber === entry.item.number}
          onRegrade={onRegrade}
        />
      ))}
    </ol>
  );
  return (
    <section aria-labelledby="marks-heading">
      <h2 id="marks-heading">Marks</h2>
      {setup && (
        <p className="setup">
          <strong>Worksheet setup:</strong> <MathText text={setup} />
        </p>
      )}
      <p className="disclaimer" role="note">
        {disclaimer}
      </p>
      {allNotMarked(graded) ? (
        <>
          <NotMarkedBanner notes={notes} />
          <details className="all-parts">
            <summary>Show the parts Echo read</summary>
            {rows}
          </details>
        </>
      ) : (
        rows
      )}
    </section>
  );
}
