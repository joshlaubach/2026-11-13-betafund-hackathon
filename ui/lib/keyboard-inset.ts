"use client";

import { useEffect } from "react";

// How far the on-screen keyboard covers the layout viewport: the gap below the visual viewport.
// Pure, so it is testable on its own. Non-finite input gives 0.
export function keyboardInset(layoutHeight: number, visualHeight: number, visualOffsetTop: number): number {
  if (!Number.isFinite(layoutHeight) || !Number.isFinite(visualHeight) || !Number.isFinite(visualOffsetTop)) return 0;
  return Math.max(0, Math.round(layoutHeight - visualHeight - visualOffsetTop));
}

// Publishes the keyboard inset as --kb-inset on <html>, so the phone tutor can lift above the keyboard.
// Does nothing when the browser has no visualViewport.
export function useKeyboardInset(): void {
  useEffect(() => {
    const visual = window.visualViewport;
    if (!visual) return;
    const root = document.documentElement;
    const update = (): void => {
      const inset = keyboardInset(window.innerHeight, visual.height, visual.offsetTop);
      root.style.setProperty("--kb-inset", `${inset}px`);
    };
    update();
    visual.addEventListener("resize", update);
    visual.addEventListener("scroll", update);
    return () => {
      visual.removeEventListener("resize", update);
      visual.removeEventListener("scroll", update);
    };
  }, []);
}
