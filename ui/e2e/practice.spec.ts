// Fixture-mode checks for the practice workspace: check an answer, hints, full solution. Runs on built-in
// fixture data only (NEXT_PUBLIC_FIXTURES=1), so no model or network call is made.
// Fixture problems: card 0 is Echo-checked with no steps; card 2 is a bank problem with one step.
import { test, expect, type Locator, type Page } from "@playwright/test";

const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const CORRECT_FIXTURE_ANSWER = "12x^{3}+2";
const WRONG_FIXTURE_ANSWER = "5";
const ANSWER_LABEL = "Your answer";

const skillsRegion = (page: Page): Locator => page.locator('section[aria-labelledby="skills-heading"]');
const practiceRegion = (page: Page): Locator => page.locator('section[aria-labelledby="practice-heading"]');
const cardAt = (page: Page, index: number): Locator => practiceRegion(page).locator("li.row").nth(index);

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "worksheet.png", mimeType: "image/png", buffer: PNG_BYTES });
  await page.locator('form.upload button[type="submit"]').click();
  await expect(skillsRegion(page)).toBeVisible({ timeout: 15_000 });
  await skillsRegion(page).locator("li.row button").first().click();
  await expect(practiceRegion(page)).toBeVisible({ timeout: 15_000 });
});

test("the answer key is hidden until the student checks a correct answer or asks for the solution", async ({ page }) => {
  const card = cardAt(page, 0);
  await expect(card.locator(".answers")).toHaveCount(0);
  await expect(card.getByRole("button", { name: "Show solution" })).toBeVisible();
});

test("typing an answer shows the Echo reads this as preview", async ({ page }) => {
  const card = cardAt(page, 0);
  await card.getByLabel(ANSWER_LABEL).fill(WRONG_FIXTURE_ANSWER);
  await expect(card.getByText("Echo reads this as:")).toBeVisible();
});

test("a wrong answer shows Not yet with the How this was checked details, and the key stays hidden", async ({ page }) => {
  const card = cardAt(page, 0);
  await card.getByLabel(ANSWER_LABEL).fill(WRONG_FIXTURE_ANSWER);
  await card.getByRole("button", { name: "Check answer" }).click();

  const status = card.getByRole("status");
  await expect(status).toContainText("Not yet");
  await expect(status.locator("details.proof")).toContainText("How this was checked");
  await expect(status.locator("details.proof")).toContainText("Evidence");
  await expect(status.locator("details.proof")).toContainText("When");
  await expect(status.locator("details.proof")).toContainText("What this does not prove");
  await expect(card.locator(".answers")).toHaveCount(0);
});

test("a correct answer shows Correct and reveals the answer key", async ({ page }) => {
  const card = cardAt(page, 0);
  await card.getByLabel(ANSWER_LABEL).fill(CORRECT_FIXTURE_ANSWER);
  await card.getByRole("button", { name: "Check answer" }).click();

  await expect(card.getByRole("status")).toContainText("Correct");
  await expect(card.locator(".answers")).toBeVisible();
});

test("Hint reveals step 1 and the button becomes Next step, then Show solution reveals the steps and the key", async ({ page }) => {
  const card = cardAt(page, 2);
  await expect(card.locator("ol.practice-steps li")).toHaveCount(0);
  await card.getByRole("button", { name: "Hint", exact: true }).click();

  await expect(card.locator("ol.practice-steps li")).toHaveCount(1);
  await expect(card.locator("ol.practice-steps li").first()).toContainText("Bring the power down");
  await expect(card.getByRole("button", { name: "Next step", exact: true })).toBeDisabled();

  await card.getByRole("button", { name: "Show solution" }).click();
  await expect(card.locator(".answers")).toBeVisible();
  await expect(card.locator("ol.practice-steps li")).toHaveCount(1);
});

test("a card without steps shows no hint button", async ({ page }) => {
  await expect(cardAt(page, 0).getByRole("button", { name: "Hint", exact: true })).toHaveCount(0);
});
