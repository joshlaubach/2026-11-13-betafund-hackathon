// Mirrors the POST /api/tutor/chat contract. Keep in sync with the server by hand.

export type TutorRole = "student" | "tutor";
export type TutorMode = "live" | "replay" | "fake";
export type TutorVerdict = "correct" | "incorrect" | "unsure" | "unable_to_verify";
export type TutorEngine = "live" | "scripted";

export type TutorActionId =
  | "new_similar_problem"
  | "harder_problem"
  | "easier_problem"
  | "practice_set"
  | "show_hint"
  | "show_next_step"
  | "show_solution"
  | "check_my_answer"
  | "explain_concept"
  | "worked_example";

// One turn of history as the server reads it.
export interface TutorTurn {
  role: TutorRole;
  text: string;
}

export interface TutorAttempt {
  answer_latex: string;
  verdict: TutorVerdict;
}

export interface TutorProblem {
  problem_id: string;
  statement: string;
  origin: string;
}

export interface TutorWorksheetTally {
  correct: number;
  incorrect: number;
  unsure: number;
}

// What the tutor knows about the student's current work. Every field is optional.
export interface TutorContext {
  topic?: string;
  topic_title?: string;
  level?: number;
  problem?: TutorProblem;
  attempts?: TutorAttempt[];
  hints_shown?: number;
  worksheet?: TutorWorksheetTally;
}

export interface TutorActionParams {
  topic?: string;
  level?: number;
  count?: number;
}

export interface TutorAction {
  id: TutorActionId;
  label: string;
  params: TutorActionParams;
}

export interface TutorSource {
  topic: string;
  topic_title: string;
  problem_id: string;
  level: number;
  statement: string;
}

export interface TutorOkResponse {
  status: "ok";
  reply: string;
  sources: TutorSource[];
  actions: TutorAction[];
  grounded: boolean;
  engine: TutorEngine;
}

export type TutorResponse = TutorOkResponse | { status: "error"; error: string };

// One line in the panel's log. Tutor lines carry the full reply so provenance and sources can render.
export interface TutorMessage {
  id: number;
  role: TutorRole;
  text: string;
  response?: TutorOkResponse;
}
