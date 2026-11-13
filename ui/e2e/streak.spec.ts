// Streak checks in fixture mode (NEXT_PUBLIC_FIXTURES=1, no model). Fixture answers are compared with the key
// with spaces removed: the first fixture problem's key is "12 x^{3} + 2", the second's "15 x^{2} - 1".
import { test, expect, type Locator, type Page } from "@playwright/test";

const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const panel = (page: Page): Locator => page.locator('[role="region"][aria-label="Echo tutor"]');
const marks = (page: Page): Locator => page.locator('section[aria-labelledby="marks-heading"]');
const partRow = (page: Page, label: string): Locator =>
  marks(page).locator("li.row").filter({ has: page.locator(".part-label", { hasText: new RegExp(`^Part ${label}$`) }) });
const streakButton = (row: Locator): Locator => row.getByRole("button", { name: "Start streak", exact: true });
const bar = (page: Page): Locator => panel(page).getByRole("progressbar");

async function markWorksheet(page: Page): Promise<void> {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "worksheet.png", mimeType: "image/png", buffer: PNG_BYTES });
  await page.locator('form.upload button[type="submit"]').click();
  await expect(marks(page)).toBeVisible({ timeout: 15_000 });
}

async function answer(page: Page, text: string): Promise<void> {
  const tutor = panel(page);
  await tutor.getByLabel("Your answer").fill(text);
  await tutor.getByRole("button", { name: "Check answer" }).click();
}

test("a wrong or unsure part shows Start streak; a Not marked part does not", async ({ page }) => {
  await markWorksheet(page);
  await expect(streakButton(partRow(page, "b"))).toBeVisible();
  await expect(streakButton(partRow(page, "f"))).toBeVisible();
  await expect(streakButton(partRow(page, "e"))).toHaveCount(0);
  await expect(streakButton(partRow(page, "a"))).toHaveCount(0);
});

test("a correct answer moves the progress bar from 0 to 1", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "0", { timeout: 10_000 });
  await answer(page, "12x^{3}+2");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "1", { timeout: 10_000 });
});

test("a wrong answer resets the progress bar to 0 with a friendly note", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  await answer(page, "12x^{3}+2");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "1", { timeout: 10_000 });
  await answer(page, "7");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "0", { timeout: 10_000 });
  // The fixture pool has ten problems, so the streak restarts on a new one instead of ending.
  await expect(panel(page).getByRole("heading", { name: "Not enough problems for this topic yet" })).toHaveCount(0);
  await expect(panel(page).getByText("Not quite. The streak starts again with a new problem.")).toBeVisible();
  await expect(panel(page).getByText(/SymPy|verdict|method/)).toHaveCount(0);
});

test("a wrong answer on the first problem resets the bar to 0 and shows the next problem", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "0", { timeout: 10_000 });
  const statement = panel(page).locator(".streak .statement");
  const first = await statement.textContent();
  await answer(page, "7");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "0", { timeout: 10_000 });
  await expect(panel(page).getByRole("heading", { name: "Not enough problems for this topic yet" })).toHaveCount(0);
  // The next problem replaces the first one on screen.
  await expect(statement).not.toHaveText(first ?? "");
  await expect(panel(page).getByLabel("Your answer")).toBeVisible();
  await expect(panel(page).getByText("Not quite. The streak starts again with a new problem.")).toBeVisible();
});

test("completing every answer in the streak shows Streak complete", async ({ page }) => {
  // A streak of 3 keeps the fixture's three problems enough, so every answer is a new problem.
  await page.addInitScript(() => window.localStorage.setItem("echo-streak-length", "3"));
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  const keys = ["12x^{3}+2", "15x^{2}-1", "4x^{3}-3"];
  for (const [index, key] of keys.entries()) {
    await answer(page, key);
    // The last answer completes the streak, and the bar leaves with the running view, so only check the middle ones.
    if (index < keys.length - 1) {
      await expect(bar(page)).toHaveAttribute("aria-valuenow", String(index + 1), { timeout: 10_000 });
    }
  }
  await expect(panel(page).getByRole("heading", { name: "Streak complete" })).toBeVisible();
  await expect(panel(page).getByRole("button", { name: "Start another streak" })).toBeVisible();
  await expect(panel(page).getByRole("button", { name: "Back to worksheet" })).toBeVisible();
});

test("using the full solution ends the streak and does not count as correct", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  await panel(page).getByRole("button", { name: "Show the full solution" }).click();
  await expect(panel(page).getByText("Streak ended: you looked at the solution")).toBeVisible();
  await expect(panel(page).getByRole("heading", { name: "Streak complete" })).toHaveCount(0);
  await expect(bar(page)).toHaveCount(0);
});

test("the ending after the solution is announced and takes focus", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  await panel(page).getByRole("button", { name: "Show the full solution" }).click();
  const heading = panel(page).getByRole("heading", { name: "Streak ended: you looked at the solution" });
  await expect(heading).toBeFocused();
  await expect(panel(page).getByRole("status").filter({ hasText: "Streak ended" })).toBeVisible();
});

