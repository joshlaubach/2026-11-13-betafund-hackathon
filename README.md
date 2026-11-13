# Echo

**Echo turns a photo of a math problem a student got wrong into up to three fresh practice problems of the same kind. A math program checks every AI-written problem before a tutor sees it. Where we have no checker yet, Echo shows verified problems from a prepared bank and labels them clearly.**

---

## The problem, in plain words

A tutor sits with a student who just missed a problem. The best next step is to practice the *same kind* of problem a few more times. Making those up by hand takes time. Asking an AI is fast, but AI sometimes writes problems with **wrong answers**, and a tutor who hands a student a wrong answer does real damage.

Echo keeps the speed of AI and removes the risk: **no AI-written problem reaches the tutor unless the checker has proven its answer is right.** Problems that did not come from the AI come from a bank of problems verified earlier, and they are labeled so the tutor always knows which kind they are looking at.

---

## The math in one minute

Echo covers **Calculus I and II**. The one checker built so far is for the **power rule**, a Calculus I derivative topic. The integration-by-substitution examples further down describe a checker that is **planned, not built yet**; they are marked as such.

- A **derivative** tells you how fast something is changing. The derivative of $x^2$ is $2x$.
- An **integral** goes the other way: it finds what you started with, given how fast it was changing. It is written $\int f(x)\,dx$, and an answer to it is called an **antiderivative**.
- An **indefinite integral** has no start or end point, so its answer is a formula plus a constant $C$ (any fixed number). Example: $\int 2x\,dx = x^2 + C$.
- A **definite integral** has a start and an end, like $\int_0^1 2x\,dx$, and its answer is one number. Here it is $1$.
- **Substitution** is a trick for spotting a function inside a function and renaming the inside part $u$ to make the problem easy. In $\int 2x\cos(x^2)\,dx$, let $u = x^2$. The integral becomes $\int \cos(u)\,du = \sin(u) + C = \sin(x^2) + C$.
- A **domain** is the set of numbers the problem is allowed to use. "$x > 0$" means only positive numbers.
- A **real number** is an ordinary number on the number line, not an imaginary one like $\sqrt{-1}$.
- $\ln$ is the **natural log**, a function that only accepts *positive* numbers. $\ln(-5)$ is not a real number.
- A **level** from 1 to 4 says how hard a problem is. 1 is the easiest and 4 is the hardest.

---

## The moment to look for

In the chat, the AI proposes a problem with a wrong answer key. The checker **rejects it**, and the bot explains *why*, using the checker's own numbers.

**What works today (run `python scripts/demo_wrong_key.py`).** The problem is "Find $f'(x)$ for $f(x) = x^4 + 3x^2 + 7$". The checker computes the derivative itself and compares it with the key on 10 test points. The correct key $4x^3 + 6x$ is accepted. The same key with $+1$ added is rejected with: "at x = 0.3137 the checker computes 2.00568 but the key gives 3.00568". Those numbers come from the checker, not from the AI. The wrong key in this demo was made on purpose (the bank key plus 1); it is not something a live AI produced.

**What is planned, not built (integral checker).** Here is the kind of mistake the substitution checker is meant to catch. The problem is:

$$\int \frac{2}{x}\,dx \quad \text{for } x > 0$$

Suppose the AI says the answer is $\ln(-x^2)$. Taking the derivative of that gives $\frac{2}{x}$, which looks right! But $\ln(-x^2)$ asks for the log of a *negative* number whenever $x > 0$, and that is not a real number. A quick "does the derivative match?" test would pass it. Echo's checker does not, because it also checks that the answer is a real number everywhere the problem lives. The correct answer is $2\ln(x) + C$.

---

## What Echo does

Echo is aimed at **all of Calculus I and II**, which is 90 topics in the problem bank (a few are not usable yet because their problems need figures we do not have). A topic only gets the "Echo-checked" label after its own checker passes a test against our verified problem bank. Topics that have not passed yet show problems straight from the bank when usable ones exist, clearly labeled **"bank-verified, not Echo-checked."** The number of topics that are Echo-checked is measured by a script, and we quote that number rather than promising all of them.

