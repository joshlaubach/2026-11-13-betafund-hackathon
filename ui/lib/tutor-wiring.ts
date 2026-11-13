// How the page connects the tutor to what the student is doing. Pure functions, so they are testable.
import type { PracticeActivity, PracticeCommandKind } from "./practice-types";
import type { TutorAction, TutorContext } from "./tutor-types";
import type { GradeResponse, ProblemsResponse } from "./types";

export const MIN_LEVEL = 1;
export const MAX_LEVEL = 4;

export interface PracticeState {
  topic: string;
  title: string;
  result: ProblemsResponse;
}

// What the page should do for one tutor action. "practice" asks for a new set; "command" acts on the active card.
export type ActionPlan =
  | { kind: "practice"; topic: string; level: number }
  | { kind: "command"; command: PracticeCommandKind }
  | { kind: "none"; reason: string };

const COMMANDS: Partial<Record<TutorAction["id"], PracticeCommandKind>> = {
  show_hint: "show_hint",
  show_next_step: "show_next_step",
  show_solution: "show_solution",
  check_my_answer: "focus_answer",
};

function clampLevel(level: number): number {
  return Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, Math.round(level)));
}

// The worksheet's tally for one topic, when the worksheet had that topic.
function worksheetTally(result: GradeResponse | null, topic: string | undefined): TutorContext["worksheet"] {
  if (!result || !topic) return undefined;
  const skill = result.skills.find((entry) => entry.topic === topic);
  if (!skill) return undefined;
  return { correct: skill.correct, incorrect: skill.incorrect, unsure: skill.unsure };
}

export function buildTutorContext(
  practice: PracticeState | null,
  activity: PracticeActivity | null,
  result: GradeResponse | null,
  fallbackTopic: { topic: string; title: string } | null,
): TutorContext | null {
  const topic = practice?.topic ?? fallbackTopic?.topic;
  const title = practice?.title ?? fallbackTopic?.title;
  if (!topic) return null;
  const context: TutorContext = { topic, topic_title: title, worksheet: worksheetTally(result, topic) };
  if (practice) context.level = clampLevel(practice.result.level);
  if (activity) {
    context.problem = {
      problem_id: activity.problem.id ?? "",
      statement: activity.problem.statement,
      origin: activity.problem.origin,
    };
    context.attempts = activity.attempts.slice(-5);
    context.hints_shown = activity.hintsShown;
  }
  return context;
}

// Turns a validated tutor action into what the page does. The level is never shown to the student.
export function planAction(action: TutorAction, practice: PracticeState | null, fallbackTopic: string | null): ActionPlan {
  const command = COMMANDS[action.id];
  if (command) {
    return practice ? { kind: "command", command } : { kind: "none", reason: "Start a practice set first." };
  }
  const topic = action.params.topic ?? practice?.topic ?? fallbackTopic;
  if (!topic) return { kind: "none", reason: "Mark a worksheet or pick a topic first." };
  const current = practice ? practice.result.level : 2;
  switch (action.id) {
    case "harder_problem":
      return { kind: "practice", topic, level: clampLevel(action.params.level ?? current + 1) };
    case "easier_problem":
      return { kind: "practice", topic, level: clampLevel(action.params.level ?? current - 1) };
    case "new_similar_problem":
    case "practice_set":
      return { kind: "practice", topic, level: clampLevel(action.params.level ?? current) };
    default:
      return { kind: "none", reason: "That action is handled in the chat." };
  }
}
