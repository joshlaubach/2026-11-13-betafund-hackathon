"use client";

import { useEffect, useId, useRef } from "react";
import type { Mode } from "@/lib/types";
import { STREAK_MAX_LENGTH, STREAK_MIN_LENGTH } from "@/lib/streak";
import { ThemeToggle } from "./ThemeToggle";

export const MODES: { value: Mode; label: string }[] = [
  { value: "live", label: "Live AI (needs internet)" },
  { value: "replay", label: "Saved replay (works offline)" },
  { value: "fake", label: "Scripted demo data" },
];

export interface SettingsPanelProps {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  streakLength: number;
  onStreakLengthChange: (length: number) => void;
  onClose: () => void;
}

export function SettingsPanel({ mode, onModeChange, streakLength, onStreakLengthChange, onClose }: SettingsPanelProps) {
  const titleId = useId();
  const lengthId = useId();
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  useEffect(() => {
    function handleKey(event: KeyboardEvent): void {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <section ref={panelRef} tabIndex={-1} role="dialog" aria-labelledby={titleId} className="settings-panel">
      <div className="settings-head">
        <h2 id={titleId}>Settings</h2>
        <button type="button" className="quiet" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="settings-row">
        <ThemeToggle />
      </div>
      <div className="field">
        <label htmlFor="mode">Where marks come from</label>
        <select id="mode" value={mode} onChange={(event) => onModeChange(event.target.value as Mode)}>
          {MODES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={lengthId}>Streak length</label>
        <div className="settings-length">
          <input
            id={lengthId}
            type="range"
            min={STREAK_MIN_LENGTH}
            max={STREAK_MAX_LENGTH}
            step={1}
            value={streakLength}
            onChange={(event) => onStreakLengthChange(Number(event.target.value))}
          />
          <output htmlFor={lengthId}>{streakLength} problems</output>
        </div>
      </div>
    </section>
  );
}
