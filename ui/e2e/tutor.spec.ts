// Page-level checks for the tutor: it opens and closes, answers with a grounded reply, and its suggested
// actions really drive the practice workspace. Fixture data only (NEXT_PUBLIC_FIXTURES=1), no model.
import { test, expect, type Locator, type Page } from "@playwright/test";

const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);
// The tutor is docked beside the workspace on desktop and is its own view on phones.
const panel = (page: Page): Locator => page.locator('[role="region"][aria-label="Echo tutor"]');
const skillsRegion = (page: Page): Locator => page.locator('section[aria-labelledby="skills-heading"]');
const practiceRegion = (page: Page): Locator => page.locator('section[aria-labelledby="practice-heading"]');
const launcher = (page: Page): Locator => page.locator("button.tutor-launch");

async function markWorksheet(page: Page): Promise<void> {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "worksheet.png", mimeType: "image/png", buffer: PNG_BYTES });
  await page.locator('form.upload button[type="submit"]').click();
  await expect(skillsRegion(page)).toBeVisible({ timeout: 15_000 });
}

async function ask(page: Page, text: string): Promise<void> {
  const input = panel(page).getByLabel("Ask the tutor");
  await input.fill(text);
  await input.press("Enter");
}

test("the launcher docks the tutor with focus in the input, and Escape closes it", async ({ page }) => {
  await page.goto("/");
  await expect(panel(page)).toBeHidden();
  await launcher(page).click();
  await expect(panel(page)).toBeVisible();
  await expect(panel(page).getByLabel("Ask the tutor")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(panel(page)).toBeHidden();
});

test("a question gets a grounded reply with its bank source, provenance, and suggested actions", async ({ page }) => {
  await markWorksheet(page);
  await launcher(page).click();
  await ask(page, "Explain the chain rule");
  const tutor = panel(page);
  await expect(tutor.getByText("CR38").first()).toBeVisible({ timeout: 10_000 });
  await expect(tutor.getByText(/Offline tutor/)).toBeVisible();
  await expect(tutor.locator("summary", { hasText: "Sources (1)" })).toBeVisible();
  await expect(tutor.getByRole("button", { name: "Try a harder problem" })).toBeVisible();
});

test("a suggested action really makes a new practice set", async ({ page }) => {
  await markWorksheet(page);
  await launcher(page).click();
  await ask(page, "Explain the chain rule");
  await panel(page).getByRole("button", { name: "Try a harder problem" }).click();
  await expect(practiceRegion(page)).toBeVisible({ timeout: 15_000 });
  await expect(practiceRegion(page).locator("li.row").first()).toBeVisible();
});

test("asking the tutor from a problem sends that problem, and a step action reveals the next step on its card", async ({ page }) => {
  await markWorksheet(page);
  await skillsRegion(page).locator("li.row button").first().click();
  const practice = practiceRegion(page);
  await expect(practice).toBeVisible({ timeout: 15_000 });
  // The third card is a bank problem with a worked step.
  const card = practice.locator("li.row").nth(2);
  await card.getByRole("button", { name: "Ask the tutor" }).click();
  const tutor = panel(page);
  await expect(tutor.getByText("Help me get started on this problem.")).toBeVisible();
  // Wait for the reply to the automatic first prompt before asking again.
  await expect(tutor.getByText("CR38").first()).toBeVisible({ timeout: 10_000 });
  await ask(page, "give me a hint");
  await tutor.getByRole("button", { name: "Show the next step" }).click();
  await expect(card.getByText("Bring the power down and lower it by one.")).toBeVisible({ timeout: 10_000 });
});

test("a failed reply shows an error with a working Retry", async ({ page }) => {
  await page.goto("/");
  await launcher(page).click();
  await ask(page, "this will fail");
  const tutor = panel(page);
  await expect(tutor.getByRole("alert")).toBeVisible({ timeout: 10_000 });
  await expect(tutor.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("no horizontal overflow with the tutor open on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 760 });
  await markWorksheet(page);
  await launcher(page).click();
  await ask(page, "Explain the chain rule");
  await expect(panel(page).getByText("CR38").first()).toBeVisible({ timeout: 10_000 });
  const widths = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, inner: window.innerWidth }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.inner);
});
