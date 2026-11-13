"use client";

import type { ProblemsResponse } from "@/lib/types";
import { MathText, Tex } from "./Tex";
import { Receipt } from "./Receipt";

export function Practice({ result, title }: { result: ProblemsResponse; title: string }) {
  const checked = result.counts.echo_checked;
  return (
    <section aria-labelledby="practice-heading">
      <h2 id="practice-heading">New problems: {title}</h2>
      {result.notes.map((note) => (
        <p key={note} className="note">
          {note}
        </p>
      ))}
      {result.status === "unsupported" && <p className="note">Echo has no usable verified problems for this topic yet.</p>}
      {result.status === "error" && <p className="note">Echo could not make problems: {result.notes.join(" ")}</p>}
      <ol className="rows">
        {result.problems.map((problem, index) => {
          const echoChecked = problem.origin !== "bank_fallback";
          return (
            <li key={`${problem.statement}-${index}`} className={`row ${echoChecked ? "row-verified" : "row-ai"}`}>
              <div className="row-head">
                <span className="source-tag">{problem.label}</span>
                {problem.origin === "replay_echo_checked" && <span className="source-tag">Replay of a saved run</span>}
              </div>
              <p className="statement">
                <MathText text={problem.statement} />
              </p>
              <dl className="answers">
                <div>
                  <dt>Answer key</dt>
                  <dd>
                    <Tex latex={problem.answer_latex} />
                  </dd>
                </div>
              </dl>
              {problem.checker && <Receipt receipt={problem.checker} />}
            </li>
          );
        })}
      </ol>
      {result.problems.length > 0 && (
        <p className="lede">
          {checked} of {result.problems.length} checked by Echo. The rest are verified bank problems and are labeled that
          way.
        </p>
      )}
    </section>
  );
}
