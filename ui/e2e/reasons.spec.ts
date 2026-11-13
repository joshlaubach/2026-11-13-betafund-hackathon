// Fixture-mode checks for the reason line under an unsure row and for the Regrade button on it.
// Runs on built-in fixture data only (NEXT_PUBLIC_FIXTURES=1), so no model or network call is made.
import { test, expect } from "@playwright/test";

// A 1x1 PNG, the same bytes as worksheet.spec.ts. Fixture mode never reads the image.
const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const READING_LINE = "Echo could not read this part clearly. Retake a clearer photo of it.";
const NO_VERDICT_LINE = "The AI gave no answer for this part. Try Regrade.";

test("a no-verdict row offers Regrade, and a reading row shows the reading line without Regrade", async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "worksheet.png", mimeType: "image/png", buffer: PNG_BYTES });
  await page.locator('form.upload button[type="submit"]').click();

  const marks = page.locator('section[aria-labelledby="marks-heading"]');
  await expect(marks).toBeVisible({ timeout: 15_000 });

  const readingRow = marks.locator("li.row").filter({ hasText: READING_LINE });
  await expect(readingRow).toHaveCount(1);
  await expect(readingRow.getByRole("button")).toHaveCount(0);

  const noVerdictRow = marks.locator("li.row").filter({ hasText: NO_VERDICT_LINE });
  await expect(noVerdictRow).toHaveCount(1);
  await expect(noVerdictRow.getByRole("button", { name: "Regrade" })).toBeVisible();
});
