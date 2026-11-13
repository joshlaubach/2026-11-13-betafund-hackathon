"use client";

import "../app/upload.css";
import { motion, useReducedMotion } from "motion/react";
import { motionTokens } from "@/lib/motion-tokens";
import { stepStates, type AnalysisStage, type StepState } from "@/lib/upload";

type Props = {
  stage: AnalysisStage;
};

const STEP_LABELS = ["Reading the handwriting", "Checking each answer"] as const;

const SUMMARIES: Record<AnalysisStage, string> = {
  reading: "Step 1 of 2: reading the handwriting.",
  grading: "Step 2 of 2: checking each answer.",
  done: "Both steps are finished.",
};

const STATE_WORDS: Record<StepState, string> = {
  waiting: "waiting",
  active: "in progress",
  done: "done",
};

const PULSE_OPACITY = [1, 0.35, 1];

function Step({ label, state }: { label: string; state: StepState }) {
  const reduce = Boolean(useReducedMotion());
  const pulsing = state === "active" && !reduce;

  return (
    <li className="analysis-step" data-state={state} aria-current={state === "active" ? "step" : undefined}>
      <motion.span
        className="step-mark"
        aria-hidden="true"
        animate={{ opacity: pulsing ? PULSE_OPACITY : 1 }}
        transition={{
          duration: motionTokens.duration.slow,
          ease: motionTokens.easing.sharp,
          repeat: pulsing ? Infinity : 0,
        }}
      />
      <span>{label}</span>
      <span className="step-state">({STATE_WORDS[state]})</span>
    </li>
  );
}

export function AnalysisProgress({ stage }: Props) {
  const states = stepStates(stage);

  return (
    <div className="analysis" role="status">
      <p className="analysis-summary">{SUMMARIES[stage]}</p>
      <ol className="analysis-steps">
        {STEP_LABELS.map((label, index) => (
          <Step key={label} label={label} state={states[index]} />
        ))}
      </ol>
    </div>
  );
}
