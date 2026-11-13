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
  ProblemsResponse,
  WorksheetReading,
} from "@/lib/types";
import { Practice } from "@/components/Practice";
import { SkillPicture } from "@/components/SkillPicture";
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
      const title = result.recommendations.find((rec) => rec.topic === topic)?.title ?? topic;
      setPracticed({ topic, title, result: answer });
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setPracticeBusy(false);
    }
  }

  const working = stage === "reading" || stage === "grading";

  return (
    <main>
      <h1>Echo</h1>
      <p className="intro">
        Photograph a student&apos;s finished calculus worksheet. Echo reads it, marks it, shows which topics need work, and
        writes new problems. Every mark and every problem says how it was checked.
      </p>

      <form
        className="upload"
        onSubmit={(event) => {
          event.preventDefault();
          void handleMark();
        }}
      >
        <div className="field">
          <label htmlFor="worksheet">Worksheet photo</label>
          <input
            id="worksheet"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>
        {previewUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="preview" src={previewUrl} alt="The worksheet photo you selected" />
        )}
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
        <div>
          <button className="primary" type="submit" disabled={!file || working}>
            {working ? "Working…" : "Read and mark worksheet"}
          </button>
        </div>
      </form>

      {stage === "reading" && (
        <p className="progress" role="status">
          Reading the worksheet…
        </p>
      )}
      {stage === "grading" && (
        <p className="progress" role="status">
          Marking each answer…
        </p>
      )}
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
          {practiced && !practiceBusy && <Practice result={practiced.result} title={practiced.title} />}
        </>
      )}
    </main>
  );
}
