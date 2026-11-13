// One place that talks to the Python server. NEXT_PUBLIC_FIXTURES=1 swaps in fake data.
import { fixtureGrade, fixtureProblems, fixtureRead } from "./fixtures";
import type {
  GradedItem,
  GradeResponse,
  Mode,
  ProblemsResponse,
  ReadResponse,
  WorksheetReading,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const USE_FIXTURES = process.env.NEXT_PUBLIC_FIXTURES === "1";
const FIXTURE_DELAY_MS = 700;

export class ApiError extends Error {}

function pause<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), FIXTURE_DELAY_MS));
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError("Could not reach the Echo server. Check that it is running on port 8000.");
  }
  if (response.status === 413) throw new ApiError("That photo is larger than 5 MB. Try a smaller one.");
  if (!response.ok) throw new ApiError(`The server answered with an error (HTTP ${response.status}).`);
  return (await response.json()) as T;
}

function jsonBody(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export function readWorksheet(file: File, mode: Mode): Promise<ReadResponse> {
  if (USE_FIXTURES) return pause(fixtureRead);
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  return send<ReadResponse>("/api/worksheet/read", { method: "POST", body: form });
}

export function gradeWorksheet(reading: WorksheetReading, mode: Mode): Promise<GradeResponse> {
  if (USE_FIXTURES) return pause(fixtureGrade);
  return send<GradeResponse>("/api/worksheet/grade", jsonBody({ reading, mode }));
}

export function regradeItem(graded: GradedItem, mode: Mode): Promise<GradedItem> {
  if (USE_FIXTURES) {
    const changed = graded.grade.method !== "bank_key" && graded.item.number === 3;
    return pause({
      ...graded,
      regraded: true,
      changed_on_regrade: changed,
      grade: changed ? { ...graded.grade, verdict: "unsure", explanation: "A second independent solve disagreed with the first." } : graded.grade,
    });
  }
  return send<GradedItem>("/api/worksheet/regrade", jsonBody({ graded, mode }));
}

// Rebuilds the skill picture and recommendations from marks, so a regrade can update them.
export function profileWorksheet(graded: GradedItem[]): Promise<GradeResponse> {
  if (USE_FIXTURES) return pause({ ...fixtureGrade, graded });
  return send<GradeResponse>("/api/worksheet/profile", jsonBody({ graded }));
}

export function requestProblems(topic: string, level: number, mode: Mode): Promise<ProblemsResponse> {
  if (USE_FIXTURES) return pause({ ...fixtureProblems, topic, level });
  return send<ProblemsResponse>("/api/problems", jsonBody({ topic, level, mode }));
}
