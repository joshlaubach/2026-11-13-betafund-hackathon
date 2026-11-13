// Fixture-mode checks for the clarify flow on an unsure row. Runs on built-in fixture data only
// (NEXT_PUBLIC_FIXTURES=1), so no model, network, or speech service is used.
import { test, expect, type Locator, type Page } from "@playwright/test";

// A 1x1 PNG, the same bytes as worksheet.spec.ts. Fixture mode never reads the image.
const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const READING_LINE = "Echo could not read this part clearly. Retake a clearer photo of it.";
const TEXT_LABEL = "Type or say it in words or math";
const FIXTURE_NOTE = "scripted: fixture mode understands only a few phrases";
const DERIVATIVE_TEXT = "derivative of x squared";

const marksRegion = (page: Page): Locator => page.locator('section[aria-labelledby="marks-heading"]');

// The unsure row for "Find the total distance.", which the fixture reads as "not marked".
const unsureRow = (page: Page): Locator => marksRegion(page).locator("li.row").filter({ hasText: READING_LINE });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "worksheet.png", mimeType: "image/png", buffer: PNG_BYTES });
  await page.locator('form.upload button[type="submit"]').click();
  await expect(marksRegion(page)).toBeVisible({ timeout: 15_000 });
});

test("an unsure row is clarified, confirmed, and then graded as corrected", async ({ page }) => {
  const row = unsureRow(page);
  await expect(row).toHaveCount(1);
  await row.getByLabel(TEXT_LABEL).fill(DERIVATIVE_TEXT);
  await row.getByRole("button", { name: "Ask Echo" }).click();
  await expect(row.getByText("Echo understood:")).toBeVisible();

  await row.getByRole("button", { name: "Use this" }).click();

  const corrected = marksRegion(page).locator(".row-verified").filter({ has: page.locator(".corrected-tag") });
  await expect(corrected).toHaveCount(1);
  await expect(corrected.locator(".corrected-tag")).toHaveText("Corrected by you");
  await expect(corrected.locator(".first-read")).toContainText("Echo first read:");
  await expect(corrected.locator(".first-read")).toContainText("Find the total distance.");
});

test("Cancel leaves the unsure row unchanged", async ({ page }) => {
  const row = unsureRow(page);
  await row.getByLabel(TEXT_LABEL).fill(DERIVATIVE_TEXT);
  await row.getByRole("button", { name: "Ask Echo" }).click();
  await expect(row.getByText("Echo understood:")).toBeVisible();

  await row.getByRole("button", { name: "Cancel" }).click();

  await expect(row.getByText("Echo understood:")).toHaveCount(0);
  await expect(marksRegion(page).locator(".corrected-tag")).toHaveCount(0);
  await expect(row).toHaveCount(1);
  await expect(row).toContainText(READING_LINE);
});

test("the answer choice shows Echo's note and corrects the student's answer", async ({ page }) => {
  const row = unsureRow(page);
  await row.getByRole("radio", { name: "This is my answer" }).check();
  await row.getByLabel(TEXT_LABEL).fill("two");
  await row.getByRole("button", { name: "Ask Echo" }).click();

  await expect(row.getByText(FIXTURE_NOTE)).toBeVisible();
  await row.getByRole("button", { name: "Use this" }).click();
  await expect(marksRegion(page).locator(".corrected-tag")).toHaveText("Corrected by you");
});

test("Ask Echo stays disabled until something is typed", async ({ page }) => {
  const row = unsureRow(page);
  const ask = row.getByRole("button", { name: "Ask Echo" });
  await expect(ask).toBeDisabled();

  await row.getByLabel(TEXT_LABEL).fill(DERIVATIVE_TEXT);
  await expect(ask).toBeEnabled();
});

test("the microphone button is hidden when the browser has no speech recognition", async ({ page }) => {
  const row = unsureRow(page);
  await expect(row.getByRole("button", { name: "Ask Echo" })).toBeVisible();

  const hasSpeech = await page.evaluate(() => {
    const scope = window as unknown as Record<string, unknown>;
    return Boolean(scope.SpeechRecognition || scope.webkitSpeechRecognition);
  });
  // Either state is valid: the button appears only where the browser can listen.
  await expect(row.getByRole("button", { name: "Speak" })).toHaveCount(hasSpeech ? 1 : 0);
});

test("at 375 px the open clarify box fits with no horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  const row = unsureRow(page);
  await row.getByLabel(TEXT_LABEL).fill(DERIVATIVE_TEXT);
  await row.getByRole("button", { name: "Ask Echo" }).click();
  await expect(row.getByText("Echo understood:")).toBeVisible();

  const widths = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(widths.scrollWidth).toBeLessThanOrEqual(widths.innerWidth);
});
