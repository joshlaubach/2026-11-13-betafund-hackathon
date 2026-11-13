// Fixture-mode checks for Ask Echo, the read-only panel under each marked row. Runs on built-in
// fixture data only (NEXT_PUBLIC_FIXTURES=1), so no model or network call is made.
import { test, expect, type Locator, type Page } from "@playwright/test";

// A 1x1 PNG, the same bytes as clarify.spec.ts. Fixture mode never reads the image.
const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const READING_LINE = "Echo could not read this part clearly. Retake a clearer photo of it.";
const TOGGLE_NAME = "Ask Echo about this part";
const REPLY_LABEL = "Echo's explanation (AI, not a mark)";
const CHIP = "Why is this marked this way?";
const TYPED_QUESTION = "Why is my answer 3 wrong?";

const marksRegion = (page: Page): Locator => page.locator('section[aria-labelledby="marks-heading"]');

// The unsure row for "Find the total distance.", which the fixture reads as "not marked".
const unsureRow = (page: Page): Locator => marksRegion(page).locator("li.row").filter({ hasText: READING_LINE });

// The first fixture row is a SymPy-verified correct mark.
const verifiedRow = (page: Page): Locator => marksRegion(page).locator("li.row.row-verified").first();

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "worksheet.png", mimeType: "image/png", buffer: PNG_BYTES });
  await page.locator('form.upload button[type="submit"]').click();
  await expect(marksRegion(page)).toBeVisible({ timeout: 15_000 });
});

test("the Ask Echo panel is collapsed by default", async ({ page }) => {
  const row = unsureRow(page);
  await expect(row.getByRole("button", { name: TOGGLE_NAME })).toBeVisible();
  await expect(row.getByLabel("Your question")).toHaveCount(0);
  await expect(row.getByRole("button", { name: CHIP })).toHaveCount(0);
});

test("opening the panel shows the suggested questions and the input", async ({ page }) => {
  const row = unsureRow(page);
  await row.getByRole("button", { name: TOGGLE_NAME }).click();

  await expect(row.getByRole("button", { name: "What did I do wrong?" })).toBeVisible();
  await expect(row.getByRole("button", { name: "How was this checked?" })).toBeVisible();
  await expect(row.getByRole("button", { name: CHIP })).toBeVisible();
  await expect(row.getByLabel("Your question")).toBeVisible();
  await expect(row.getByLabel("Your question")).toHaveAttribute("maxlength", "300");
});

test("clicking a suggested question shows the reply under the AI label", async ({ page }) => {
  const row = unsureRow(page);
  await row.getByRole("button", { name: TOGGLE_NAME }).click();
  await row.getByRole("button", { name: CHIP }).click();

  await expect(row.getByText(REPLY_LABEL)).toBeVisible();
  await expect(row.locator(".ask-reply")).toContainText(CHIP);
});

test("typing a question and clicking Ask shows the reply", async ({ page }) => {
  const row = unsureRow(page);
  await row.getByRole("button", { name: TOGGLE_NAME }).click();
  await row.getByLabel("Your question").fill(TYPED_QUESTION);
  await row.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(row.getByText(REPLY_LABEL)).toBeVisible();
  await expect(row.locator(".ask-reply")).toContainText(TYPED_QUESTION);
});

test("Ask stays disabled for an empty or blank question", async ({ page }) => {
  const row = unsureRow(page);
  await row.getByRole("button", { name: TOGGLE_NAME }).click();
  const ask = row.getByRole("button", { name: "Ask", exact: true });
  await expect(ask).toBeDisabled();

  await row.getByLabel("Your question").fill("   ");
  await expect(ask).toBeDisabled();

  await row.getByLabel("Your question").fill(TYPED_QUESTION);
  await expect(ask).toBeEnabled();
});

test("the panel is also present on a verified row", async ({ page }) => {
  const row = verifiedRow(page);
  await expect(row.getByRole("button", { name: TOGGLE_NAME })).toBeVisible();

  await row.getByRole("button", { name: TOGGLE_NAME }).click();
  await row.getByRole("button", { name: CHIP }).click();
  await expect(row.getByText(REPLY_LABEL)).toBeVisible();
});
