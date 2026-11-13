"use client";

import type {
  AskRow,
  ClarifyField,
  FirstRead,
  GradedItem,
  GradeMethod,
  GradeReason,
  Mode,
  Verdict,
} from "@/lib/types";
import { AskBox } from "./AskBox";
import { ClarifyBox } from "./ClarifyBox";
import { StaggerItem } from "./Motion";
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

// What each way of marking can and cannot show. Written from how core/grading actually works.
const LIMITS: Record<GradeMethod, string> = {
  bank_key:
    "The answer matched the stored key for a verified bank problem. Echo did not re-derive the key, and the mark is only as good as Echo's reading of the photo.",
  sympy_computed:
    "SymPy computed the answer from the problem as Echo read it. If the handwriting was misread, this mark is wrong too.",
  ai_ladder:
    "Independent AI solves agreed. SymPy only compared the answers; it did not check the AI's answer. AI can be wrong.",
  ai_solve_sympy:
    "An AI solved it and SymPy compared the two answers. SymPy did not check the AI's answer. AI can be wrong.",
  ai_judgment: "An AI judged this answer. Echo has not computed it, so treat it as a second opinion.",
  not_graded: "Echo did not mark this part, so nothing here is a result.",
};

// How sure the AI reader was about the handwriting. Kept apart from the math check: a correct calculation on a
// misread line proves nothing about what the student wrote.
const READING_WORDS: Record<"low" | "medium" | "high", string> = {
  high: "The AI reader was confident it read this part correctly.",
  medium: "The AI reader was fairly confident it read this part correctly. Compare it with the photo.",
  low: "The AI reader was not confident it read this part correctly. Compare it with the photo.",
};

function readingLine(item: GradedItem["item"]): string {
  const base = item.corrected_by_user ? "You confirmed this reading yourself." : READING_WORDS[item.confidence];
  return `${base} This is separate from the math check below.`;
}

// A glyph for each status, so a status never depends on color alone.
const STATUS_GLYPH: Record<string, string> = {
  "Echo verified": "✓",
  "Bank confirmed": "✓",
  "AI-graded, unverified": "◐",
  "Unable to verify": "?",
};

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
  onStartStreak?: (entry: GradedItem) => void;
}

interface RowProps {
  index: number;
  entry: GradedItem;
  busy: boolean;
  mode: Mode;
  firstRead: FirstRead | undefined;
  onRegrade: (item: GradedItem) => void;
  onCorrect: (entry: GradedItem, field: ClarifyField, latex: string) => void;
  onStartStreak?: (entry: GradedItem) => void;
}

// The student's final answers, or their whole written line when no final answer was read.
function studentAnswers(entry: GradedItem): string[] {
  const { item } = entry;
  if (item.final_answers_latex.length > 0) return item.final_answers_latex;
  return item.student_answer_latex ? [item.student_answer_latex] : [];
}

// What Ask Echo sees about one row. Read-only: it is never used to change the mark.
function askRowOf(entry: GradedItem): AskRow {
  const { item, grade } = entry;
  return {
    statement_latex: item.statement_latex,
    student_answer_latex: studentAnswers(entry).join("; "),
    reference_answer_latex: grade.reference_answer_latex ?? "",
    method: grade.method,
    verdict: grade.verdict,
    reason: grade.reason ?? "",
    explanation: grade.explanation,
    label: grade.label,
  };
}

function FirstReadLine({ read }: { read: FirstRead }) {
  return (
    <p className="first-read">
      Echo first read:{" "}
      {read.field === "problem" ? <MathText text={read.text} /> : <Tex latex={read.text} />}
    </p>
  );
}

