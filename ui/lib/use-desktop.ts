"use client";

import { useSyncExternalStore } from "react";

export const DESKTOP_QUERY = "(min-width: 62rem)";

function subscribeToDesktop(onChange: () => void): () => void {
  const query = window.matchMedia(DESKTOP_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function readDesktop(): boolean {
  return window.matchMedia(DESKTOP_QUERY).matches;
}

// The server renders the desktop layout; the client corrects it after hydration without a mismatch warning.
export function useIsDesktop(): boolean {
  return useSyncExternalStore(subscribeToDesktop, readDesktop, () => true);
}
