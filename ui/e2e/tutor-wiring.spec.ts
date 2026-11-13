// The rules that turn a tutor action into a page operation. Pure functions, no page.
import { expect, test } from "@playwright/test";
import { buildTutorContext, planAction, type PracticeState } from "../lib/tutor-wiring";
import type { TutorAction } from "../lib/tutor-types";
import type { ProblemsResponse } from "../lib/types";

const PRACTICE: PracticeState = {
  topic: "chain_rule",
  title: "Chain rule",
  result: { topic: "chain_rule", level: 4, problems: [] } as unknown as ProblemsResponse,
};
const action = (id: TutorAction["id"], params: TutorAction["params"] = {}): TutorAction => ({ id, label: id, params });

test("harder never goes above the top level, easier never below the bottom", () => {
  expect(planAction(action("harder_problem"), PRACTICE, null)).toEqual({ kind: "practice", topic: "chain_rule", level: 4 });
  const low = { ...PRACTICE, result: { ...PRACTICE.result, level: 1 } };
  expect(planAction(action("easier_problem"), low, null)).toEqual({ kind: "practice", topic: "chain_rule", level: 1 });
});

test("step actions act on the active card, and need a practice set", () => {
  expect(planAction(action("show_next_step"), PRACTICE, null)).toEqual({ kind: "command", command: "show_next_step" });
  expect(planAction(action("check_my_answer"), PRACTICE, null)).toEqual({ kind: "command", command: "focus_answer" });
  expect(planAction(action("show_hint"), null, "chain_rule").kind).toBe("none");
});

test("a practice action uses the action's topic, then the practice topic, then the fallback", () => {
  expect(planAction(action("practice_set", { topic: "power_rule", level: 2 }), PRACTICE, null)).toEqual({
    kind: "practice",
    topic: "power_rule",
    level: 2,
  });
  expect(planAction(action("new_similar_problem"), null, "limits")).toEqual({ kind: "practice", topic: "limits", level: 2 });
  expect(planAction(action("new_similar_problem"), null, null).kind).toBe("none");
});

test("the tutor context carries the active problem, its attempts, and the hints shown", () => {
  const problem = { statement: "Find $f'(x)$.", answer_latex: "2x", steps: [], origin: "bank_fallback", label: "", id: "CR1" };
  const context = buildTutorContext(
    PRACTICE,
    { problem: problem as never, attempts: [{ answer_latex: "x", verdict: "incorrect" }], hintsShown: 1 },
    null,
    null,
  );
  expect(context?.problem).toEqual({ problem_id: "CR1", statement: "Find $f'(x)$.", origin: "bank_fallback" });
  expect(context?.attempts).toHaveLength(1);
  expect(context?.hints_shown).toBe(1);
  expect(context?.level).toBe(4);
});