function MarkRow({ index, entry, busy, mode, firstRead, onRegrade, onCorrect, onStartStreak }: RowProps) {
  const { item, grade } = entry;
  const verifiedMethod = VERIFIED_METHODS.includes(grade.method);
  // An unsure mark is never shown as verified, even when its method is a verified one.
  const verified = verifiedMethod && grade.verdict !== "unsure";
  const aiBased = AI_METHODS.includes(grade.method);
  const unsure = grade.verdict === "unsure" || grade.method === "not_graded";
  const referenceHeading =
    grade.method === "bank_key" ? "Verified answer" : verifiedMethod ? "SymPy's answer" : "AI's answer";
  // Status names: Echo verified (SymPy computed it), Bank confirmed (matched the bank's verified key),
  // AI-graded, unverified (an AI decided), Unable to verify (Echo could not reach a reliable conclusion).
  const tagText = verified
    ? grade.method === "bank_key"
      ? "Bank confirmed"
      : "Echo verified"
    : grade.method === "not_graded" || grade.verdict === "unsure"
      ? "Unable to verify"
      : "AI-graded, unverified";
  // Correct verified marks need no reading to trust, so their proof starts closed. Everything else starts open.
  const proofOpen = !(verified && grade.verdict === "correct");
  const answers = studentAnswers(entry);
  // Only AI-graded rows get the AI edge. A SymPy or unmarked row that is not verified keeps the plain edge.
  const edgeClass = verified ? "row-verified" : aiBased ? "row-ai" : "row-plain";
  // Regrade asks an AI again, so it is offered only for AI-method rows. SymPy marks are never regraded.
  const offerRegrade = aiBased;
  // A streak practises the part's topic. Not-marked parts (not_graded, or a low-confidence read) never offer one.
  const offerStreak = grade.verdict !== "correct" && grade.method !== "not_graded" && item.confidence !== "low";
  const reasonLine = grade.verdict === "unsure" && grade.reason ? reasonText(grade.reason, offerRegrade) : undefined;
  return (
    <StaggerItem index={index} className={`row ${edgeClass}`}>
      <div className="row-head">
        <span className={`verdict verdict-${grade.verdict}`}>
          <span aria-hidden="true">{VERDICT_GLYPH[grade.verdict]}</span> {VERDICT_WORDS[grade.verdict]}
        </span>
        {item.part_label && <span className="part-label">Part {item.part_label}</span>}
        <span className="source-tag">
          <span aria-hidden="true">{STATUS_GLYPH[tagText]}</span> {tagText}
        </span>
        {item.corrected_by_user && <span className="corrected-tag">Corrected by you</span>}
      </div>
      <p className="statement">
        <MathText text={item.statement_latex} />
      </p>
      {firstRead && <FirstReadLine read={firstRead} />}
      <dl className="answers">
        <div>
          <dt>Student&apos;s answer</dt>
          <dd>
            {answers.length > 0
              ? answers.map((answer, index) => (
                  <span key={index} className="answer-item">
                    <Tex latex={answer} />
                    {index < answers.length - 1 && <span aria-hidden="true">;&nbsp;</span>}
                  </span>
                ))
              : "Nothing"}
          </dd>
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
      {reasonLine && <p className="explain">{reasonLine}</p>}
      <details className="proof" open={proofOpen}>
        <summary>How this was checked</summary>
        <dl className="proof-list">
          <div>
            <dt>Reading the handwriting</dt>
            <dd>{readingLine(item)}</dd>
          </div>
          <div>
            <dt>Checked by</dt>
            <dd>{grade.label}</dd>
          </div>
          <div>
            <dt>What was compared</dt>
            <dd>
              <MathText text={grade.explanation} />
            </dd>
          </div>
          <div>
            <dt>What this does not prove</dt>
            <dd>{LIMITS[grade.method]}</dd>
          </div>
        </dl>
      </details>
      <AskBox
        // Keyed by the grade and the corrected flag, so an old reply never explains a changed mark.
        key={`${item.corrected_by_user ? "corrected" : "original"}-${grade.method}-${grade.verdict}`}
        row={askRowOf(entry)}
        mode={mode}
      />
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
        <details className="clarify-wrap">
          <summary>Fix what Echo read: type it or say it</summary>
          {/* Keyed by the corrected flag, so a box for a row that was just corrected starts empty. */}
          <ClarifyBox
            key={item.corrected_by_user ? "corrected" : "original"}
            mode={mode}
            busy={busy}
            onUse={(field, latex) => onCorrect(entry, field, latex)}
          />
        </details>
      )}
      {offerRegrade && (
        <button className="quiet" onClick={() => onRegrade(entry)} disabled={busy}>
          {busy ? "Regrading…" : "Regrade"}
        </button>
      )}
      {offerStreak && onStartStreak && (
        <button className="quiet" onClick={() => onStartStreak(entry)}>
          Start streak
        </button>
      )}
    </StaggerItem>
  );
}

// True only when there is at least one item and every item is "Not marked".
function allNotMarked(graded: GradedItem[]): boolean {
  return (
    graded.length > 0 &&
    graded.every((entry) => entry.grade.method === "not_graded" || entry.grade.reason === "reading")
  );
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
  onStartStreak,
}: Props) {
  const rows = (
    <ol className="rows">
      {graded.map((entry, index) => (
        <MarkRow
          key={entry.item.number}
          index={index}
          entry={entry}
          busy={busyNumber === entry.item.number}
          mode={mode}
          firstRead={firstReads[entry.item.number]}
          onRegrade={onRegrade}
          onCorrect={onCorrect}
          onStartStreak={onStartStreak}
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
