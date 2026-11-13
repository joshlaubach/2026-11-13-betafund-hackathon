"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { checkPracticeAnswer } from "@/lib/practice-api";
import type {
  PracticeActivity,
  PracticeAttempt,
  PracticeCheckOk,
  PracticeCommand,
  PracticeCommandKind,
  PracticeVerdict,
} from "@/lib/practice-types";
import type { Mode, PracticeProblem } from "@/lib/types";
import { Reveal, StaggerItem } from "./Motion";
import { Receipt } from "./Receipt";
import { MathText, Tex } from "./Tex";

export const PRACTICE_MAX_CHARS = 300;
const CHECK_FALLBACK = "Echo could not check this answer. Try again.";
const UNABLE_HINT = "Try writing it another way, for example 1/8 instead of one eighth.";
const NOT_PROVEN = "A numeric check at sample points, not a symbolic proof. It is only as good as the key it compares against.";
const BANK_CHECKED_BY = "SymPy, comparing with the bank's verified answer";
const KEY_CHECKED_BY = "SymPy, comparing with this problem's key";

const VERDICT_PILL: Record<PracticeVerdict, { label: string; className: string }> = {
  correct: { label: "Correct", className: "verdict-correct" },
  incorrect: { label: "Not yet", className: "verdict-incorrect" },
  unable_to_verify: { label: "Unable to verify", className: "verdict-unsure" },
};

export interface PracticeCardProps {
  problem: PracticeProblem;
  topic: string;
  mode: Mode;
  index: number;
  onAskTutor: (problem: PracticeProblem) => void;
  onActivity: (activity: PracticeActivity) => void;
  command?: PracticeCommand;
}

