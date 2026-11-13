// Settings panel checks in fixture mode. The panel holds the theme toggle, the marks source, and the streak length.
import { test, expect, type Page } from "@playwright/test";

const settingsButton = (page: Page) => page.getByRole("button", { name: "Settings", exact: true });
const dialog = (page: Page) => page.getByRole("dialog", { name: "Settings", exact: true });
const lengthSlider = (page: Page) => page.getByRole("slider", { name: "Streak length" });

test("the Settings button opens the panel, which holds the theme, the marks source and the streak length", async ({ page }) => {
  await page.goto("/");
  await expect(dialog(page)).toHaveCount(0);
  await settingsButton(page).click();
  await expect(dialog(page)).toBeVisible();
  await expect(page.getByRole("group", { name: "Theme", exact: true })).toBeVisible();
  await expect(page.getByLabel("Where marks come from")).toBeVisible();
  await expect(lengthSlider(page)).toHaveValue("5");
});

test("Escape closes the panel and returns focus to the Settings button", async ({ page }) => {
  await page.goto("/");
  await settingsButton(page).click();
  await expect(dialog(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog(page)).toHaveCount(0);
  await expect(settingsButton(page)).toBeFocused();
});

test("the streak length slider persists across a reload", async ({ page }) => {
  await page.goto("/");
  await settingsButton(page).click();
  await lengthSlider(page).focus();
  await page.keyboard.press("ArrowLeft");
  await expect(lengthSlider(page)).toHaveValue("4");
  await page.reload();
  await settingsButton(page).click();
  await expect(lengthSlider(page)).toHaveValue("4");
});

test("a blocked localStorage does not break the page or the slider", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.addInitScript(() => {
    const blocked = () => {
      throw new Error("storage blocked");
    };
    Storage.prototype.getItem = blocked;
    Storage.prototype.setItem = blocked;
  });
  await page.goto("/");
  await settingsButton(page).click();
  await expect(lengthSlider(page)).toHaveValue("5");
  await lengthSlider(page).focus();
  await page.keyboard.press("ArrowRight");
  await expect(lengthSlider(page)).toHaveValue("6");
  expect(pageErrors).toEqual([]);
});
