import { expect, test } from "@playwright/test";
import { tutorBody } from "../lib/tutor-api";
import { fixtureTutorReply } from "../lib/tutor-fixtures";
import { parseTutorMarkdown } from "../lib/tutor-markdown";
import type { TutorTurn } from "../lib/tutor-types";

function longHistory(count: number): TutorTurn[] {
  return Array.from({ length: count }, (_, index) => ({
    role: index % 2 === 0 ? "student" : "tutor",
    text: `turn ${index}`,
  }));
}

test("tutorBody builds a flat body with message, history, context and mode", () => {
  // Arrange
  const context = { topic: "chain_rule", topic_title: "Chain rule", level: 2 };

  // Act
  const body = tutorBody("  Why?  ", longHistory(3), context, "fake");

  // Assert
  expect(Object.keys(body).sort()).toEqual(["context", "history", "message", "mode"]);
  expect(body.message).toBe("Why?");
  expect(body.context).toEqual(context);
  expect(body.mode).toBe("fake");
});

test("tutorBody keeps only the last 12 history turns", () => {
  const body = tutorBody("Next step?", longHistory(15), null, "live");

  expect(body.history).toHaveLength(12);
  expect(body.history[0].text).toBe("turn 3");
  expect(body.history[11].text).toBe("turn 14");
});

test("tutorBody cuts each history text to 1200 characters", () => {
  const history: TutorTurn[] = [{ role: "student", text: "x".repeat(1500) }];

  const body = tutorBody("Hi", history, null, "live");

  expect(body.history[0].text).toHaveLength(1200);
});

test("tutorBody sends null context as null and the bank mode as fake", () => {
  const body = tutorBody("Hi", [], null, "bank");

  expect(body.context).toBeNull();
  expect(body.mode).toBe("fake");
});

test("parseTutorMarkdown splits paragraphs on blank lines and joins soft-wrapped lines", () => {
  expect(parseTutorMarkdown("First line\nstill first.\n\nSecond.")).toEqual([
    { kind: "p", text: "First line still first." },
    { kind: "p", text: "Second." },
  ]);
});

test("parseTutorMarkdown turns consecutive numbered lines into one ol", () => {
  expect(parseTutorMarkdown("Intro.\n\n1. Outer function: $\\sin(u)$.\n2. Multiply by $u'=2x$.")).toEqual([
    { kind: "p", text: "Intro." },
    { kind: "ol", items: ["Outer function: $\\sin(u)$.", "Multiply by $u'=2x$."] },
  ]);
});

test("parseTutorMarkdown turns dash lines into one ul", () => {
  expect(parseTutorMarkdown("- one\n- two")).toEqual([{ kind: "ul", items: ["one", "two"] }]);
});

test("parseTutorMarkdown leaves bold markers in the text for the renderer", () => {
  expect(parseTutorMarkdown("**Hint:** look at the outer function first.")).toEqual([
    { kind: "p", text: "**Hint:** look at the outer function first." },
  ]);
});

test("parseTutorMarkdown keeps math intact", () => {
  const text = "Compute $\\int_0^1 x\\,dx$ now.";
  expect(parseTutorMarkdown(text)).toEqual([{ kind: "p", text }]);
});

test("fixtureTutorReply returns hint actions for a hint message", () => {
  const reply = fixtureTutorReply("I need a hint", null);

  expect(reply.status).toBe("ok");
  if (reply.status !== "ok") return;
  expect(reply.reply).toContain("**Hint:**");
  expect(reply.actions.map((action) => action.id)).toEqual(["show_next_step", "check_my_answer", "worked_example"]);
});

test("fixtureTutorReply returns an error for a fail message", () => {
  expect(fixtureTutorReply("please fail", null)).toEqual({
    status: "error",
    error: "The tutor is unavailable.",
  });
});

test("fixtureTutorReply default reply cites CR38 with one scripted source", () => {
  const reply = fixtureTutorReply("Show me an example", null);

  expect(reply.status).toBe("ok");
  if (reply.status !== "ok") return;
  expect(reply.engine).toBe("scripted");
  expect(reply.grounded).toBe(true);
  expect(reply.sources.map((source) => source.problem_id)).toEqual(["CR38"]);
});

test("inline 'Step 1: ... Step 2: ...' becomes one step per line, with lead and tail paragraphs kept", () => {
  const reply =
    "Here is a worked example. Step 1: differentiate, giving $dx/dt = 3$ and $dy/dt = 2t$. " +
    "Step 2: divide to get $dy/dx = 2t/3$, then evaluate. Step 3: write the line through the point. " +
    "Now try the same three steps on your problem.";
  expect(parseTutorMarkdown(reply)).toEqual([
    { kind: "p", text: "Here is a worked example." },
    {
      kind: "ol",
      items: [
        "differentiate, giving $dx/dt = 3$ and $dy/dt = 2t$.",
        "divide to get $dy/dx = 2t/3$, then evaluate.",
        "write the line through the point.",
      ],
    },
    { kind: "p", text: "Now try the same three steps on your problem." },
  ]);
});

test("a single 'Step 1' mention stays a paragraph", () => {
  expect(parseTutorMarkdown("Start with Step 1: find the derivative.")).toEqual([
    { kind: "p", text: "Start with Step 1: find the derivative." },
  ]);
});
