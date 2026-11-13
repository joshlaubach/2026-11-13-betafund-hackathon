// End-to-end checks for the Echo worksheet page. Runs on built-in fixture data only (NEXT_PUBLIC_FIXTURES=1),
// so no model or network call is made. Selectors target structure (sections, row classes, roles), not label wording.
import { test, expect, type Locator, type Page } from "@playwright/test";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

// A 1x1 PNG, generated from its bytes at run time. No binary fixture is committed.
const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const SCREENSHOT_DIR = path.resolve(__dirname, "..", "test-results");

let tempDir = "";
let pngPath = "";

test.beforeAll(() => {
  tempDir = mkdtempSync(path.join(os.tmpdir(), "echo-e2e-"));
  pngPath = path.join(tempDir, "worksheet.png");
  writeFileSync(pngPath, PNG_BYTES);
});

test.afterAll(() => {
  rmSync(tempDir, { recursive: true, force: true });
});

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

const marksRegion = (page: Page): Locator => page.locator('section[aria-labelledby="marks-heading"]');
const skillsRegion = (page: Page): Locator => page.locator('section[aria-labelledby="skills-heading"]');
const practiceRegion = (page: Page): Locator => page.locator('section[aria-labelledby="practice-heading"]');
const submitButton = (page: Page): Locator => page.locator('form.upload button[type="submit"]');

async function markWorksheet(page: Page): Promise<void> {
  await page.locator('input[type="file"]').setInputFiles(pngPath);
  await submitButton(page).click();
  await expect(marksRegion(page)).toBeVisible({ timeout: 15_000 });
}

// Opens the practice set for the first recommendation, then opens the first checker receipt.
async function openFirstReceipt(page: Page): Promise<Locator> {
  await skillsRegion(page).locator("li.row button").first().click();
  const practice = practiceRegion(page);
  await expect(practice).toBeVisible({ timeout: 15_000 });
  const receipt = practice.locator("details.receipt").first();
  await receipt.locator("summary").click();
  await expect(receipt.locator("table")).toBeVisible();
  return receipt;
}

test("happy path: marks show verified and AI rows, AI rows can be regraded", async ({ page }) => {
  await markWorksheet(page);
  const marks = marksRegion(page);

  await expect(marks.locator(".row-verified").first()).toBeVisible();
  await expect(marks.locator(".row-ai").first()).toBeVisible();

  const aiRows = marks.locator(".row-ai");
  const aiCount = await aiRows.count();
  expect(aiCount).toBeGreaterThan(0);
  for (let index = 0; index < aiCount; index += 1) {
    // Unsure AI rows also carry the clarify controls, so only the Regrade button is counted here.
    await expect(aiRows.nth(index).getByRole("button", { name: "Regrade" })).toHaveCount(1);
  }
  await expect(marks.locator(".row-verified button")).toHaveCount(0);

  await expect(marks.getByRole("note")).toBeVisible();
});

test("every mark and every practice problem has a visible source tag", async ({ page }) => {
  await markWorksheet(page);
  const marks = marksRegion(page);
  const markRowCount = await marks.locator("li.row").count();
  expect(markRowCount).toBeGreaterThan(0);
  await expect(marks.locator(".source-tag")).toHaveCount(markRowCount);
  await expect(marks.locator(".source-tag").first()).toBeVisible();

  await openFirstReceipt(page);
  const practice = practiceRegion(page);
  const problemRowCount = await practice.locator("li.row").count();
  expect(problemRowCount).toBeGreaterThan(0);
  await expect(practice.locator(".source-tag")).toHaveCount(problemRowCount);
  await expect(practice.locator(".source-tag").first()).toBeVisible();
});

