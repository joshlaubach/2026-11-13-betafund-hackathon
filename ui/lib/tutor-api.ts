// Talks to POST /api/tutor/chat. NEXT_PUBLIC_FIXTURES=1 swaps in fixture replies.
import { ApiError } from "./api";
import { fixtureTutorReply } from "./tutor-fixtures";
import type { Mode } from "./types";
import type {
  TutorContext,
  TutorMode,
  TutorResponse,
  TutorTurn,
} from "./tutor-types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const USE_FIXTURES = process.env.NEXT_PUBLIC_FIXTURES === "1";
const FIXTURE_DELAY_MS = 700;
const CHAT_PATH = "/api/tutor/chat";

export const TUTOR_HISTORY_TURNS = 12;
export const TUTOR_TEXT_MAX = 1200;
const ATTEMPTS_MAX = 5;

export interface TutorRequestBody {
  message: string;
  history: TutorTurn[];
  context: TutorContext | null;
  mode: TutorMode;
}

// The server accepts only live, replay and fake. The bank-only mode is served as the offline fake.
function toTutorMode(mode: Mode): TutorMode {
  return mode === "bank" ? "fake" : mode;
}

function trimContext(context: TutorContext): TutorContext {
  if (!context.attempts) return context;
  return { ...context, attempts: context.attempts.slice(-ATTEMPTS_MAX) };
}

// The flat body the server reads: message, history, context, mode. Nothing nested.
export function tutorBody(
  message: string,
  history: TutorTurn[],
  context: TutorContext | null,
  mode: Mode,
): TutorRequestBody {
  return {
    message: message.trim(),
    history: history.slice(-TUTOR_HISTORY_TURNS).map((turn) => ({
      role: turn.role,
      text: turn.text.slice(0, TUTOR_TEXT_MAX),
    })),
    context: context === null ? null : trimContext(context),
    mode: toTutorMode(mode),
  };
}

function pause<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), FIXTURE_DELAY_MS));
}

async function postTutor(body: TutorRequestBody): Promise<TutorResponse> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${CHAT_PATH}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Could not reach the Echo server. Check that it is running on port 8000.");
  }
  if (!response.ok) throw new ApiError(`The server answered with an error (HTTP ${response.status}).`);
  const data = (await response.json()) as TutorResponse;
  if (data.status !== "ok" && data.status !== "error") throw new ApiError("The tutor sent an unexpected reply.");
  return data;
}

export function sendTutorMessage(
  message: string,
  history: TutorTurn[],
  context: TutorContext | null,
  mode: Mode,
): Promise<TutorResponse> {
  if (USE_FIXTURES) return pause(fixtureTutorReply(message, context));
  return postTutor(tutorBody(message, history, context, mode));
}