1. The tutor **uploads a photo** of a handwritten problem into a chat.
2. The photo reader **reads it**. The tutor **confirms or fixes** the reading, because handwriting is messy and a wrong reading would spoil everything after it.
3. The tutor asks for **three problems at a level from 1 to 4**.
4. If the topic is Echo-checked, the AI writes **five drafts**. The checker tests every one. **The first three that pass are shown,** each with a checker log. Otherwise the tutor gets up to three problems from the bank, labeled as above, when usable ones exist, or a clear "not supported yet" message when they do not.
5. The tutor can then ask **"why was this one rejected?"**, ask for **harder or easier**, ask for a **hint**, or ask for a **worksheet** (a printable page of the practice problems) to download.

---

## How the checker decides

**Built today:** the power-rule derivative checker (`core/derivative_checker.py`). It reads the problem and key with a strict reader, derives the answer with SymPy, and compares on 10 test points that sit off any regular grid (so a key cannot sneak through by matching only at neat numbers). At least 6 points must be usable. A key with the wrong value at any point is rejected, and an unreadable key is refused rather than guessed at.

**Planned, not built:** the integral checker described below. Other topics get their own checker that follows the same idea: recompute the answer independently, then compare. For the integral checker, a problem has to pass **every** test below. Failing any one means rejection.

1. **Safe reading.** The problem and answer are read with a strict grammar and never run as code, so a bad or oversized input cannot break Echo. A check that takes more than 5 seconds hits the timeout and is stopped.
2. **Does the problem make sense?** The formula must work at every number in the domain. A spot where it breaks, like dividing by zero, makes the problem invalid.
3. **Is the answer a real number everywhere?** This is the test from the example above. For an answer with $\ln$ or a square root, the inside part must stay positive (for $\ln$) or non-negative (for a square root) across the whole domain.
4. **Does it undo?** Take the derivative of the answer key. It must give back the original problem. For $\int 2x\cos(x^2)\,dx$ with key $\sin(x^2)$:
$$\frac{d}{dx}\sin(x^2) = 2x\cos(x^2) \quad \checkmark$$
5. **Spot check.** Plug in several test numbers and compare. Two numbers $a$ and $b$ count as equal when they agree to about nine digits, measured relative to their size:
$$|a - b| \le 10^{-9}\cdot\max(|a|,|b|)$$
This is only a safety net. It never *proves* an answer. Proof is always done with exact symbols.
6. **Is it really a substitution problem?** The problem must have a genuine "function inside a function" ($\sin(x+1)$, $(5x+3)^3$) and not just a plain power like $x^2$. The AI must also name the inside part $u = g(x)$ and the outside part $f(u)$, and the checker confirms that putting them together rebuilds the problem.
7. **Does it match the student's problem?** The new problems must have the same *kind* of inside and outside functions as the problem the student missed, the same level, and the same type (definite or indefinite). They must also be different from each other and from the original.

**Definite integrals** get one extra rule. The AI must supply an antiderivative $F$ that passes the tests above. Then the answer must equal $F(\text{upper}) - F(\text{lower})$ exactly. For example:
$$\int_0^1 2x\,dx = F(1) - F(0) = 1 - 0 = 1, \quad F(x) = x^2$$

---

## When things go wrong

Venue wifi is unreliable, so Echo has four fallbacks:

| If this fails | Echo does this instead |
|---|---|
| The photo reader gets the handwriting wrong | The tutor corrects it on the confirm screen |
| Fewer than three AI drafts pass | It fills in from the problem bank and labels where each problem came from. (A template generator was planned; it is not built.) |
| The AI is slow or offline, or there is no API key | A clearly labeled **replay** of a saved run, or the bank problems with their own label |
| The laptop dies | A backup demo video |

