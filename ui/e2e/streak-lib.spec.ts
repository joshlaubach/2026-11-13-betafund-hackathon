// Pure checks for the streak logic (lib/streak.ts). No browser needed; storage is a fake.
import { expect, test } from "@playwright/test";
import {
  STREAK_DEFAULT_LENGTH,
  answerCorrect,
  buildPool,
  clampLevel,
  currentProblem,
  needsFill,
  nearbyLevel,
  nextLevel,
  parseStreakLength,
  readStreakLength,
  resetStreak,
  startStreak,
  useSolution,
  writeStreakLength,
  type StorageLike,
} from "../lib/streak";
import type { PracticeProblem } from "../lib/types";

const problem = (statement: string, level?: number): PracticeProblem => ({
  statement,
  answer_latex: "1",
  steps: [],
  origin: "bank_fallback",
  label: "bank-verified, not Echo-checked",
  ...(level === undefined ? {} : { level }),
});

const blockedStorage: StorageLike = {
  getItem: () => {
    throw new Error("storage blocked");
  },
  setItem: () => {
    throw new Error("storage blocked");
  },
};

function memoryStorage(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = value;
    },
  };
}

test("nextLevel starts at the mistake's level and caps at mistake + 1 and at 4", () => {
  expect(nextLevel(2, 0)).toBe(2);
  expect(nextLevel(2, 1)).toBe(3);
  expect(nextLevel(2, 5)).toBe(3);
  expect(nextLevel(4, 0)).toBe(4);
  expect(nextLevel(4, 1)).toBe(4);
});

test("clampLevel keeps levels within 1 to 4, and nearbyLevel goes up or down at the top", () => {
  expect(clampLevel(0)).toBe(1);
  expect(clampLevel(9)).toBe(4);
  expect(clampLevel(2.4)).toBe(2);
  expect(nearbyLevel(1)).toBe(2);
  expect(nearbyLevel(4)).toBe(3);
});

test("the streak length defaults to 5 when storage is missing, blocked, or invalid", () => {
  expect(readStreakLength(null)).toBe(STREAK_DEFAULT_LENGTH);
  expect(STREAK_DEFAULT_LENGTH).toBe(5);
  expect(readStreakLength(blockedStorage)).toBe(5);
  expect(readStreakLength(memoryStorage({ "echo-streak-length": "abc" }))).toBe(5);
  expect(readStreakLength(memoryStorage({ "echo-streak-length": "2" }))).toBe(5);
  expect(readStreakLength(memoryStorage({ "echo-streak-length": "11" }))).toBe(5);
  expect(readStreakLength(memoryStorage({ "echo-streak-length": "" }))).toBe(5);
  expect(readStreakLength(memoryStorage({ "echo-streak-length": "7" }))).toBe(5);
  expect(parseStreakLength("6")).toBe(6);
});

test("writing the streak length clamps it and survives blocked storage", () => {
  const storage = memoryStorage();
  writeStreakLength(storage, 42);
  expect(storage.data["echo-streak-length"]).toBe("6");
  expect(() => writeStreakLength(blockedStorage, 4)).not.toThrow();
});

test("buildPool takes each problem's real level: same-level first, neighbours only while short, others dropped", () => {
  // The request was for level 2, but the server filled it with level 1 and level 3 problems and one level 4 problem.
  const own = { level: 2, problems: [problem("a", 2), problem("b", 1), problem("x", 4)] };
  const fill = { level: 3, problems: [problem("c", 3), problem("d", 2)] };
  const short = buildPool(2, 5, [own, fill]);
  expect(short.map((entry) => [entry.problem.statement, entry.nearby])).toEqual([
    ["a", false],
    ["d", false],
    ["b", true],
    ["c", true],
  ]);
  // A problem with no level is taken as the level it was requested for.
  const untagged = buildPool(2, 5, [{ level: 2, problems: [problem("u")] }]);
  expect(untagged).toEqual([{ problem: problem("u"), nearby: false }]);
  // Neighbours are not added once the same-level problems are enough.
  const enough = buildPool(2, 2, [own, fill]);
  expect(enough.every((entry) => !entry.nearby)).toBe(true);
  expect(enough.length).toBe(2);
});

