// The Ask Echo request body must match what server/worksheet_api.py AskRequest reads:
// the row's fields at the top level, next to question and mode. A nested "row" is silently ignored
// by the server, which then explains an empty row. Fixture-mode page tests cannot see that.
import { expect, test } from "@playwright/test";
import { askBody } from "../lib/api";
import type { AskRow } from "../lib/types";

const ROW: AskRow = {
  statement_latex: "Compute v(0).",
  student_answer_latex: "0",
  reference_answer_latex: "0",
  method: "sympy_computed",
  verdict: "correct",
  reason: "",
  explanation: "The answers match.",
  label: "Marked by Echo's checker",
};
const SERVER_FIELDS = [
  "question",
  "mode",
  "statement_latex",
  "student_answer_latex",
  "reference_answer_latex",
  "method",
  "verdict",
  "reason",
  "explanation",
  "label",
];

test("the ask request body has every field the server reads at the top level", () => {
  const body = askBody("Why?", ROW, "replay");
  for (const field of SERVER_FIELDS) expect(body).toHaveProperty(field);
  expect(body).not.toHaveProperty("row");
  expect(body.explanation).toBe("The answers match.");
  expect(body.question).toBe("Why?");
  expect(body.mode).toBe("replay");
});