The checker runs **on the laptop itself**, so it never depends on the internet.

---

## What we are honest about

- **Answer keys are "computer-checked" only for Echo-checked topics.** That means they passed every test above. It does not mean a human reviewed each one. Every other topic shows bank problems labeled "bank-verified, not Echo-checked" when usable ones exist, and a "not supported yet" message when they do not.
- **Coverage is a measured number.** Before submitting we report how many topics are Echo-checked and how many bank problems they cover, and we say how many bank problems we left out and why (for example, problems that refer to a figure we do not have).
- **Reading a photo can go wrong, and every later step inherits it.** Echo reads handwriting with AI. If a problem or answer is misread, the marks, the skill picture and the recommendations are built on the misreading, and no later check can catch it. The page says so next to every reading. We report the measured reading accuracy on our own test photos, not a promise.
- **Levels were rated by one tutor.** A second rater has not checked them.
- **Hints are written by AI and are not checked.** Only answer keys are.
- **When it was built, and what is reused:** the problem bank, the written plan, and the code were prepared before the event. The checking code in the `app/` folder (the per-topic checkers, the safe math reader, and the sandbox) comes from the author's existing AI math tutor, built earlier. The organizer approved writing code beforehand, as long as the final submission is made before the deadline. What is new for this event is Echo itself: the photo-to-topic flow, the chat, the bank audit and the test gate, and the labeled fallback. The status table below shows what exists right now.
- **Echo covers Calculus I and II only.** It was not tested on other kinds of math.

## What we chose not to build

Level 5, a second difficulty scale, a trained difficulty estimator, extra topics, user accounts, custom PDF code, and voice output. Voice input is a bonus we add only if it works three times in a row.

## What's next

- More subjects where a program can check the answer.
- Remembering each student's recurring mistakes.

---

## Project status

> Last updated 2026-11-12 (Thursday evening). It shows what exists in the repository right now.

| Piece | Status |
|---|---|
| Build plan for Calculus I and II, reviewed and approved by a second AI ([`PLAN.md`](PLAN.md), [`PLAN-REVIEW-LOG.md`](PLAN-REVIEW-LOG.md)) | Done |
| Problem bank ([`docs/verified_problems.json`](docs/verified_problems.json)) | Done |
| Bank audit script | Done. 3,405 of 3,450 level 1 to 4 problems are usable; 88 of 90 topics have at least one |
| Strict input reader and LaTeX reader (`core/`) | Done. Reads 2,537 bank answers correctly and none wrongly; 230 are refused instead of guessed |
| Checkers (one per topic) | **1 of 90 topics Echo-checked: `power_rule`.** Gate result: 40 of 40 problems supported, the checker accepted all 40 bank keys and rejected all 120 deliberately wrong keys |
| Labeled bank fallback | Done. Every other usable topic serves bank problems labeled "bank-verified, not Echo-checked" |
| AI drafting layer | Done and used live once (`claude-sonnet-5-5`, 3 of 5 drafts accepted, all hand-checked). Live, replay and scripted (fake) sources |
| One entry point for the chat (`core/entry.py`) | Done. Falls back to replay or bank with a plain-words note |
| Saved replay | `replay/power_rule_L2.json` is a saved **live** run. `replay/power_rule_L2_fake.json` is **scripted** (made without a model) and is labeled that way |
| Chat and photo upload, photo reading, level check | Not built yet |
| Template generator | Dropped; the bank fills the gap instead |
| Worksheet download, backup video | Not built yet |

What the gate does and does not show: it shows the checker agrees with the bank's keys and rejects corrupted ones. The bank may come from similar checking code, so this is consistency, not independent proof.

### Running it

The API has no login, so run it on localhost only and never expose its port to a network.

You need Python 3.10 or newer. All commands run from this folder. Install the packages first:

```bash
pip install -r requirements-dev.txt       # runtime packages plus pytest (requirements.txt alone skips pytest)
```

