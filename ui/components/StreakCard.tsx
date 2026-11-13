"use client";

import { motion, useReducedMotion } from "motion/react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ApiError, requestProblems } from "@/lib/api";
import { motionTokens } from "@/lib/motion-tokens";
import { checkPracticeAnswer } from "@/lib/practice-api";
import {
  answerCorrect,
  buildPool,
  currentProblem,
  nearbyLevel,
  needsFill,
  nextLevel,
  resetStreak,
  startStreak,
  useSolution,
  type PoolSource,
  type StreakState,
} from "@/lib/streak";
import type { Mode } from "@/lib/types";
import { PRACTICE_MAX_CHARS, SourceTags } from "./PracticeCard";
import { visibleNotes } from "./Practice";
import { MathText, Tex } from "./Tex";

export interface StreakCardProps {
  topic: string;
  title: string;
  mistakeLevel: number;
  mode: Mode;
  // The streak length chosen in Settings. The current page view uses it even when storage is blocked.
  length: number;
  onBack: () => void;
}

const CHECK_FALLBACK = "Echo could not check this answer. Try again.";
const NO_PROBLEMS = "Echo has no usable problems for this topic yet.";
const WRONG_NOTE = "Not quite. The streak starts again with a new problem.";
const UNSURE_NOTE = "Echo could not check that one, so the streak starts again.";
const ENDED_HEADING = "Streak ended: you looked at the solution";
const EXHAUSTED_HEADING = "Not enough problems for this topic yet";
const motionEase = { duration: motionTokens.duration.normal, ease: motionTokens.easing.smooth };

// Own level first. Only when that is too short for the streak, the next level up or down fills the rest.
// Returns the pool and the notes from every response it used, so the card can show the same notes as practice.
async function loadPool(topic: string, level: number, length: number, mode: Mode) {
  const own = await requestProblems(topic, level, mode, length);
  const sources: PoolSource[] = [{ level, problems: own.problems }];
  let notes = own.notes;
  // Decided by distinct statements, since duplicates in the response do not count toward the streak.
  if (needsFill(own.problems, length)) {
    const fill = await requestProblems(topic, nearbyLevel(level), mode, length);
    sources.push({ level: nearbyLevel(level), problems: fill.problems });
    notes = [...notes, ...fill.notes];
  }
  return { pool: buildPool(level, length, sources), notes };
}

function StreakBar({ correct, length, reduceMotion }: { correct: number; length: number; reduceMotion: boolean }) {
  const percent = (correct / length) * 100;
  return (
    <>
      <div
        className="streak-bar"
        role="progressbar"
        aria-label="Streak progress"
        aria-valuemin={0}
        aria-valuemax={length}
        aria-valuenow={correct}
        aria-valuetext={`${correct} of ${length} correct in a row`}
      >
        <motion.span
          className="streak-bar-fill"
          initial={false}
          animate={{ width: `${percent}%` }}
          transition={reduceMotion ? { duration: 0 } : motionEase}
        />
      </div>
      <p className="streak-count">
        {correct} of {length} correct in a row
      </p>
    </>
  );
}

