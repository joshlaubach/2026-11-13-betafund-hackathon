"use client";

import type { ClarifyField, FirstRead, GradedItem, GradeMethod, GradeReason, Mode, Verdict } from "@/lib/types";
import { ClarifyBox } from "./ClarifyBox";
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
// A SymPy-marked row has no Regrade button, so its disagreement line does not mention one.
const DISAGREEMENT_WITHOUT_REGRADE = "Independent AI solves disagreed. Check this one yourself.";

function reasonText(reason: GradeReason, canRegrade: boolean): string | undefined {
  if (reason === "disagreement" && !canRegrade) return DISAGREEMENT_WITHOUT_REGRADE;
  return REASON_LINES[reason];
}

const NOT_MARKED_FALLBACK =
  "It may not be a calculus worksheet, or the photo may be too unclear to read. Try a clearer, closer photo.";

interface Props {
  graded: GradedItem[];
  setup: string;
  notes: string;
  disclaimer: string;
  busyNumber: number | null;
  mode: Mode;
  firstReads: Readonly<Record<number, FirstRead>>;
  onRegrade: (item: GradedItem) => void;
  onCorrect: (entry: GradedItem, field: ClarifyField, latex: string) => void;
}

interface RowProps {
  entry: GradedItem;
  busy: boolean;
  mode: Mode;
  firstRead: FirstRead | undefined;
  onRegrade: (item: GradedItem) => void;
  onCorrect: (entry: GradedItem, field: ClarifyField, latex: string) => void;
}

// The student's final answers, or their whole written line when no final answer was read.
function studentAnswers(entry: GradedItem): string[] {
  const { item } = entry;
  if (item.final_answers_latex.length > 0) return item.final_answers_latex;
  return item.student_answer_latex ? [item.student_answer_latex] : [];
}

function FirstReadLine({ read }: { read: FirstRead }) {
  return (
    <p className="first-read">
      Echo first read:{" "}
      {read.field === "problem" ? <MathText text={read.text} /> : <Tex latex={read.text} />}
    </p>
  );
}

function MarkRow({ entry, busy, mode, firstRead, onRegrade, onCorrect }: RowProps) {
  const { item, grade } = entry;
  const verifiedMethod = VERIFIED_METHODS.includes(grade.method);
  // An unsure mark is never shown as verified, even when its method is a verified one.
  const verified = verifiedMethod && grade.verdict !== "unsure";
  const aiBased = AI_METHODS.includes(grade.method);
  const unsure = grade.verdict === "unsure" || grade.method === "not_graded";
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
  // Only AI-graded rows get the AI edge. A SymPy or unmarked row that is not verified keeps the plain edge.
  const edgeClass = verified ? "row-verified" : aiBased ? "row-ai" : "row-plain";
  // Regrade asks an AI again, so it is offered only for AI-method rows. SymPy marks are never regraded.
  const offerRegrade = aiBased;
  const reasonLine = grade.verdict === "unsure" && grade.reason ? reasonText(grade.reason, offerRegrade) : undefined;
  return (
    <li className={`row ${edgeClass}`}>
      <div className="row-head">
        <span className={`verdict verdict-${grade.verdict}`}>
          <span aria-hidden="true">{VERDICT_GLYPH[grade.verdict]}</span> {VERDICT_WORDS[grade.verdict]}
        </span>
        {item.part_label && <span className="part-label">Part {item.part_label}</span>}
        <span className="source-tag">{tagText}</span>
        {item.corrected_by_user && <span className="corrected-tag">Corrected by you</span>}
      </div>
      <p className="statement">
        <MathText text={item.statement_latex} />
      </p>
      {firstRead && <FirstReadLine read={firstRead} />}
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
      {unsure && (
        // Keyed by the corrected flag, so a box for a row that was just corrected starts empty.
        <ClarifyBox
          key={item.corrected_by_user ? "corrected" : "original"}
          mode={mode}
          busy={busy}
          onUse={(field, latex) => onCorrect(entry, field, latex)}
        />
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

export function WorksheetResults({
  graded,
  setup,
  notes,
  disclaimer,
  busyNumber,
  mode,
  firstReads,
  onRegrade,
  onCorrect,
}: Props) {
  const rows = (
    <ol className="rows">
      {graded.map((entry) => (
        <MarkRow
          key={entry.item.number}
          entry={entry}
          busy={busyNumber === entry.item.number}
          mode={mode}
          firstRead={firstReads[entry.item.number]}
          onRegrade={onRegrade}
          onCorrect={onCorrect}
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