test("a check still pending when the solution is shown cannot complete the streak", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  await answer(page, "12x^{3}+2");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "1", { timeout: 10_000 });
  await answer(page, "15x^{2}-1");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "2", { timeout: 10_000 });
  // The last answer is correct, but the solution is shown before its check (about 700 ms in fixtures) returns.
  await answer(page, "4x^{3}-3");
  await panel(page).getByRole("button", { name: "Show the full solution" }).click();
  await expect(panel(page).getByText("Streak ended: you looked at the solution")).toBeVisible();
  await page.waitForTimeout(1500);
  await expect(panel(page).getByRole("heading", { name: "Streak complete" })).toHaveCount(0);
  await expect(panel(page).getByText("Streak ended: you looked at the solution")).toBeVisible();
});

test("a length chosen in Settings applies to the next streak even when storage is blocked", async ({ page }) => {
  await page.addInitScript(() => {
    const blocked = () => {
      throw new Error("storage blocked");
    };
    Storage.prototype.getItem = blocked;
    Storage.prototype.setItem = blocked;
  });
  await markWorksheet(page);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const slider = page.getByRole("slider", { name: "Streak length" });
  await slider.focus();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await expect(slider).toHaveValue("3");
  await page.keyboard.press("Escape");
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toHaveAttribute("aria-valuemax", "3", { timeout: 10_000 });
  // The stored default of 5 would shorten this streak to the 3 problems available and show a note. The note must not appear.
  await expect(panel(page).getByText(/so this streak is/)).toHaveCount(0);
});

test("showing the full solution keeps the hints and shows the steps", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  await answer(page, "12x^{3}+2");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "1", { timeout: 10_000 });
  await answer(page, "15x^{2}-1");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "2", { timeout: 10_000 });
  // The third problem is the bank problem, which has a worked step.
  await panel(page).getByRole("button", { name: "Hint", exact: true }).click();
  await expect(panel(page).getByText("Bring the power down and lower it by one.")).toBeVisible();
  await panel(page).getByRole("button", { name: "Show the full solution" }).click();
  await expect(panel(page).getByText("Streak ended: you looked at the solution")).toBeVisible();
  await expect(panel(page).getByText("Bring the power down and lower it by one.")).toBeVisible();
});

test("completing a streak is announced and moves focus to the completion heading", async ({ page }) => {
  // A streak of 3 makes three correct answers complete it (the default 5 needs five).
  await page.addInitScript(() => window.localStorage.setItem("echo-streak-length", "3"));
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  const keys = ["12x^{3}+2", "15x^{2}-1", "4x^{3}-3"];
  for (const [index, key] of keys.entries()) {
    await answer(page, key);
    if (index < keys.length - 1) {
      await expect(bar(page)).toHaveAttribute("aria-valuenow", String(index + 1), { timeout: 10_000 });
    }
  }
  await expect(panel(page).getByRole("heading", { name: "Streak complete" })).toBeFocused();
  await expect(panel(page).getByRole("status").filter({ hasText: "Streak complete" })).toBeVisible();
});

// The solution control exists only while a streak is running, and a pending load shows no streak. So a user cannot
// click "Show the full solution" during a load. This checks the reachable path that the load guard protects.
test("after the solution ends a streak, starting another shows a fresh streak with no leftover ended heading", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  await panel(page).getByRole("button", { name: "Show the full solution" }).click();
  await expect(panel(page).getByRole("heading", { name: "Streak ended: you looked at the solution" })).toBeVisible();
  await panel(page).getByRole("button", { name: "Start another streak" }).click();
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "0", { timeout: 10_000 });
  await expect(panel(page).getByRole("heading", { name: "Streak ended: you looked at the solution" })).toHaveCount(0);
});

// The streak card shows the same source labels as the practice card, for the same problem.
test("a streak problem shows the same source label as the practice card for that problem", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).click();
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  const streakTag = (index: number) => panel(page).locator(".streak .row-head .source-tag").nth(index);
  await expect(streakTag(0)).toHaveText("Echo verified");
  // Two correct answers move the streak to the bank problem, which is labelled Bank confirmed.
  await answer(page, "12x^{3}+2");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "1", { timeout: 10_000 });
  await answer(page, "15x^{2}-1");
  await expect(bar(page)).toHaveAttribute("aria-valuenow", "2", { timeout: 10_000 });
  await expect(streakTag(0)).toHaveText("Bank confirmed");

  // The practice card for the same problems, from the skill row, uses the same labels.
  await page.locator('section[aria-labelledby="skills-heading"] li.row button').first().click();
  const practice = page.locator('section[aria-labelledby="practice-heading"]');
  await expect(practice.locator("li.row").first().locator(".source-tag").first()).toHaveText("Echo verified", { timeout: 15_000 });
  await expect(practice.locator("li.row").nth(2).locator(".source-tag").first()).toHaveText("Bank confirmed");
});

// Keyboard start: the answer field takes focus, so typing reaches it and not the tutor chat.
test("starting a streak from the keyboard focuses its answer field, so typing does not send a tutor message", async ({ page }) => {
  await markWorksheet(page);
  await streakButton(partRow(page, "b")).focus();
  await page.keyboard.press("Enter");
  await expect(bar(page)).toBeVisible({ timeout: 10_000 });
  await page.keyboard.type("12x^{3}+2");
  await expect(panel(page).getByLabel("Your answer")).toHaveValue("12x^{3}+2");
  await expect(panel(page).locator(".tutor-turn-student")).toHaveCount(0);
});