The versions are pinned to the ones the tests passed on. A fresh virtual environment with only these packages passes all 560 tests.

```bash
python -m pytest tests -q                 # 560 tests, all offline
python scripts/gate_power_rule.py         # run this first: writes build/gate_power_rule.json
python scripts/demo_wrong_key.py          # accepted key, then a wrong key rejected with numbers
python scripts/demo_fallback.py           # the three labels: Echo-checked, bank, unsupported
python scripts/demo_entry.py --mode replay                            # no key, no internet
python scripts/demo_entry.py --mode bank --topic u_substitution --level 2
python scripts/demo_entry.py --mode fake                              # scripted drafts, no model
```

The `build/` folder is not committed, so the gate script must be run once before the demos. Live mode needs a key: copy `.env.example` to `.env`, fill in `ANTHROPIC_API_KEY`, and run `python scripts/live_smoke.py`. Without a key, live mode falls back to the bank and says so.

---

## Where things are

| Path | What it is |
|---|---|
| [`PLAN.md`](PLAN.md) | The detailed build plan, including every checker rule |
| [`PLAN-REVIEW-LOG.md`](PLAN-REVIEW-LOG.md) | The record of a second AI reviewing the plan and what we changed because of it |
| [`docs/verified_problems.json`](docs/verified_problems.json) | The problem bank: 3,510 problems in 90 calculus topics. Echo uses levels 1 to 4 (3,450 problems), minus any problem that fails our audit |
| [`docs/`](docs/) | Notes on progress, decisions, and known problems |
| [`app/`](app/) | The checking code, reused from the author's existing AI math tutor. It is sorted into `calc1/` (Calculus I), `calc2/` (Calculus II), `shared/` (helpers for both), and `api/` (a web layer Echo does not use). A file-by-file map is in [`docs/app-map.md`](docs/app-map.md) |
| [`core/`](core/) | Echo's own code: strict reader, LaTeX reader, derivative checker, bank fallback, AI drafting layer, and the single entry point (`entry.py`) |
| [`replay/`](replay/) | Saved runs for offline demos (one live, one scripted) |
| [`scripts/`](scripts/) and [`tests/`](tests/) | The audit, gate and demo scripts, and their tests |
| [`CLAUDE.md`](CLAUDE.md) | Instructions for the AI coding assistant used to build this |

### Running with Docker

Docker runs both halves: the API on port 8000 and the page on port 3000. You need Docker with Compose v2.

```bash
docker build -t echo-api .            # API image: installs requirements.txt and runs the gate once
docker build -t echo-ui ui            # page image: builds the Next.js standalone server
docker compose up -d --wait           # starts both and waits for the health checks
```

Then open http://localhost:3000. Stop with `docker compose down`.

**Localhost only.** The API has no authentication and any caller can spend model tokens, so the ports are published on 127.0.0.1 only. Do not expose this stack to a network, and do not change the port mappings to bind to other addresses.

- **Replay is the default.** `ECHO_MODE` defaults to `replay`, so no key and no internet are needed. Drafts come from the saved runs in `replay/`, which are mounted from the host.
- **Live mode needs a key.** Copy `.env.example` to `.env` (git ignores it), set `ANTHROPIC_API_KEY`, and set `ECHO_MODE=live`. Compose reads `.env` at start-up and passes it to the API container at run time only. The key is never written into an image.
- **Saving a live run as a replay.** Set `ECHO_SAVE_REPLAYS=1` in `.env` or the host environment, and run live. Good runs are written into the host's `replay/` folder through the volume mount.
- **The API image runs the gate during the build.** `scripts/gate_power_rule.py` writes `build/gate_power_rule.json` bound to the bank's SHA-256, and the build fails unless it prints `GATE: ENABLED`. Rebuild the API image after any change to `docs/verified_problems.json`.
- The page's browser calls the API at `NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8000`). This is set at build time, so change it with `--build-arg` if the API runs elsewhere.
