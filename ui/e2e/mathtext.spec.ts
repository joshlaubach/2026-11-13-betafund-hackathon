import { expect, test } from "@playwright/test";
import { wrapBareLatex } from "../lib/mathtext";

test("wraps a bare LaTeX run and leaves the words plain", () => {
  expect(wrapBareLatex("Compute \\int_0^5 v(t)\\,dt and write a sentence")).toBe(
    "Compute $\\int_0^5 v(t)\\,dt$ and write a sentence",
  );
});

test("leaves text that already has dollar signs alone", () => {
  const text = "Compute $v(0)$. Write a sentence.";
  expect(wrapBareLatex(text)).toBe(text);
});

test("leaves plain text without LaTeX alone", () => {
  const text = "Find v'(t). Compute v'(0) and write a sentence.";
  expect(wrapBareLatex(text)).toBe(text);
});

test("wraps two separate runs separately", () => {
  expect(wrapBareLatex("Evaluate \\lim_{x\\to 0} f and then \\frac{1}{2} x")).toBe(
    "Evaluate $\\lim_{x\\to 0}$ f and then $\\frac{1}{2}$ x",
  );
});
