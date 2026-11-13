// Checks the size arithmetic behind browser-side photo preparation. Pure functions only: no page, no server.
import { test, expect } from "@playwright/test";
import { MAX_SIDE_PX, scaledSize } from "../lib/photo";

test("scaledSize leaves a photo that already fits unchanged", () => {
  expect(scaledSize(1600, 1200, MAX_SIDE_PX)).toEqual({ width: 1600, height: 1200 });
});

test("scaledSize fits the long side to 2000 and keeps the aspect ratio, landscape or portrait", () => {
  expect(scaledSize(4032, 3024, MAX_SIDE_PX)).toEqual({ width: 2000, height: 1500 });
  expect(scaledSize(3024, 4032, MAX_SIDE_PX)).toEqual({ width: 1500, height: 2000 });
});

test("scaledSize never upscales a small photo", () => {
  expect(scaledSize(800, 600, MAX_SIDE_PX)).toEqual({ width: 800, height: 600 });
});

test("scaledSize keeps at least one pixel on the short side", () => {
  expect(scaledSize(4000, 1, MAX_SIDE_PX)).toEqual({ width: 2000, height: 1 });
});
