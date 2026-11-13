"use client";

import type { GradedItem, Verdict } from "@/lib/types";
import { MathText, Tex } from "./Tex";

const VERDICT_WORDS: Record<Verdict, string> = {
  correct: "Correct",
  incorrect: "Incorrect",
  unsure: "Unsure",
};
const VERDICT_GLYPH: Record<Verdict, string> = { correct: "✓", incorrect: "✗", unsure: "?" };

interface Props {
  graded: GradedItem[];
  disclaimer: string;
  busyNumber: number | null;
  onRegrade: (item: GradedItem) => void;
}

export function WorksheetResults({ graded, disclaimer, busyNumber, onRegrade }: Props) {
  return (
    <section aria-labelledby="marks-heading">
      <h2 id="marks-heading">Marks</h2>
      <p className="disclaimer" role="note">
        {disclaimer}
      </p>
      <ol className="rows">
        {graded.map((entry) => {
          const { item, grade } = entry;
          const verified = grade.method === "bank_key";
          return (
            <li key={item.number} className={`row ${verified ? "row-verified" : "row-ai"}`}>
              <div className="row-head">
                <span className={`verdict verdict-${grade.verdict}`}>
                  <span aria-hidden="true">{VERDICT_GLYPH[grade.verdict]}</span> {VERDICT_WORDS[grade.verdict]}
                </span>
                <span className="source-tag">{verified ? "Verified mark" : "AI-graded"}</span>
              </div>
              <p className="statement">
                <MathText text={item.statement_latex} />
              </p>
              <dl className="answers">
                <div>
                  <dt>Student wrote</dt>
                  <dd>{item.student_answer_latex ? <Tex latex={item.student_answer_latex} /> : "Nothing"}</dd>
                </div>
                {grade.reference_answer_latex && (
                  <div>
                    <dt>{verified ? "Verified answer" : "AI's answer"}</dt>
                    <dd>
                      <Tex latex={grade.reference_answer_latex} />
                    </dd>
                  </div>
                )}
              </dl>
              <p className="explain">{grade.explanation}</p>
              <p className="label">{grade.label}</p>
              {entry.changed_on_regrade && (
                <p className="changed" role="status">
                  This mark changed when regraded. Treat it with extra care.
                </p>
              )}
              {!verified && (
                <button className="quiet" onClick={() => onRegrade(entry)} disabled={busyNumber === item.number}>
                  {busyNumber === item.number ? "Regrading…" : "Regrade"}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
