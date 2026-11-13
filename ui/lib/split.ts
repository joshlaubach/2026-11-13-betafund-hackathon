// Pure helpers for the docked tutor's width. No React here, so they are testable on their own.

export const TUTOR_WIDTH_KEY = "echo-tutor-width";
export const TUTOR_DEFAULT_WIDTH = 420;
export const TUTOR_MIN_WIDTH = 320;
export const TUTOR_MAX_SHARE = 0.6;
export const TUTOR_KEY_STEP = 24;

export type StorageLike = Pick<Storage, "getItem" | "setItem">;

export function tutorMaxWidth(viewport: number): number {
  return Math.max(TUTOR_MIN_WIDTH, Math.floor(viewport * TUTOR_MAX_SHARE));
}

// Keeps a width between the minimum and 60% of the viewport. Non-finite input falls back to the default.
export function clampTutorWidth(px: number, viewport: number): number {
  const requested = Number.isFinite(px) ? Math.round(px) : TUTOR_DEFAULT_WIDTH;
  return Math.min(tutorMaxWidth(viewport), Math.max(TUTOR_MIN_WIDTH, requested));
}

// Keyboard resizing. ArrowLeft widens the tutor (the separator moves left), ArrowRight narrows it.
// Home jumps to the minimum and End to the maximum (the usual separator convention). Returns null for keys this does not handle.
export function nextWidthForKey(key: string, current: number, viewport: number): number | null {
  if (key === "ArrowLeft") return clampTutorWidth(current + TUTOR_KEY_STEP, viewport);
  if (key === "ArrowRight") return clampTutorWidth(current - TUTOR_KEY_STEP, viewport);
  if (key === "Home") return TUTOR_MIN_WIDTH;
  if (key === "End") return tutorMaxWidth(viewport);
  return null;
}

// Storage access can throw (privacy modes, quota, disabled storage). Both functions swallow that.
export function readStoredWidth(storage: StorageLike | null): number | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(TUTOR_WIDTH_KEY);
    if (raw === null) return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function writeStoredWidth(storage: StorageLike | null, width: number): boolean {
  if (!storage) return false;
  try {
    storage.setItem(TUTOR_WIDTH_KEY, String(width));
    return true;
  } catch {
    return false;
  }
}

// window.localStorage itself can throw when the browser blocks storage.
export function browserStorage(): StorageLike | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}
