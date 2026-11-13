// Theme toggle checks. The toggle is located only by role and accessible name, so it can move
// (for example into the page header) without changing these tests.
import { test, expect, type Page } from "@playwright/test";

const themeGroup = (page: Page) => page.getByRole("group", { name: "Theme", exact: true });
const option = (page: Page, choice: "system" | "light" | "dark") =>
  themeGroup(page).getByRole("button", { name: `Theme: ${choice}`, exact: true });
const htmlTheme = (page: Page) =>
  page.evaluate(() => document.documentElement.dataset.theme ?? null);

test("the theme toggle offers system, light and dark", async ({ page }) => {
  await page.goto("/");
  await expect(option(page, "system")).toBeVisible();
  await expect(option(page, "light")).toBeVisible();
  await expect(option(page, "dark")).toBeVisible();
});

test("choosing Dark sets data-theme to dark", async ({ page }) => {
  await page.goto("/");
  await option(page, "dark").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(option(page, "dark")).toHaveAttribute("aria-pressed", "true");
});

test("the Dark choice survives a reload", async ({ page }) => {
  await page.goto("/");
  await option(page, "dark").click();
  await page.reload();
  expect(await htmlTheme(page)).toBe("dark");
  await expect(option(page, "dark")).toHaveAttribute("aria-pressed", "true");
});

test("choosing System removes data-theme", async ({ page }) => {
  await page.goto("/");
  await option(page, "dark").click();
  await option(page, "system").click();
  expect(await page.evaluate(() => document.documentElement.hasAttribute("data-theme"))).toBe(false);
  expect(await htmlTheme(page)).toBeNull();
});

test("the page loads and the toggle works when localStorage throws", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => {
      throw new Error("storage blocked");
    };
  });

  await page.goto("/");
  await expect(option(page, "dark")).toBeVisible();
  await option(page, "dark").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(pageErrors).toEqual([]);
});