test("skill picture lists recommendations and opens practice with a checker receipt", async ({ page }) => {
  await markWorksheet(page);
  const skills = skillsRegion(page);
  const recommendations = skills.locator("li.row");
  const recommendationCount = await recommendations.count();
  expect(recommendationCount).toBeGreaterThan(0);
  for (let index = 0; index < recommendationCount; index += 1) {
    const button = recommendations.nth(index).locator("button");
    await expect(button).toHaveCount(1);
    await expect(button).toHaveText(/\d/);
  }

  const receipt = await openFirstReceipt(page);
  const practice = practiceRegion(page);
  await expect(practice.locator("li.row").first()).toBeVisible();
  const dataRowCount = await receipt.locator("tbody tr").count();
  expect(dataRowCount).toBeGreaterThanOrEqual(3);
});

test("regrade shows a busy state, then returns without an error", async ({ page }) => {
  await markWorksheet(page);
  // Anchored on the first AI row, so the button stays the same element while its label reads "Regrading…".
  const regradeButton = marksRegion(page).locator(".row-ai").first().locator("button");
  await expect(regradeButton).toBeEnabled();

  await regradeButton.click();
  await expect(regradeButton).toBeDisabled();
  await expect(regradeButton).toBeEnabled({ timeout: 10_000 });

  // Next.js renders its own empty role=alert route announcer, so only alerts with text count as errors.
  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveCount(0);
});

test("empty state: submit stays disabled until a file is chosen", async ({ page }) => {
  const submit = submitButton(page);
  await expect(submit).toBeDisabled();

  await page.locator('input[type="file"]').setInputFiles(pngPath);
  await expect(submit).toBeEnabled();
});

test("keyboard: tab reaches file input, mode select and submit, each with a visible outline", async ({ page }) => {
  await page.locator('input[type="file"]').setInputFiles(pngPath);
  // Clicking the heading moves the sequential focus starting point to the top of the page.
  await page.locator("h1").click();

  const outlineOfFocused = (): Promise<string> =>
    page.evaluate(() => getComputedStyle(document.activeElement as HTMLElement).outlineStyle);

  await page.keyboard.press("Tab");
  await expect(page.locator("#worksheet")).toBeFocused();
  expect(await outlineOfFocused()).not.toBe("none");

  await page.keyboard.press("Tab");
  await expect(page.locator("#mode")).toBeFocused();
  expect(await outlineOfFocused()).not.toBe("none");

  await page.keyboard.press("Tab");
  await expect(submitButton(page)).toBeFocused();
  expect(await outlineOfFocused()).not.toBe("none");
});

test("reduced motion: receipt rows have no animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await markWorksheet(page);
  const receipt = await openFirstReceipt(page);

  const animationName = await receipt
    .locator("tbody tr")
    .first()
    .evaluate((row) => getComputedStyle(row).animationName);
  expect(animationName).toBe("none");
});

test("control: receipt rows animate when reduced motion is not requested", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await markWorksheet(page);
  const receipt = await openFirstReceipt(page);

  const animationName = await receipt
    .locator("tbody tr")
    .first()
    .evaluate((row) => getComputedStyle(row).animationName);
  expect(animationName).not.toBe("none");
});

test("responsive: no horizontal scroll at 375x800 after the happy path", async ({ page }) => {
  await markWorksheet(page);
  await openFirstReceipt(page);
  await page.setViewportSize({ width: 375, height: 800 });

  const widths = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(widths.scrollWidth).toBeLessThanOrEqual(widths.innerWidth);

  mkdirSync(SCREENSHOT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, "worksheet-375x800.png"), fullPage: true });
});

test("banner: when no part can be marked, one banner says so and the parts stay under a details", async ({ page }) => {
  // The fixture reader picks the all-unmarked photo when the file name contains "greek".
  await page.locator('input[type="file"]').setInputFiles({ name: "greek.png", mimeType: "image/png", buffer: PNG_BYTES });
  await submitButton(page).click();

  await expect(page.getByText("Echo could not mark anything on this photo.")).toBeVisible({ timeout: 15_000 });
  const parts = page.locator("details.all-parts");
  await expect(parts.locator("summary")).toHaveText("Show the parts Echo read");
  await expect(parts.locator("li.row")).toHaveCount(2);
});
