# Streak game and Settings: spec

## Streak (practice game)

- **Trigger.** A worksheet part marked Incorrect or Unsure shows a "Start streak" button. Parts that are Not marked (method not_graded, or low confidence) never show it.
- **Where.** The streak runs inside the tutor panel, on the part's topic. The level starts at the level Echo suggests for that topic.
- **Problems.** Bank problems for the topic, from the existing practice request. Each answer is checked by the existing practice check. No new checker.
- **Level.** The first streak runs at the mistake's level. Each completed streak raises the next one by one, capped at mistake + 1 and at level 4. A reset keeps the current level.
- **Not enough problems.** If the level has fewer problems than the streak length, the rest come from the next level up (or down at the top). Those problems are labelled "From a nearby level".
- **Length.** Read from Settings. Default 5, range 3 to 6. A streak may be shorter than the length when the topic has fewer distinct problems: it then starts at the number available and says so, "Only N different problems are available for this topic, so this streak is N long."
- **Progress.** A bar shows N correct in a row out of N.
- **Wrong answer.** The bar resets to 0 and a new problem starts. The note is plain: "Not quite. The streak starts again with a new problem."
- **Unsure answer.** Same as wrong, with: "Echo could not check that one, so the streak starts again."
- **Hints.** Allowed during a streak. They do not count as correct.
- **Full solution.** Ends the streak: "Streak ended: you looked at the solution". It does not count.
- **Completion.** At N correct: a short animation (none when reduced motion is set), the heading "Streak complete", the concept name, and the buttons "Start another streak" and "Back to worksheet".
- **Style.** Existing design tokens, both themes. The bar uses the pen colour on a soft track.
- **Scope.** A practice game only. The tutor chat is unchanged.

## Settings

- A "Settings" gear button in the masthead, beside "Ask the tutor". It opens a panel under the masthead tools. Escape closes it and returns focus to the button.
- The panel holds: the theme toggle (moved from the masthead), "Where marks come from" (moved from the upload area), and "Streak length" (a slider from 3 to 6, showing the current value).
- The streak length is stored under `echo-streak-length` in localStorage. Every read and write is guarded: a blocked store never breaks the page. Missing or invalid values fall back to 5.

## Code

- `ui/lib/streak.ts`: pure level, length and state logic (no React).
- `ui/components/StreakCard.tsx`: the streak card and progress bar, rendered in the tutor panel.
- `ui/components/SettingsPanel.tsx`: the Settings panel.
- Tests: `ui/e2e/streak-lib.spec.ts`, `ui/e2e/streak.spec.ts`, `ui/e2e/settings.spec.ts`.
