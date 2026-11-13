import { expect, test } from "@playwright/test";
import { splitMath, wrapBareLatex } from "../lib/mathtext";

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

test("splitMath reads \\(...\\) as inline math", () => {
  expect(splitMath("Let \\(f(x)=x^2\\) be given.")).toEqual([
    { kind: "text", value: "Let " },
    { kind: "inline", value: "f(x)=x^2" },
    { kind: "text", value: " be given." },
  ]);
});

test("splitMath reads \\[...\\] as display math", () => {
  expect(splitMath("Then \\[\\int_0^1 x\\,dx\\] holds.")).toEqual([
    { kind: "text", value: "Then " },
    { kind: "display", value: "\\int_0^1 x\\,dx" },
    { kind: "text", value: " holds." },
  ]);
});

test("splitMath still reads $ and $$", () => {
  expect(splitMath("A $x$ and $$y$$ end")).toEqual([
    { kind: "text", value: "A " },
    { kind: "inline", value: "x" },
    { kind: "text", value: " and " },
    { kind: "display", value: "y" },
    { kind: "text", value: " end" },
  ]);
});

test("splitMath handles all four delimiters in one string", () => {
  expect(splitMath("$a$ \\(b\\) $$c$$ \\[d\\]").map((segment) => segment.kind)).toEqual([
    "inline",
    "text",
    "inline",
    "text",
    "display",
    "text",
    "display",
  ]);
});

test("splitMath leaves unbalanced delimiters as plain text", () => {
  expect(splitMath("open \\( never closed")).toEqual([{ kind: "text", value: "open \\( never closed" }]);
  expect(splitMath("open \\[ never closed")).toEqual([{ kind: "text", value: "open \\[ never closed" }]);
  expect(splitMath("price $5 only")).toEqual([{ kind: "text", value: "price $5 only" }]);
});

test("splitMath returns plain text unchanged when there is no math", () => {
  expect(splitMath("Find v'(t).")).toEqual([{ kind: "text", value: "Find v'(t)." }]);
});

test("wrapBareLatex leaves \\( and \\[ delimited text alone", () => {
  const inline = "Compute \\(\\int_0^5 v(t)\\,dt\\) now";
  const display = "Compute \\[\\int_0^5 v(t)\\,dt\\] now";
  expect(wrapBareLatex(inline)).toBe(inline);
  expect(wrapBareLatex(display)).toBe(display);
});

test("snake_case names stay plain words, real subscripts still render", () => {
  expect(wrapBareLatex("The method was not bank_key or sympy_computed, so this is not verified.")).toBe(
    "The method was not bank_key or sympy_computed, so this is not verified.",
  );
  expect(wrapBareLatex("Let x_1 and a_n be terms")).toBe("Let $x_1$ and $a_n$ be terms");
});