function formatWhen(checkedAt: string): string {
  return new Date(checkedAt).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

function CheckResult({ result, isBank }: { result: PracticeCheckOk; isBank: boolean }) {
  const pill = VERDICT_PILL[result.verdict];
  return (
    <div className="practice-verdict">
      <span className={`verdict ${pill.className}`}>{pill.label}</span>
      <p>{result.explanation}</p>
      {result.verdict === "unable_to_verify" && <p>{UNABLE_HINT}</p>}
      <details className="proof" open>
        <summary>How this was checked</summary>
        <dl className="proof-list">
          <div>
            <dt>Checked by</dt>
            <dd>{isBank ? BANK_CHECKED_BY : KEY_CHECKED_BY}</dd>
          </div>
          <div>
            <dt>Evidence</dt>
            <dd>{result.evidence}</dd>
          </div>
          <div>
            <dt>When</dt>
            <dd>
              <time dateTime={result.checked_at}>{formatWhen(result.checked_at)}</time>
            </dd>
          </div>
          <div>
            <dt>What this does not prove</dt>
            <dd>{NOT_PROVEN}</dd>
          </div>
        </dl>
      </details>
    </div>
  );
}

export function PracticeCard({ problem, topic, mode, index, onAskTutor, onActivity, command }: PracticeCardProps) {
  const inputId = useId();
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [result, setResult] = useState<PracticeCheckOk | null>(null);
  const [attempts, setAttempts] = useState<PracticeAttempt[]>([]);
  const [hintsShown, setHintsShown] = useState(0);
  const [keyOpen, setKeyOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const runCommandRef = useRef<(kind: PracticeCommandKind) => void>(() => {});
  // The nonce present at mount is treated as already handled, so a stale command never fires on mount.
  const handledNonce = useRef<number | undefined>(command?.nonce);

  const steps = problem.steps;
  const isBank = problem.origin === "bank_fallback";
  const echoChecked = !isBank;
  const trimmed = answer.trim();
  const allStepsShown = hintsShown >= steps.length;

  function report(nextAttempts: PracticeAttempt[], nextHints: number) {
    onActivity({ problem, attempts: nextAttempts, hintsShown: nextHints });
  }

  function showNextStep() {
    if (allStepsShown) return;
    const nextHints = hintsShown + 1;
    setHintsShown(nextHints);
    report(attempts, nextHints);
  }

  function showSolution() {
    const nextHints = steps.length;
    setHintsShown(nextHints);
    setKeyOpen(true);
    report(attempts, nextHints);
  }

  async function checkAnswer() {
    if (!trimmed || busy) return;
    setBusy(true);
    setCheckError(null);
    try {
      const response = await checkPracticeAnswer(topic, problem, trimmed, mode);
      if (response.status === "error") {
        setCheckError(response.error);
        return;
      }
      const nextAttempts = [...attempts, { answer_latex: trimmed, verdict: response.verdict }];
      setResult(response);
      setAttempts(nextAttempts);
      if (response.verdict === "correct") setKeyOpen(true);
      report(nextAttempts, hintsShown);
    } catch (caught) {
      setCheckError(caught instanceof ApiError ? caught.message : CHECK_FALLBACK);
    } finally {
      setBusy(false);
    }
  }

  function runCommand(kind: PracticeCommandKind) {
    if (kind === "focus_answer") inputRef.current?.focus();
    else if (kind === "show_solution") showSolution();
    else showNextStep();
  }

  // The ref is refreshed after every render, so the command effect always calls the latest handlers.
  useEffect(() => {
    runCommandRef.current = runCommand;
  });

  useEffect(() => {
    if (!command || command.nonce === handledNonce.current) return;
    handledNonce.current = command.nonce;
    runCommandRef.current(command.kind);
  }, [command]);

  const stepsLabel = isBank ? "Worked steps from Echo's verified bank" : "Worked steps";
  const hintLabel = hintsShown === 0 ? "Hint" : "Next step";

  return (
    <StaggerItem index={index} className={`row ${echoChecked ? "row-verified" : "row-ai"}`}>
      <div className="practice-card" onClick={() => report(attempts, hintsShown)}>
        <div className="row-head">
          <span className="source-tag">{echoChecked ? "Echo verified" : "Bank confirmed"}</span>
          {problem.origin === "replay_echo_checked" && <span className="source-tag">Replay of a saved run</span>}
        </div>
        <p className="statement">
          <MathText text={problem.statement} />
        </p>

        <form
          className="practice-answer"
          onSubmit={(event) => {
            event.preventDefault();
            void checkAnswer();
          }}
        >
          <label htmlFor={inputId}>Your answer</label>
          <input
            id={inputId}
            ref={inputRef}
            type="text"
            value={answer}
            maxLength={PRACTICE_MAX_CHARS}
            onChange={(event) => setAnswer(event.target.value)}
          />
          {trimmed && (
            <p className="practice-preview">
              Echo reads this as: <Tex latex={trimmed} />
            </p>
          )}
          <div className="practice-actions">
            <button type="submit" className="primary" disabled={!trimmed || busy}>
              {busy ? "Checking…" : "Check answer"}
            </button>
          </div>
        </form>

        <div className="practice-actions">
          {steps.length > 0 && (
            <button type="button" className="quiet" disabled={allStepsShown} onClick={showNextStep}>
              {hintLabel}
            </button>
          )}
          <button type="button" className="quiet" onClick={showSolution}>
            Show solution
          </button>
          <button type="button" className="quiet" onClick={() => onAskTutor(problem)}>
            Ask the tutor
          </button>
        </div>

        {checkError && (
          <p className="error" role="alert">
            {checkError}
          </p>
        )}

        <div role="status" className="practice-result">
          {result && (
            <Reveal key={result.checked_at}>
              <CheckResult result={result} isBank={isBank} />
            </Reveal>
          )}
        </div>

        {hintsShown > 0 && (
          <>
            <p className="practice-steps-label">{stepsLabel}</p>
            <ol className="practice-steps">
              {steps.slice(0, hintsShown).map((step, stepIndex) => (
                <StaggerItem key={stepIndex} index={stepIndex}>
                  <MathText text={step} />
                </StaggerItem>
              ))}
            </ol>
          </>
        )}

        {keyOpen && (
          <Reveal>
            <dl className="answers practice-key">
              <div>
                <dt>Answer key</dt>
                <dd>
                  <Tex latex={problem.answer_latex} />
                </dd>
              </div>
            </dl>
            {problem.checker && <Receipt receipt={problem.checker} />}
          </Reveal>
        )}
      </div>
    </StaggerItem>
  );
}
