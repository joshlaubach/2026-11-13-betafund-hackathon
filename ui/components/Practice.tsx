"use client";

import type { Mode, PracticeProblem, ProblemsResponse } from "@/lib/types";
import type { PracticeActivity, PracticeCommand } from "@/lib/practice-types";
import { PracticeCard } from "./PracticeCard";
import { Swap } from "./Motion";

// Difficulty is chosen by Echo and never shown, so notes about a problem's level are left out. So are two
// backend notes that only repeat each problem's own badge (one of them names a raw topic id).
const LEVEL_NOTE = /\blevel\b|is not Echo-checked yet; showing bank problems|bank problem\(s\), labeled/i;

const noop = (): void => {};

interface PracticeProps {
  result: ProblemsResponse;
  title: string;
  mode?: Mode;
  onAskTutor?: (problem: PracticeProblem) => void;
  onActivity?: (activity: PracticeActivity) => void;
  activeIndex?: number;
  command?: PracticeCommand;
}

export function Practice({
  result,
  title,
  mode = "live",
  onAskTutor = noop,
  onActivity = noop,
  activeIndex = 0,
  command,
}: PracticeProps) {
  const checked = result.counts.echo_checked;
  return (
    <section aria-labelledby="practice-heading">
      <h2 id="practice-heading">New problems: {title}</h2>
      {result.notes.filter((note) => !LEVEL_NOTE.test(note)).map((note) => (
        <p key={note} className="note">
          {note}
        </p>
      ))}
      {result.status === "unsupported" && <p className="note">Echo has no usable verified problems for this topic yet.</p>}
      {result.status === "error" && <p className="note">Echo could not make problems: {result.notes.join(" ")}</p>}
      <Swap swapKey={`${result.topic}-${result.level}`}>
        <ol className="rows">
          {result.problems.map((problem, index) => (
            <PracticeCard
              key={`${problem.statement}-${index}`}
              problem={problem}
              topic={result.topic}
              mode={mode}
              index={index}
              onAskTutor={onAskTutor}
              onActivity={onActivity}
              command={index === activeIndex ? command : undefined}
            />
          ))}
        </ol>
      </Swap>
      {result.problems.length > 0 && (
        <p className="lede">
          {checked} of {result.problems.length} checked by Echo. The rest are verified bank problems and are labeled that
          way.
        </p>
      )}
    </section>
  );
}
