// Difficulty is chosen by Echo and never shown to the student: no "level N" wording on the practice buttons
// or in the practice notes. Fixture data only (NEXT_PUBLIC_FIXTURES=1).
import { test, expect, type Locator, type Page } from "@playwright/test";

const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
const skillsRegion = (page: Page): Locator => page.locator('section[aria-labelledby="skills-heading"]');
const practiceRegion = (page: Page): Locator => page.locator('section[aria-labelledby="practice-heading"]');

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "worksheet.png", mimeType: "image/png", buffer: PNG_BYTES });
  await page.locator('form.upload button[type="submit"]').click();
  await expect(skillsRegion(page)).toBeVisible({ timeout: 15_000 });
});

test("practice buttons say what they do and never mention a level", async ({ page }) => {
  const buttons = skillsRegion(page).locator("li.row button");
  await expect(buttons.first()).toHaveText("Practice this topic");
  await expect(skillsRegion(page)).not.toContainText(/\blevel\b/i);
});

test("the practice section shows no level wording after problems are made", async ({ page }) => {
  await skillsRegion(page).locator("li.row button").first().click();
  await expect(practiceRegion(page)).toBeVisible({ timeout: 15_000 });
  await expect(practiceRegion(page)).not.toContainText(/\blevel\b/i);
  await expect(practiceRegion(page)).not.toContainText(/showing bank problems|bank problem\(s\)/);
});
