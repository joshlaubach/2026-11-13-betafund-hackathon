# Echo

**Echo turns a photo of a math problem a student got wrong into up to three fresh practice problems of the same kind. A math program checks every AI-written problem before a tutor sees it. Where we have no checker yet, Echo shows verified problems from a prepared bank and labels them clearly.**

---

## The problem, in plain words

A tutor sits with a student who just missed a problem. The best next step is to practice the *same kind* of problem a few more times. Making those up by hand takes time. Asking an AI is fast, but AI sometimes writes problems with **wrong answers**, and a tutor who hands a student a wrong answer does real damage.

Echo keeps the speed of AI and removes the risk: **no AI-written problem reaches the tutor unless the checker has proven its answer is right.** Problems that did not come from the AI come from a bank of problems verified earlier, and they are labeled so the tutor always knows which kind they are looking at.

---

## The math in one minute

Echo covers **Calculus I and II**. The examples below use integration by substitution, one Calculus I topic, because it is the first and deepest checker we are building.

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

Here is a real example of the kind of mistake it catches. The problem is:

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

This describes the checker for integrals, the first one built. Other topics get their own checker that follows the same idea: recompute the answer independently, then compare. A problem has to pass **every** test below. Failing any one means rejection.

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
| Fewer than three AI drafts pass | It fills in from the problem bank, then from the template generator, and labels where each problem came from |
| The AI is slow or offline | A clearly labeled **replay** of a saved run, plus the template generator, which works offline |
| The laptop dies | A backup demo video |

The checker runs **on the laptop itself**, so it never depends on the internet.

---

## What we are honest about

- **Answer keys are "computer-checked" only for Echo-checked topics.** That means they passed every test above. It does not mean a human reviewed each one. Every other topic shows bank problems labeled "bank-verified, not Echo-checked" when usable ones exist, and a "not supported yet" message when they do not.
- **Coverage is a measured number.** Before submitting we report how many topics are Echo-checked and how many bank problems they cover, and we say how many bank problems we left out and why (for example, problems that refer to a figure we do not have).
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

> **Update this table before submitting.** It shows what exists in the repository right now.

| Piece | Status |
|---|---|
| Build plan for Calculus I and II, reviewed and approved by a second AI ([`PLAN.md`](PLAN.md), [`PLAN-REVIEW-LOG.md`](PLAN-REVIEW-LOG.md)) | Done |
| Problem bank ([`docs/verified_problems.json`](docs/verified_problems.json)) | Done |
| Bank audit and test scripts | Not built yet |
| Checkers (one per topic) | Not built yet. Topics checked so far: 0 (the audit script will report how many topics are usable) |
| Chat and photo upload | Not built yet |
| Template generator | Not built yet |
| Worksheet download | Not built yet |
| Saved replay and backup video | Not made yet |

### Running it

Run instructions will be added here when the app exists.

---

## Where things are

| Path | What it is |
|---|---|
| [`PLAN.md`](PLAN.md) | The detailed build plan, including every checker rule |
| [`PLAN-REVIEW-LOG.md`](PLAN-REVIEW-LOG.md) | The record of a second AI reviewing the plan and what we changed because of it |
| [`docs/verified_problems.json`](docs/verified_problems.json) | The problem bank: 3,510 problems in 90 calculus topics. Echo uses levels 1 to 4 (3,450 problems), minus any problem that fails our audit |
| [`docs/`](docs/) | Notes on progress, decisions, and known problems |
| [`app/`](app/) | The checking code, reused from the author's existing AI math tutor. It is sorted into `calc1/` (Calculus I), `calc2/` (Calculus II), `shared/` (helpers for both), and `api/` (a web layer Echo does not use). A file-by-file map is in [`docs/app-map.md`](docs/app-map.md) |
| [`scripts/`](scripts/) and [`tests/`](tests/) | The bank audit script and its tests |
| [`CLAUDE.md`](CLAUDE.md) | Instructions for the AI coding assistant used to build this |
