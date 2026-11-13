// Pure logic for the practice streak game. No React. Storage is passed in, so tests can use a fake.
import { MAX_LEVEL, MIN_LEVEL } from "./tutor-wiring";
import type { PracticeProblem } from "./types";

export const STREAK_DEFAULT_LENGTH = 5;
export const STREAK_MIN_LENGTH = 3;
export const STREAK_MAX_LENGTH = 6;
export const STREAK_LENGTH_KEY = "echo-streak-length";

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export interface StreakProblem {
  problem: PracticeProblem;
  // True when the problem's real level differs from the streak's level (a fallback from the next level up or down).
  nearby: boolean;
}

// One response's problems and the level that was requested for them.
export interface PoolSource {
  level: number;
  problems: PracticeProblem[];
}

export interface StreakState {
  level: number;
  length: number; // the streak length actually used: never more than the distinct problems available
  correct: number; // correct in a row
  position: number; // index into pool; a streak never reuses a problem
  pool: StreakProblem[];
  completedStreaks: number;
  // "exhausted": too few distinct problems are left to finish the streak.
  phase: "running" | "complete" | "ended" | "exhausted";
}

export function clampLevel(level: number): number {
  return Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, Math.round(level)));
}

// The first streak runs at the mistake's level. Each completed streak raises the next one by one, never past mistake + 1.
export function nextLevel(mistakeLevel: number, completedStreaks: number): number {
  return clampLevel(mistakeLevel + Math.min(Math.max(completedStreaks, 0), 1));
}

// The level to borrow problems from when this level has too few: one up, or one down at the top.
export function nearbyLevel(level: number): number {
  return clampLevel(level < MAX_LEVEL ? level + 1 : level - 1);
}

// Only exactly one level up or down, and only within 1 to 4.
function isNeighbour(level: number, actual: number): boolean {
  return Math.abs(actual - level) === 1 && actual >= MIN_LEVEL && actual <= MAX_LEVEL;
}

export function parseStreakLength(raw: string | null): number {
  if (raw === null) return STREAK_DEFAULT_LENGTH;
  const value = Number(raw.trim());
  if (!Number.isInteger(value) || value < STREAK_MIN_LENGTH || value > STREAK_MAX_LENGTH) return STREAK_DEFAULT_LENGTH;
  return value;
}

export function readStreakLength(storage: StorageLike | null): number {
  if (!storage) return STREAK_DEFAULT_LENGTH;
  try {
    return parseStreakLength(storage.getItem(STREAK_LENGTH_KEY));
  } catch {
    // Storage can throw when blocked; the default still applies.
    return STREAK_DEFAULT_LENGTH;
  }
}

export function writeStreakLength(storage: StorageLike | null, length: number): void {
  if (!storage) return;
  const clamped = Math.min(STREAK_MAX_LENGTH, Math.max(STREAK_MIN_LENGTH, Math.round(length)));
  try {
    storage.setItem(STREAK_LENGTH_KEY, String(clamped));
  } catch {
    // The choice still applies for this page view; it just will not persist.
  }
}

// The browser's localStorage, or null when it is missing or blocked.
export function browserStorage(): StorageLike | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

// Each problem's level is its own level when the server sends one, otherwise the level it was requested for.
// Same-level problems come first. Neighbour-level problems are added only while the pool is short, and a problem
// is never repeated (matched by statement). Levels outside the neighbours of this level are dropped.
export function buildPool(level: number, length: number, sources: PoolSource[]): StreakProblem[] {
  const tagged = sources.flatMap((source) =>
    source.problems.map((problem) => ({ problem, actual: problem.level ?? source.level })),
  );
  const seen = new Set<string>();
  const pool: StreakProblem[] = [];
  const add = (wanted: (actual: number) => boolean, nearby: boolean) => {
    for (const { problem, actual } of tagged) {
      if (!wanted(actual) || seen.has(problem.statement)) continue;
      seen.add(problem.statement);
      pool.push({ problem, nearby });
    }
  };
  add((actual) => actual === level, false);
  if (pool.length < length) add((actual) => isNeighbour(level, actual), true);
  return pool;
}

// Fill is needed when the own-level response has fewer distinct statements than the streak length.
export function needsFill(own: PracticeProblem[], length: number): boolean {
  return new Set(own.map((problem) => problem.statement)).size < length;
}

// The streak runs at most as long as the distinct problems allow, so the bar never promises more than can happen.
export function startStreak(args: {
  level: number;
  length: number;
  completedStreaks: number;
  pool: StreakProblem[];
}): StreakState {
  const length = Math.min(args.length, args.pool.length);
  return { ...args, length, correct: 0, position: 0, phase: "running" };
}

export function currentProblem(state: StreakState): StreakProblem | null {
  return state.pool[state.position] ?? null;
}

// Moves to the next distinct problem. The streak is exhausted when the problems left cannot make up the run.
function advance(state: StreakState, correct: number): StreakState {
  const position = state.position + 1;
  const remaining = state.pool.length - position;
  const phase = remaining < state.length - correct ? "exhausted" : "running";
  return { ...state, correct, position, phase };
}

export function answerCorrect(state: StreakState): StreakState {
  const correct = state.correct + 1;
  if (correct >= state.length) {
    return { ...state, correct, phase: "complete", completedStreaks: state.completedStreaks + 1 };
  }
  return advance(state, correct);
}

// A wrong answer or an unsure check: the count goes back to 0 and the level stays the same.
export function resetStreak(state: StreakState): StreakState {
  return advance(state, 0);
}

// Looking at the solution ends the streak. It does not count as correct and does not complete a streak.
export function useSolution(state: StreakState): StreakState {
  return { ...state, phase: "ended" };
}
