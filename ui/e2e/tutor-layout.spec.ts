// Layout checks for the docked tutor: it stays inside the viewport on desktop, tablet and phone sizes, its composer
// stays reachable in a long conversation, and it survives a resize. Fixture data only (NEXT_PUBLIC_FIXTURES=1), no model.
// Motion is reduced so the tutor's slide finishes at once and the boxes measured are its final positions.
import { test, expect, type Locator, type Page } from "@playwright/test";
import { keyboardInset } from "../lib/keyboard-inset";

// The tutor is docked beside the workspace on desktop and is its own view on phones and tablets.
const panel = (page: Page): Locator => page.locator('[role="region"][aria-label="Echo tutor"]');
const launcher = (page: Page): Locator => page.locator("button.tutor-launch");
const tutorTab = (page: Page): Locator => page.getByRole("tab", { name: "Tutor", exact: true });

async function openTutor(page: Page, width: number): Promise<void> {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width, height: 900 });
  await page.goto("/");
  // Below 62rem (992px) the tutor is a tab; above it the launcher docks the tutor.
  if (width < 992) await tutorTab(page).click();
  else await launcher(page).click();
  await expect(panel(page)).toBeVisible();
}

async function expectInsideViewport(page: Page, locator: Locator): Promise<void> {
  const box = await locator.boundingBox();
  const size = await page.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight }));
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(-1);
  expect(box!.y).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(size.width + 1);
  expect(box!.y + box!.height).toBeLessThanOrEqual(size.height + 1);
}

async function expectComposerInside(page: Page): Promise<void> {
  const tutor = panel(page);
  await expectInsideViewport(page, tutor.getByLabel("Ask the tutor"));
  await expectInsideViewport(page, tutor.getByRole("button", { name: "Send" }));
}

async function expectNoSidewaysScroll(page: Page): Promise<void> {
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client);
}

async function ask(page: Page, text: string): Promise<void> {
  const input = panel(page).getByLabel("Ask the tutor");
  await input.fill(text);
  await input.press("Enter");
}

const SIZES = [
  { name: "desktop 1440x900", width: 1440, height: 900 },
  { name: "desktop 1280x640", width: 1280, height: 640 },
  { name: "small desktop 1024x600", width: 1024, height: 600 },
  { name: "tablet 820x1180", width: 820, height: 1180 },
  { name: "phone 390x844", width: 390, height: 844 },
];

for (const size of SIZES) {
  test(`the tutor fits the viewport at ${size.name}`, async ({ page }) => {
    await openTutor(page, size.width);
    await expectInsideViewport(page, panel(page));
    await expectComposerInside(page);
    await expectNoSidewaysScroll(page);
  });
}

test("a long conversation scrolls in the log and keeps the composer in view", async ({ page }) => {
  await openTutor(page, 1280);
  const tutor = panel(page);
  for (let count = 1; count <= 12; count += 1) {
    await ask(page, `Question ${count} about the chain rule`);
    await expect(tutor.locator(".tutor-turn-tutor")).toHaveCount(count, { timeout: 10_000 });
  }
  const log = await tutor.locator(".tutor-log").evaluate((element) => ({
    scroll: element.scrollHeight,
    client: element.clientHeight,
  }));
  expect(log.scroll).toBeGreaterThan(log.client);
  // The log is the element that scrolls, so the panel itself does not overflow.
  const panelOverflow = await tutor.evaluate((element) => element.scrollHeight - element.clientHeight);
  expect(panelOverflow).toBeLessThanOrEqual(1);
  await expectInsideViewport(page, tutor);
  await expectComposerInside(page);
});

test("the tutor stays inside the viewport after a resize", async ({ page }) => {
  await openTutor(page, 1440);
  await page.setViewportSize({ width: 1280, height: 600 });
  await expectInsideViewport(page, panel(page));
  await expectComposerInside(page);
});

test("keyboardInset is the gap under the visual viewport, never negative", () => {
  expect(keyboardInset(800, 500, 0)).toBe(300);
  expect(keyboardInset(800, 800, 0)).toBe(0);
  expect(keyboardInset(800, 500, 100)).toBe(200);
  expect(keyboardInset(Number.NaN, 500, 0)).toBe(0);
  expect(keyboardInset(500, 800, 0)).toBe(0);
});
