# Teammate tasks

Which pieces of Echo suit the teammate, and why. Written so that anyone can follow it, with technical words explained where they first appear.

**How this was decided.** It is based only on the teammate's public GitHub page (7 repositories, seen on 2026-11-12). The page shows repository names and languages but no descriptions, so these are guesses from names. Ask the teammate what they are actually strongest at and how many hours they have, then adjust.

**What the page suggests:**
- **Data science in notebooks.** Customer segmentation, a recommender system, and vehicle damage classification from images. A *notebook* is a file where you run code in small steps and see the results as you go.
- **Statistics in R.** Retail profitability analysis and one more R project. R is a programming language popular for statistics.
- **Web or app work.** One TypeScript project (`skincare-ai`). TypeScript is a language for building web pages.
- **Maps.** An interactive geospatial (map-based) project.
- **Not visible:** testing, writing documentation, or symbolic math.

## Words used below

| Word | Plain meaning |
|---|---|
| **Bank** | Our prepared list of 3,510 calculus problems with answers already checked (`docs/verified_problems.json`). |
| **Level** | How hard a problem is, from 1 (easiest) to 4 (hardest). |
| **Topic** | The kind of problem, such as "u-substitution" or "power rule". The bank has 90. |
| **Checker (verifier)** | A math program that recomputes an answer to see whether a stated answer is right. |
| **Nearest neighbors** | To guess something about a new item, find the few most similar items you already know and copy what they have in common. Like guessing a movie's rating from the movies most like it. |
| **Brief** | A short written assignment that says what to build and how we will check it is done. |
| **"Done when"** | A check anyone can run to see whether the task is finished, such as a command and the output it should print. |

## Tasks that fit best

### 1. Level guesser (best fit)

- **In plain words:** when the tutor asks for "level 3," the new problems should really be level 3. The plan says to guess a problem's level by looking at the five most similar bank problems and seeing what level they have (the "nearest neighbors" idea above). This is the same kind of thinking as a recommender system: "problems like this one."
- **What gets built:** a small function that takes a problem and returns a level from 1 to 4.
- **Done when:** on bank problems the function has not seen (held out), it guesses the right level at a rate we write down. The number we measure is the number we report, even if it is lower than we hoped.
- **Why her:** nearest-neighbor and similarity work is what a recommender system is.

### 2. Bank data analysis

- **In plain words:** before we trust the bank, someone should look at it carefully. How many problems does each topic have? Are some problems copies of each other? Which topics have too few problems at some levels? The plan also needs a set of deliberately wrong answer keys ("corrupted keys") to prove the checker rejects wrong answers.
- **What gets built:** a notebook plus a script that prints counts per topic and level, lists near-duplicates, and creates the corrupted-key test data.
- **Done when:** the script runs from a clean copy of the repository and prints the counts. The numbers match the bank audit script's totals (for example, 3,450 problems at levels 1 to 4).
- **Why her:** this is the kind of data cleaning and summary work in her notebooks. It also feeds the "measured coverage" line the README promises, so we quote a real number.

### 3. Photo reading and topic matching

- **In plain words:** the tutor uploads a photo of a handwritten problem. Something has to read it and decide which of the 90 topics it belongs to. The tutor then confirms or fixes the reading, because handwriting is messy.
- **What gets built:** a function that takes a photo and returns the problem text and a best-guess topic. We would first choose which image-reading AI to use.
- **Done when:** on a set of sample photos we collect, it returns text and a topic, and we report how often the topic is right.
- **Why her:** she has worked with image classification.
- **Needs a decision first:** which image model to use (an online AI service or one that runs on the laptop). Online services need the venue wifi, and our plan already has a fallback for when it fails.

### 4. Chat screens

- **In plain words:** the part the tutor actually sees. A page to upload the photo, a screen to confirm what was read, and a list of three problems that each show where they came from (checked by Echo, or "bank-verified, not Echo-checked").
- **What gets built:** the web pages. The checking behind them is built separately and plugged in.
- **Done when:** the pages open in a browser, and with fake sample data we can click through from upload to three labeled problems.
- **Why her:** she has a TypeScript project, so she may already know how to build pages. Confirm this.

### 5. Demo and pitch

- **In plain words:** judges see the demo and the README first. We need a saved replay (a recording of a good run, labeled as a replay), a backup video in case the laptop fails, an up-to-date status table in `README.md`, and a "Running it" section.
- **Done when:** the replay plays without internet, and someone who has never seen the project can follow the "Running it" steps.
- **Why her:** it works in parallel with everything else and suits anyone good at explaining.

## Tasks to keep with the orchestrator and workers

- **The checkers and the gate script.** These are the heart of the claim "a math program checked this." A mistake here quietly breaks the main promise, so they stay with the orchestrator (the main Claude session), the Haiku workers, and a review step.
- **`core/input_boundary.py`.** This is the strict reader that turns text into math safely. It is security-sensitive and already heavily tested.

## Working together

- **Separate folders.** Give each task its own folder (for example `levels/`, `notebooks/`, `ui/`) so two people never edit the same file.
- **Write a brief for each task** with a "Done when" check, the same way we do for the Haiku workers.
- **Share the repository.** The repository is private, so the teammate must be added as a collaborator before starting.
- **Start today with tasks 1 and 2.** Neither waits on the checker work.
