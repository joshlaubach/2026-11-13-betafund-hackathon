"use client";

import { useEffect, useState } from "react";
import { THEME_STORAGE_KEY } from "@/lib/theme";

export type ThemeChoice = "system" | "light" | "dark";

const CHOICES: readonly ThemeChoice[] = ["system", "light", "dark"];
const DEFAULT_CHOICE: ThemeChoice = "system";
const LABELS: Record<ThemeChoice, string> = { system: "System", light: "Light", dark: "Dark" };

function isThemeChoice(value: string | null): value is ThemeChoice {
  return value !== null && (CHOICES as readonly string[]).includes(value);
}

function readStoredChoice(): ThemeChoice {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeChoice(value) ? value : DEFAULT_CHOICE;
  } catch {
    // Storage can throw (blocked or disabled); treat it as no stored choice.
    return DEFAULT_CHOICE;
  }
}

function writeStoredChoice(choice: ThemeChoice): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // The choice still applies for this page view; it just will not persist.
  }
}

function applyChoice(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === DEFAULT_CHOICE) {
    root.removeAttribute("data-theme");
    return;
  }
  root.dataset.theme = choice;
}

export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>(DEFAULT_CHOICE);

  // Read after mount so server and client markup match; the inline script in layout.tsx already set the attribute.
  useEffect(() => {
    setChoice(readStoredChoice());
  }, []);

  const choose = (next: ThemeChoice): void => {
    setChoice(next);
    writeStoredChoice(next);
    applyChoice(next);
  };

  return (
    <div role="group" aria-label="Theme" className="theme-toggle">
      {CHOICES.map((option) => (
        <button
          key={option}
          type="button"
          className="theme-toggle-option"
          aria-label={`Theme: ${option}`}
          aria-pressed={choice === option}
          onClick={() => choose(option)}
        >
          {LABELS[option]}
        </button>
      ))}
    </div>
  );
}
