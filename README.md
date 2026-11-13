# Echo

Echo reads a photo of a finished calculus worksheet, marks the student's final answers, and shows which topics need practice. It recommends topics from the marks and serves new problems with a label that says how each problem was checked.

## How a mark is made

The AI reading step separates each question, the student's final answer, and any setup shared by several parts. The page shows the reading beside the marks. Every mark carries a method label.

| Route | What happens | Label on the mark |
|---|---|---|
| Low confidence read | If the reader flags a part as unclear, live and fake grading leave it unsure. | Not marked |
| Bank match | The question matches an eligible bank problem. SymPy compares the student's answer with its bank key. | Verified bank answer |
| SymPy computation | SymPy computes a reference answer for a supported derivative, limit, value, definite or indefinite integral, tangent line, equation, or solution set. It then compares the student's answer. | Echo's checker computed the answer |
| AI ladder | When SymPy cannot compute the answer, two models solve the question without seeing the student's answer. A third model breaks a disagreement. SymPy may compare the answers, but it does not verify the AI's answer. | AI graded; not verified by Echo |
| AI judge | When the answer cannot be compared as math, a model judges the mathematical answer. | AI judgment only |

A blind AI solve also checks a computed SymPy answer when available. Agreement confirms it; disagreement makes the mark unsure. It never turns a correct mark into incorrect or an incorrect mark into correct. The **Regrade** button re-runs AI marking in live mode. Replay and fake mode keep the existing mark.

The skill picture counts marks per topic. Recommendations put weak topics first, then shaky topics, then topics with too little data. Within each group, topics follow course order. Only `power_rule` has a gate for Echo-checked generated practice problems. Other usable topics serve bank problems labeled **“bank-verified, not Echo-checked.”**

## Running it

Docker with Compose v2 runs the API at `http://127.0.0.1:8000` and the page at `http://localhost:3000`. Run these commands from this folder:

```bash
docker build -t echo-api .
docker build -t echo-ui ui
docker compose up -d --wait
```

Open http://localhost:3000. Stop the stack with `docker compose down`. The API build runs the `power_rule` gate. Both published ports bind to `127.0.0.1`.

Choose **Live AI**, **Saved replay**, or **Scripted demo data** on the page. Live needs internet and `ANTHROPIC_API_KEY` in the environment or an untracked `.env` file. The API defaults to replay mode, but the page opens with Live AI selected; choose Saved replay to use a saved photo reading. Replay needs a saved reading for that exact photo. Scripted demo data uses fake reading and grades without a model call.

For a page-only fixture demo in PowerShell, run:

```powershell
cd ui
npm ci
$env:NEXT_PUBLIC_FIXTURES = "1"
npm run dev
```

Open http://localhost:3000. Fixture mode serves sample readings, marks, and practice problems from the page code. It does not call the API.

## What to be honest about

- AI marks can be wrong. SymPy comparing a student's answer with an AI answer does not verify the AI answer.
- A misread question or final answer can produce a wrong mark and a misleading skill picture. The reader may split handwritten working and final answers differently on another run.
- Parametric curves and questions based on graphs or tables have no worksheet SymPy route here; they fall to AI solving or judgment. SymPy does handle two-sided limits when both sides have the same real limit. Limits that it cannot compute fall to AI. Written prose explanations are shown but are not graded.
- The profile endpoint trusts the marks sent by the page. This design is suitable only for the local demo, where the API is bound to localhost and checks Host, Origin on writes, and request body size. It has no login.
- Only one topic has Echo-checked generated problems. A bank label means the problem came from the audited bank; it does not mean Echo checked a new AI draft for that topic.
- An AI cross-check can confirm a SymPy mark or make it unsure. It cannot reverse the verdict.
- Voice input uses your browser's built-in speech recognition. Chrome and Edge may send the audio to the browser vendor. It never reaches Echo's server, and typing works without it. Typed or spoken text is turned into LaTeX by a small AI call, and Echo grades nothing until you confirm its reading.
- Echo's upload code strips image metadata, including location data, before reading supported photos. It keeps photo bytes in memory and does not save them in replay files. Saved replays contain readings and marks.

## Status

| Piece | Status on 2026-11-12 |
|---|---|
| Finished worksheet photo reading | Built: live vision, matching saved replay, and scripted fake reading |
| Answer marking | Built: bank, SymPy, AI ladder, AI judge, and low-confidence handling |
| Skill picture and practice | Built: topic counts, ranked recommendations, and labeled practice problems |
| Echo-checked generated practice | `power_rule` only; other usable topics use labeled bank problems |
| Browser page and Docker | Built: upload, results, Regrade, practice, and local API and page containers |
| Typed or voice correction of a reading | Built: on an unsure or unmarked part, type or speak what it says, confirm Echo's understanding, then the corrected part is graded and tagged "Corrected by you" |
| Why a mark is unsure | Built: each unsure mark says whether the reading, the form of the answers, a disagreement between solves, a missing AI answer, or a known rule is the cause |

The bank and reused `app/` checking code predate this worksheet flow. See [progress](docs/progress.md), [decisions](docs/decisions.md), and [known issues](docs/known-issues.md) for current notes.
