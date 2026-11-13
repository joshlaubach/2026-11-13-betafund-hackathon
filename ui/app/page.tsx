"use client";

import { useEffect, useState } from "react";
import { ApiError, gradeWorksheet, profileWorksheet, readWorksheet, regradeItem, requestProblems } from "@/lib/api";
import { correctItem, firstReadOf } from "@/lib/correction";
import type {
  ClarifyField,
  FirstRead,
  GradedItem,
  GradeResponse,
  Mode,
  PracticeProblem,
  ProblemsResponse,
  WorksheetReading,
} from "@/lib/types";
import { Practice } from "@/components/Practice";
import { SkillPicture } from "@/components/SkillPicture";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AnalysisProgress } from "@/components/AnalysisProgress";
import { SplitWorkspace } from "@/components/SplitWorkspace";
import { UploadDropzone } from "@/components/UploadDropzone";
import { WorksheetPreview } from "@/components/WorksheetPreview";
import { TutorPanel } from "@/components/TutorPanel";
import type { PracticeActivity, PracticeCommand } from "@/lib/practice-types";
import type { TutorAction } from "@/lib/tutor-types";
import { buildTutorContext, planAction } from "@/lib/tutor-wiring";
import { WorksheetResults } from "@/components/WorksheetResults";

type Stage = "idle" | "reading" | "grading" | "done";
interface Practiced {
  topic: string;
  title: string;
  result: ProblemsResponse;
}

const READING_DISCLAIMER =
  "Echo reads handwriting with AI and can misread it, especially unclear writing. If a problem or answer is read wrongly, its mark will be wrong too. Compare each problem below with the worksheet.";

const MODES: { value: Mode; label: string }[] = [
  { value: "live", label: "Live AI (needs internet)" },
  { value: "replay", label: "Saved replay (works offline)" },
  { value: "fake", label: "Scripted demo data" },
];

// The three kinds of mark, in the same colors the rows use, so a first-time visitor can read a result.
const MARK_KINDS: { className: string; title: string; text: string }[] = [
  {
    className: "kind-verified",
    title: "Echo verified",
    text: "A math program (SymPy) computed the answer itself and compared it with the student's.",
  },
  {
    className: "kind-verified",
    title: "Bank confirmed",
    text: "The answer matched the key of a problem from Echo's verified bank.",
  },
  {
    className: "kind-ai",
    title: "AI-graded, unverified",
    text: "AI solved it independently. Useful, but no program checked it, so it can be wrong.",
  },
  {
    className: "kind-plain",
    title: "Unable to verify",
    text: "Echo could not read or compare this part. It says why and how to fix it.",
  },
];

