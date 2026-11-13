"use client";

import type { GradeResponse, SkillStatus } from "@/lib/types";

const STATUS_WORDS: Record<SkillStatus, string> = {
  solid: "Solid",
  shaky: "Shaky",
  weak: "Weak",
  not_enough_data: "Not enough data",
};
const STATUS_GLYPH: Record<SkillStatus, string> = { solid: "●", shaky: "◐", weak: "○", not_enough_data: "–" };

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

interface Props {
  result: GradeResponse;
  activeTopic: string | null;
  onPractice: (topic: string, level: number) => void;
}

export function SkillPicture({ result, activeTopic, onPractice }: Props) {
  const { summary, skills, recommendations, unplaced } = result;
  return (
    <section aria-labelledby="skills-heading">
      <h2 id="skills-heading">What to work on</h2>
      <p className="lede">
        From {plural(summary.problems_seen, "problem")}: {plural(summary.verified_marks, "verified mark")} and{" "}
        {plural(summary.ai_marks, "AI-graded mark")}. {unplaced > 0 && `${plural(unplaced, "problem")} could not be placed in a topic.`}
      </p>

      <details className="gloss">
        <summary>What do &quot;Echo verified&quot; and &quot;Bank confirmed&quot; mean?</summary>
        <p>
          <strong>Echo verified:</strong> Echo wrote the problem and a math program (SymPy) computed and confirmed the
          answer key. A topic only counts after its checker accepted every real key and rejected every deliberately
          wrong key in a test. Today that is the power rule.
        </p>
        <p>
          <strong>Bank confirmed:</strong> the problem and its worked solution come from a bank that was verified
          before Echo and then filtered by an audit script. Echo&apos;s own checker has not passed its test for this
          topic yet, so Echo does not claim to have re-derived the key. When you check an answer, SymPy still compares
          it with the bank&apos;s key.
        </p>
      </details>

      <ol className="rows">
        {recommendations.map((rec) => (
          <li key={rec.topic} className={`row ${rec.echo_checked ? "row-verified" : "row-ai"}`}>
            <div className="row-head">
              <span className={`status status-${rec.status}`}>
                <span aria-hidden="true">{STATUS_GLYPH[rec.status]}</span> {STATUS_WORDS[rec.status]}
              </span>
              <span className="source-tag">
                {rec.echo_checked ? "Echo verified problems" : "Bank confirmed problems"}
              </span>
            </div>
            <h3>{rec.title}</h3>
            <p className="explain">{rec.reason}</p>
            <button
              className={activeTopic === rec.topic ? "quiet" : "primary"}
              onClick={() => onPractice(rec.topic, rec.suggested_level)}
              aria-pressed={activeTopic === rec.topic}
            >
              Practice this topic
            </button>
          </li>
        ))}
      </ol>

      <details className="all-topics">
        <summary>All topics seen on the worksheet</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Topic</th>
              <th scope="col">Right</th>
              <th scope="col">Wrong</th>
              <th scope="col">Unsure</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {skills.map((skill) => (
              <tr key={skill.topic}>
                <td>{skill.title}</td>
                <td>{skill.correct}</td>
                <td>{skill.incorrect}</td>
                <td>{skill.unsure}</td>
                <td>{STATUS_WORDS[skill.status]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