test("buildPool never repeats a statement", () => {
  const pool = buildPool(2, 5, [{ level: 2, problems: [problem("a"), problem("a")] }]);
  expect(pool.map((entry) => entry.problem.statement)).toEqual(["a"]);
});

test("a streak is shortened to the distinct problems available, and never reuses one", () => {
  const pool = buildPool(2, 5, [{ level: 2, problems: [problem("a"), problem("b"), problem("c")] }]);
  const state = startStreak({ level: 2, length: 5, completedStreaks: 0, pool });
  expect(state.length).toBe(3);
  expect(currentProblem(state)?.problem.statement).toBe("a");
  // A reset with exactly three problems cannot finish three in a row, so the streak is exhausted, not repeated.
  const afterReset = resetStreak(state);
  expect(afterReset.phase).toBe("exhausted");
});

test("a streak keeps going while the problems left can still make up the run", () => {
  const pool = buildPool(2, 2, [{ level: 2, problems: [problem("a"), problem("b"), problem("c")] }]);
  let state = startStreak({ level: 2, length: 2, completedStreaks: 0, pool });
  state = resetStreak(state);
  expect(state.phase).toBe("running");
  expect(currentProblem(state)?.problem.statement).toBe("b");
  state = answerCorrect(state);
  expect(state.phase).toBe("running");
  expect(currentProblem(state)?.problem.statement).toBe("c");
  // Only c is left and two correct are needed, so a reset now exhausts the streak.
  expect(resetStreak(state).phase).toBe("exhausted");
});

test("a correct answer counts, a wrong answer resets and keeps the level, and a solution ends without counting", () => {
  const pool = buildPool(2, 2, [{ level: 2, problems: [problem("a"), problem("b"), problem("c"), problem("d")] }]);
  let state = startStreak({ level: 2, length: 2, completedStreaks: 0, pool });
  expect(currentProblem(state)?.problem.statement).toBe("a");

  state = answerCorrect(state);
  expect(state.correct).toBe(1);
  expect(state.phase).toBe("running");

  state = resetStreak(state);
  expect(state.correct).toBe(0);
  expect(state.level).toBe(2);
  expect(state.phase).toBe("running");

  state = answerCorrect(answerCorrect(state));
  expect(state.phase).toBe("complete");
  expect(state.completedStreaks).toBe(1);

  const ended = useSolution(startStreak({ level: 1, length: 2, completedStreaks: 0, pool }));
  expect(ended.phase).toBe("ended");
  expect(ended.correct).toBe(0);
  expect(ended.completedStreaks).toBe(0);
});

test("the fill decision counts distinct statements, so a duplicate at level 4 still fills the pool to 3", () => {
  // Level-4 strategy case: ST38, ST16 and ST12 come back, but ST16 and ST12 share a statement, so only two are distinct.
  const own = { level: 4, problems: [problem("ST38", 4), problem("ST16", 4), problem("ST16", 4)] };
  expect(needsFill(own.problems, 3)).toBe(true);
  const fill = { level: 3, problems: [problem("ST05", 3)] };
  const pool = buildPool(4, 3, [own, fill]);
  expect(pool.length).toBe(3);
  expect(pool.map((entry) => entry.problem.statement)).toEqual(["ST38", "ST16", "ST05"]);
  expect(pool.map((entry) => entry.nearby)).toEqual([false, false, true]);
});

test("a topic with only two distinct problems starts a streak of 2 and says so, without repeating", () => {
  // ST16 and ST12 share a statement and ST38 is the only other distinct problem: two distinct, so length 3 cannot run.
  const own = { level: 4, problems: [problem("ST16", 4), problem("ST16", 4), problem("ST38", 4)] };
  expect(needsFill(own.problems, 3)).toBe(true);
  const pool = buildPool(4, 3, [own]);
  expect(pool.map((entry) => entry.problem.statement)).toEqual(["ST16", "ST38"]);
  const state = startStreak({ level: 4, length: 3, completedStreaks: 0, pool });
  expect(state.length).toBe(2);
  expect(state.pool.length).toBe(2);
});