export function StreakCard({ topic, title, mistakeLevel, mode, length, onBack }: StreakCardProps) {
  const reduceMotion = Boolean(useReducedMotion());
  const inputId = useId();
  const [streak, setStreak] = useState<StreakState | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<string[]>([]);
  // Counts each streak that starts, so the answer field takes focus once per streak.
  const [runId, setRunId] = useState(0);
  const answerRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [stepsShown, setStepsShown] = useState(0);
  // Bumped whenever the streak changes outside a check (new streak, solution). A check that returns late is then dropped.
  const sessionRef = useRef(0);
  const headingRef = useRef<HTMLHeadingElement>(null);

  async function begin(completedStreaks: number) {
    const level = nextLevel(mistakeLevel, completedStreaks);
    sessionRef.current += 1;
    const session = sessionRef.current;
    setLoading(true);
    setError(null);
    setNotice(null);
    setAnswer("");
    setStepsShown(0);
    setBusy(false);
    setStreak(null);
    try {
      const loaded = await loadPool(topic, level, length, mode);
      // The streak was ended or restarted while this load was pending (Strict Mode runs the mount effect twice).
      if (session !== sessionRef.current) return;
      if (loaded.pool.length === 0) {
        setError(NO_PROBLEMS);
        return;
      }
      setNotes(visibleNotes(loaded.notes));
      setStreak(startStreak({ level, length, completedStreaks, pool: loaded.pool }));
      setRunId((count) => count + 1);
    } catch (caught) {
      if (session === sessionRef.current) setError(caught instanceof ApiError ? caught.message : CHECK_FALLBACK);
    } finally {
      if (session === sessionRef.current) setLoading(false);
    }
  }

  // Each card starts one streak on mount. The parent gives a new key for each new streak request.
  useEffect(() => {
    void begin(0);
  }, []);

  // A new streak puts focus in its answer field, so a restart does not drop focus to the page.
  useEffect(() => {
    if (runId > 0) answerRef.current?.focus();
  }, [runId]);

  // Completion and endings move focus to their heading, because the answer form is gone.
  const phase = streak?.phase;
  useEffect(() => {
    if (phase === "complete" || phase === "ended" || phase === "exhausted") headingRef.current?.focus();
  }, [phase]);

  const current = streak ? currentProblem(streak) : null;

  async function checkAnswer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = answer.trim();
    if (!streak || !current || streak.phase !== "running" || !text || busy) return;
    const session = sessionRef.current;
    setBusy(true);
    setError(null);
    try {
      const response = await checkPracticeAnswer(topic, current.problem, text, mode);
      // The streak was ended or restarted while this check was pending: its result no longer applies.
      if (session !== sessionRef.current) return;
      if (response.status === "error") {
        setError(response.error);
        return;
      }
      if (response.verdict === "correct") {
        setStreak(answerCorrect(streak));
        setNotice(null);
      } else {
        setStreak(resetStreak(streak));
        setNotice(response.verdict === "incorrect" ? WRONG_NOTE : UNSURE_NOTE);
      }
      setAnswer("");
      setStepsShown(0);
    } catch (caught) {
      if (session === sessionRef.current) setError(caught instanceof ApiError ? caught.message : CHECK_FALLBACK);
    } finally {
      if (session === sessionRef.current) setBusy(false);
    }
  }

  function showSolution() {
    if (!streak) return;
    sessionRef.current += 1;
    setBusy(false);
    setStreak(useSolution(streak));
    setNotice(null);
    setStepsShown(current?.problem.steps.length ?? 0);
  }

  const steps = current?.problem.steps ?? [];
  const actions = (
    <div className="streak-actions">
      <button type="button" className="primary" onClick={() => void begin(streak?.completedStreaks ?? 0)}>
        Start another streak
      </button>
      <button type="button" className="quiet" onClick={onBack}>
        Back to worksheet
      </button>
    </div>
  );

  return (
    <section className="streak" aria-label="Practice streak">
      <p className="streak-kicker">Streak: {title}</p>
      {loading && (
        <p className="progress" role="status">
          Making problems…
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {phase === "complete" && (
        <motion.div
          role="status"
          className="streak-complete"
          initial={reduceMotion ? false : { opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={reduceMotion ? { duration: 0 } : motionEase}
        >
          <h3 ref={headingRef} tabIndex={-1}>
            Streak complete
          </h3>
          <p>{title}</p>
          {actions}
        </motion.div>
      )}

      {phase === "ended" && current && (
        <div role="status" className="streak-complete">
          <h3 ref={headingRef} tabIndex={-1}>
            {ENDED_HEADING}
          </h3>
          <dl className="answers practice-key">
            <div>
              <dt>Answer key</dt>
              <dd>
                <Tex latex={current.problem.answer_latex} />
              </dd>
            </div>
          </dl>
          {actions}
        </div>
      )}

      {streak && phase === "exhausted" && (
        <>
          <StreakBar correct={streak.correct} length={streak.length} reduceMotion={reduceMotion} />
          <div role="status" className="streak-complete">
          <h3 ref={headingRef} tabIndex={-1}>
            {EXHAUSTED_HEADING}
          </h3>
          <p>Echo has too few different problems here for a streak to finish. Try another topic.</p>
          <div className="streak-actions">
            <button type="button" className="quiet" onClick={onBack}>
              Back to worksheet
            </button>
          </div>
          </div>
        </>
      )}

      {streak && phase === "running" && current && (
        <>
          <StreakBar correct={streak.correct} length={streak.length} reduceMotion={reduceMotion} />
          {streak.length < length && (
            <p className="streak-nearby">
              Only {streak.length} different problems are available for this topic, so this streak is {streak.length} long.
            </p>
          )}
          {current.nearby && <p className="streak-nearby">From a nearby level</p>}
          <div className="row-head">
            <SourceTags problem={current.problem} />
          </div>
          {notes.map((note) => (
            <p key={note} className="note">
              {note}
            </p>
          ))}
          <p className="statement">
            <MathText text={current.problem.statement} />
          </p>
          <form className="streak-answer" onSubmit={(event) => void checkAnswer(event)}>
            <label htmlFor={inputId}>Your answer</label>
            <input
              id={inputId}
              ref={answerRef}
              type="text"
              value={answer}
              maxLength={PRACTICE_MAX_CHARS}
              onChange={(event) => setAnswer(event.target.value)}
            />
            <button type="submit" className="primary" disabled={!answer.trim() || busy}>
              {busy ? "Checking…" : "Check answer"}
            </button>
          </form>
          {notice && (
            <p className="streak-note" role="status">
              {notice}
            </p>
          )}
          <div className="streak-actions">
            {steps.length > 0 && (
              <button
                type="button"
                className="quiet"
                disabled={stepsShown >= steps.length}
                onClick={() => setStepsShown(stepsShown + 1)}
              >
                {stepsShown === 0 ? "Hint" : "Next step"}
              </button>
            )}
            <button type="button" className="quiet" onClick={showSolution}>
              Show the full solution
            </button>
            <button type="button" className="quiet" onClick={onBack}>
              Back to worksheet
            </button>
          </div>
        </>
      )}

      {/* Hints and steps stay visible after the solution is shown, so nothing the student saw disappears. */}
      {(phase === "running" || phase === "ended") && current && stepsShown > 0 && (
        <ol className="practice-steps">
          {steps.slice(0, stepsShown).map((step, index) => (
            <li key={index}>
              <MathText text={step} />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
