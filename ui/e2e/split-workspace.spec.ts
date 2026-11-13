// Unit checks for the docked tutor's width helpers. No browser page is needed; storage is faked.
import { expect, test } from "@playwright/test";
import {
  TUTOR_DEFAULT_WIDTH,
  TUTOR_MIN_WIDTH,
  TUTOR_WIDTH_KEY,
  clampTutorWidth,
  nextWidthForKey,
  readStoredWidth,
  writeStoredWidth,
  type StorageLike,
} from "../lib/split";

const WIDE = 1440;

function memoryStorage(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = value;
    },
  };
}

function throwingStorage(): StorageLike {
  return {
    getItem: () => {
      throw new Error("storage blocked");
    },
    setItem: () => {
      throw new Error("quota exceeded");
    },
  };
}

test("clampTutorWidth keeps widths between 320px and 60% of the viewport", () => {
  expect(clampTutorWidth(100, WIDE)).toBe(TUTOR_MIN_WIDTH);
  expect(clampTutorWidth(900, WIDE)).toBe(Math.floor(WIDE * 0.6));
  expect(clampTutorWidth(400, WIDE)).toBe(400);
});

test("clampTutorWidth rounds fractional pixels and falls back to the default for non-finite input", () => {
  expect(clampTutorWidth(401.6, WIDE)).toBe(402);
  expect(clampTutorWidth(Number.NaN, WIDE)).toBe(TUTOR_DEFAULT_WIDTH);
  expect(clampTutorWidth(Number.POSITIVE_INFINITY, WIDE)).toBe(TUTOR_DEFAULT_WIDTH);
});

test("on a narrow viewport the 320px minimum still wins over the 60% cap", () => {
  expect(clampTutorWidth(500, 400)).toBe(TUTOR_MIN_WIDTH);
});

test("ArrowLeft widens and ArrowRight narrows by 24px, clamped to the limits", () => {
  expect(nextWidthForKey("ArrowLeft", 420, WIDE)).toBe(444);
  expect(nextWidthForKey("ArrowRight", 420, WIDE)).toBe(396);
  expect(nextWidthForKey("ArrowRight", TUTOR_MIN_WIDTH, WIDE)).toBe(TUTOR_MIN_WIDTH);
  expect(nextWidthForKey("ArrowLeft", Math.floor(WIDE * 0.6), WIDE)).toBe(Math.floor(WIDE * 0.6));
});

test("Home goes to the minimum width and End to the maximum", () => {
  expect(nextWidthForKey("End", 420, WIDE)).toBe(Math.floor(WIDE * 0.6));
  expect(nextWidthForKey("Home", 420, WIDE)).toBe(TUTOR_MIN_WIDTH);
});

test("nextWidthForKey returns null for keys it does not handle", () => {
  expect(nextWidthForKey("a", 420, WIDE)).toBeNull();
  expect(nextWidthForKey("ArrowUp", 420, WIDE)).toBeNull();
});

test("a stored width is read back as a number", () => {
  const storage = memoryStorage({ [TUTOR_WIDTH_KEY]: "512" });
  expect(readStoredWidth(storage)).toBe(512);
});

test("a missing, non-numeric, or missing-storage value reads as null", () => {
  expect(readStoredWidth(memoryStorage())).toBeNull();
  expect(readStoredWidth(memoryStorage({ [TUTOR_WIDTH_KEY]: "wide" }))).toBeNull();
  expect(readStoredWidth(null)).toBeNull();
});

test("writeStoredWidth stores the width under the echo-tutor-width key", () => {
  const storage = memoryStorage();
  expect(writeStoredWidth(storage, 480)).toBe(true);
  expect(storage.data[TUTOR_WIDTH_KEY]).toBe("480");
  expect(writeStoredWidth(null, 480)).toBe(false);
});

test("storage that throws never breaks reading or writing", () => {
  expect(readStoredWidth(throwingStorage())).toBeNull();
  expect(writeStoredWidth(throwingStorage(), 480)).toBe(false);
});