function HowItWorks() {
  return (
    <section className="guide" aria-labelledby="guide-heading">
      <h2 id="guide-heading">How Echo marks a worksheet</h2>
      <ol className="guide-steps">
        <li>Upload a photo of a finished worksheet.</li>
        <li>Echo reads each problem and the student&apos;s answer, and shows what it read.</li>
        <li>Each part gets a mark that says exactly how it was checked.</li>
      </ol>
      <ul className="kinds">
        {MARK_KINDS.map((kind) => (
          <li key={kind.title} className={`kind ${kind.className}`}>
            <strong>{kind.title}</strong>
            <span>{kind.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="skeleton" aria-hidden="true">
      <span className="bar bar-wide" />
      <span className="bar" />
      <span className="bar bar-short" />
    </div>
  );
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Try again.";
}

export default function Home() {
  const [mode, setMode] = useState<Mode>("live");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [sourceLine, setSourceLine] = useState<string>("");
  const [setup, setSetup] = useState<string>("");
  const [readingNotes, setReadingNotes] = useState<string>("");
  const [result, setResult] = useState<GradeResponse | null>(null);
  const [busyNumber, setBusyNumber] = useState<number | null>(null);
  const [practiced, setPracticed] = useState<Practiced | null>(null);
  const [practiceBusy, setPracticeBusy] = useState(false);
  const [tutorOpen, setTutorOpen] = useState(false);
  // On phones and tablets one view shows at a time; on desktop both sit side by side.
  const [mobileView, setMobileView] = useState<"worksheet" | "tutor">("worksheet");
  const [tutorPrompt, setTutorPrompt] = useState<{ text: string; nonce: number } | undefined>(undefined);
  // The practice problem the student is working on, with their attempts and hints so far.
  const [activity, setActivity] = useState<PracticeActivity | null>(null);
  const [command, setCommand] = useState<PracticeCommand | undefined>(undefined);
  // What Echo first read for each corrected row, keyed by part number. Kept so it is never overwritten.
  const [firstReads, setFirstReads] = useState<Record<number, FirstRead>>({});

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function handleMark() {
    if (!file) return;
    setError(null);
    setResult(null);
    setPracticed(null);
    setFirstReads({});
    setStage("reading");
    try {
      const read = await readWorksheet(file, mode);
      if (read.status !== "ok" || !read.reading) {
        throw new ApiError(read.error ?? "Echo could not read that photo. Try a clearer one.");
      }
      setSourceLine(read.label.replace(/^source:\s*/i, ""));
      setSetup(read.reading.shared_context);
      setReadingNotes(read.reading.notes);
      setStage("grading");
      setResult(await gradeWorksheet(read.reading, mode));
      setStage("done");
    } catch (caught) {
      setError(errorText(caught));
      setStage("idle");
    }
  }

  async function handleRegrade(entry: GradedItem) {
    if (!result) return;
    setError(null);
    setBusyNumber(entry.item.number);
    try {
      const updated = await regradeItem(entry, mode);
      const graded = result.graded.map((current) => (current.item.number === updated.item.number ? updated : current));
      const profile = await profileWorksheet(graded);
      setResult({ ...profile, graded });
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusyNumber(null);
    }
  }

  // The student confirmed a clarified reading: grade only this part, then merge it and recompute the profile.
  async function handleCorrect(entry: GradedItem, field: ClarifyField, latex: string) {
    if (!result) return;
    const number = entry.item.number;
    const corrected = correctItem(entry.item, field, latex);
    const reading: WorksheetReading = { items: [corrected], notes: "", shared_context: setup };
    setError(null);
    setBusyNumber(number);
    try {
      const response = await gradeWorksheet(reading, mode);
      const fresh = response.graded.find((current) => current.item.number === number) ?? response.graded[0];
      if (!fresh) throw new ApiError("Echo could not mark the corrected part. Try again.");
      const graded = result.graded.map((current) => (current.item.number === number ? fresh : current));
      const profile = await profileWorksheet(graded);
      setFirstReads((previous) =>
        previous[number] ? previous : { ...previous, [number]: firstReadOf(entry.item, field) },
      );
      setResult({ ...profile, graded });
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusyNumber(null);
    }
  }

  async function handlePractice(topic: string, level: number) {
    if (!result) return;
    setError(null);
    setPracticeBusy(true);
    try {
      const answer = await requestProblems(topic, level, mode);
      const title =
        result.recommendations.find((rec) => rec.topic === topic)?.title ??
        (practiced?.topic === topic ? practiced.title : topic);
      setActivity(null);
      setPracticed({ topic, title, result: answer });
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setPracticeBusy(false);
    }
  }

  function openTutor() {
    setTutorOpen(true);
    setMobileView("tutor");
  }

  function closeTutor() {
    setTutorOpen(false);
    setMobileView("worksheet");
  }

  // The student asked the tutor about one problem: that problem becomes active and the tutor opens with a prompt.
  function handleAskTutor(problem: PracticeProblem) {
    setActivity((previous) =>
      previous?.problem === problem ? previous : { problem, attempts: [], hintsShown: 0 },
    );
    openTutor();
    setTutorPrompt({ text: "Help me get started on this problem.", nonce: Date.now() });
  }

  // A suggested action from the tutor. Each id maps to one validated page operation (see lib/tutor-wiring.ts).
  function handleTutorAction(action: TutorAction) {
    const plan = planAction(action, practiced, fallbackTopic?.topic ?? null);
    if (plan.kind === "none") {
      setError(plan.reason);
      return;
    }
    // On a phone the result is in the worksheet view, so switch to it. On desktop the tutor stays docked.
    if (window.matchMedia("(max-width: 61.99rem)").matches) setMobileView("worksheet");
    if (plan.kind === "practice") {
      void handlePractice(plan.topic, plan.level);
    } else {
      setCommand({ kind: plan.command, nonce: Date.now() });
    }
    document.getElementById("practice-heading")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const working = stage === "reading" || stage === "grading";
  const fallbackTopic = result?.recommendations[0]
    ? { topic: result.recommendations[0].topic, title: result.recommendations[0].title }
    : null;
  const tutorContext = buildTutorContext(practiced, activity, result, fallbackTopic);
  const activeIndex = practiced && activity ? Math.max(0, practiced.result.problems.indexOf(activity.problem)) : 0;
  const tutorLabel = tutorContext?.topic_title
    ? `About: ${tutorContext.topic_title}${activity ? `, problem ${activeIndex + 1}` : ""}`
    : "Ask about any calculus topic.";

  return (
    <>
      <header className="masthead">
        <div className="masthead-inner">
          <h1 className="wordmark">Echo</h1>
          <p className="tagline">Every mark says how it was checked.</p>
          <div className="masthead-tools">
            <button
              type="button"
              className="quiet tutor-launch"
              aria-expanded={tutorOpen}
              onClick={() => (tutorOpen ? closeTutor() : openTutor())}
            >
              Ask the tutor
            </button>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <SplitWorkspace
        tutorOpen={tutorOpen}
        onTutorOpenChange={(open) => (open ? openTutor() : closeTutor())}
        mobileView={mobileView}
        onMobileViewChange={setMobileView}
        workspace={
      <div className="workspace-pane">
      <main className="workspace">
        <section className="intake" aria-label="Upload a worksheet">
          <p className="intro">
            Photograph a student&apos;s finished calculus worksheet. Echo reads it, marks it, shows which topics need work,
            and writes new problems.
          </p>
          <form
            className="upload"
            onSubmit={(event) => {
              event.preventDefault();
              void handleMark();
            }}
          >
            <UploadDropzone file={file} onFile={setFile} disabled={working} />
            {/* The primary action sits right under the dropzone, above the preview, so it is visible without scrolling. */}
            <div>
              <button className="primary analyze" type="submit" disabled={!file || working}>
                {working ? "Analyzing…" : "Analyze worksheet"}
              </button>
            </div>
            {/* The data source stays visible in the summary; changing it is an advanced option. */}
            <details className="advanced">
              <summary>Marks come from: {MODES.find((option) => option.value === mode)?.label}</summary>
              <div className="field">
                <label htmlFor="mode">Where marks come from</label>
                <select id="mode" value={mode} onChange={(event) => setMode(event.target.value as Mode)}>
                  {MODES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </details>
            {previewUrl && <WorksheetPreview src={previewUrl} alt="The worksheet photo you selected" />}
          </form>
        </section>

        <div className="results">
          {!result && stage === "idle" && !error && <HowItWorks />}
          {working && <AnalysisProgress stage={stage === "reading" ? "reading" : "grading"} />}
          {working && <Skeleton />}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          {result && (
            <>
              {sourceLine && <p className="mode-note">Reading source: {sourceLine}</p>}
          <p className="disclaimer" role="note">
            {READING_DISCLAIMER}
          </p>
          <WorksheetResults
            graded={result.graded}
            setup={setup}
            notes={readingNotes}
            disclaimer={result.disclaimer}
            busyNumber={busyNumber}
            mode={mode}
            firstReads={firstReads}
            onRegrade={(entry) => void handleRegrade(entry)}
            onCorrect={(entry, field, latex) => void handleCorrect(entry, field, latex)}
          />
          <SkillPicture
            result={result}
            activeTopic={practiced?.topic ?? null}
            onPractice={(topic, level) => void handlePractice(topic, level)}
          />
          {practiceBusy && (
            <p className="progress" role="status">
              Making problems…
            </p>
          )}
          {practiced && !practiceBusy && (
            <Practice
              result={practiced.result}
              title={practiced.title}
              mode={mode}
              onAskTutor={handleAskTutor}
              onActivity={setActivity}
              activeIndex={activeIndex}
              command={command}
            />
          )}
            </>
          )}
        </div>
      </main>
      </div>
        }
        tutor={
      <TutorPanel
        layout="docked"
        open={tutorOpen}
        onClose={closeTutor}
        onRequestOpen={openTutor}
        mode={mode}
        context={tutorContext}
        onAction={handleTutorAction}
        prompt={tutorPrompt}
        contextLabel={tutorLabel}
      />
        }
      />
    </>
  );
}
