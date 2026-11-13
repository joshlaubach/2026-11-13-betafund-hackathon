# Review of the SymPy-first grading code (2026-11-12)

Independent read-only review by Codex. Codex could not run Python, so its findings were traced by reading code. The orchestrator then reproduced each finding with the test helpers (`tests/test_worksheet_shapes.py::_grade_one`).

## Orchestrator triage

| # | Finding | Reproduced? | Decision |
|---|---|---|---|
| 1 | A definition's domain restriction ("for x>0") is dropped, so f'(-1) is marked correct | **Yes** (correct, sympy_computed) | Fix: fall through to the AI path when a definition carries a restriction |
| 2 | A second math ask joined by "and state ..." is stripped as a writing instruction, so an answer missing it is marked correct | **Yes** | Fix: only strip genuine writing asks; a clause with math falls through to the AI path |
| 3 | Bank match ignores the item's shared context | Not reproduced (needs a context-dependent bank entry; bank statements are self-contained) | Low risk, note only |
| 4 | A contradictory chain `dy/dx = 100 = 1/2` is accepted via its last segment | **Yes** | Fix: a chain whose segments disagree is unsure |
| 5 | Limit certified across a domain hole (`x*sqrt(x^2-1e-14)`) | Contrived | Skip |
| 6 | Antiderivative off by 1e-13 passes the tolerance | Contrived | Skip |
| 7 | Tangent-line equation with a 1e-13 extra factor passes | Contrived | Skip |
| 8 | A decimal (`3.14159265359`) is correct when "exact" was asked | **Yes** (correct, sympy_computed) | Fix: exact ask plus a decimal student answer is unsure |
| 9 | `x^3` increasing: `(-inf, inf)` vs the union around 0 | Not reproduced as stated (the answer came back unsure, AI judgment, because the interval was not read) | Note only; revisit if time |
| 10 | Cusp horizontal tangent at (0,0) | **Yes** (marked incorrect against the empty set) | Rare; note only |
| 11 | `1e-3` read as e - 3 | **Yes** (marked incorrect) | Rare in handwriting; note only |
| 12 | Non-real interval endpoint `(sqrt(-1), 1)` raises an exception | **Yes** (ValueError escapes) | Fix: catch it and return unreadable |
| 13 | A contradictory AI reply (`0=1`) still counts as agreement | Not reproduced separately | Note only |

## Codex report (verbatim)

# SymPy-first grading bug report

**Verification:** These findings are traced through the exact code paths. Python was unavailable in this environment, so the stated outcomes are **runtime unverified**. No files were changed, no network service was called, and the test suite was not run.

## CRITICAL — false verified correct

1. **A domain restriction is discarded.** [definitions.py:64](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/definitions.py:64>) trims the definition before “for,” and [sympy_task.py:150](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/sympy_task.py:150>) then differentiates it without the restriction. Context: `f(x)=x^2 for x>0.` Statement: `Find f'(-1).` Student: `-2`. **Code result:** `correct`, `sympy_computed`. **Correct:** \(f'(-1)\) is undefined because \(-1\) is outside the stated domain.

2. **A second mathematical request is treated as a writing instruction and removed.** [definitions.py:20](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/definitions.py:20>) and [sympy_task.py:227](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/sympy_task.py:227>) drop everything from “and state.” Statement: `Find f'(x) for f(x) = x^2 and state where f'(x) > 0.` Student: `2x`. **Code result:** `correct`, `sympy_computed`, for the derivative alone. **Correct:** The answer omits the requested region \(x>0\).

3. **Bank matching ignores the problem’s shared context.** [worksheet.py:386](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/worksheet.py:386>) matches only `statement_latex`; [worksheet.py:432](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/worksheet.py:432>) then grades against that bank key. Reproduction input: `WorksheetItem(number=1, statement_latex="Find f'(0).", context_latex="f(x)=x^2.", student_answer_latex="1")`, with a supplied bank entry `{"id":"1","topic":"derivatives","statement":"Find f'(0).","answer":{"latex":"1"}}`. **Code result:** `correct`, `bank_key`. **Correct:** For the item’s function, \(f'(0)=0\). This path requires a context-dependent entry in the supplied bank.

4. **A contradictory slope equation is accepted by reading only its last segment.** [equations.py:471](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/equations.py:471>) uses `rsplit("=", 1)[-1]`. Context: `y^2=x.` Statement: `Find the slope of the tangent at (1,1).` Student: `dy/dx = 100 = 1/2`. **Code result:** `correct`, `sympy_computed`, because only `1/2` is compared. **Correct:** The submitted chain asserts the false equality \(100=1/2\).

5. **A real limit is certified across a hole in its domain.** [sympy_task.py:284](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/sympy_task.py:284>) probes only \(0\pm10^{-6}\) before accepting SymPy’s two-sided limit. Statement: `\lim_{x\to 0} x\sqrt{x^2-0.00000000000001}`. Student: `0`. **Code-traced result:** `correct`, `sympy_computed`: both probes are real and the computed expression tends to zero. **Correct:** As a real function it has no domain points within \(10^{-7}\) of zero, so zero is not an accumulation point of its domain and the requested real limit is undefined. The SymPy limit step is runtime unverified.

6. **A wrong antiderivative passes the derivative tolerance at every sample.** [antiderivatives.py:120](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/antiderivatives.py:120>) and [antiderivatives.py:143](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/antiderivatives.py:143>) use numerical closeness as correctness. Statement: `Find \int x dx`. Student: `\frac{x^2}{2}+10^{-13}x+C`. **Code result:** `correct`, `sympy_computed`; its derivative differs from \(x\) by only \(10^{-13}\) at all fixed samples. **Correct:** Its derivative is \(x+10^{-13}\), so it is not an antiderivative of \(x\).

7. **An equation with an extra line is accepted as the tangent line.** [equations.py:232](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/equations.py:232>) tests approximate proportionality at bounded sample points. Context: `f(x)=x.` Statement: `Write the equation of the tangent line to f at x = 0.` Student: `(y-x)(1+10^{-13}x)=0`. **Code result:** `correct`, `sympy_computed`; the extra factor differs from 1 by less than the comparison tolerance at every sample. **Correct:** The equation also contains the vertical line \(x=-10^{13}\), so it is not the tangent line \(y=x\).

8. **A decimal earns “correct” despite an explicit exact-answer request.** [solvers.py:450](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/solvers.py:450>) accepts close constants, and [sympy_task.py:401](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/sympy_task.py:401>) considers rounding only after a `DIFFERENT` comparison. Statement: `Find $f'(0)$ for $f(x) = \pi x$. Give an exact answer.` Student: `3.14159265359`. **Code result:** `correct`, `sympy_computed`. **Correct:** The requested exact answer is \(\pi\); the decimal is an approximation.

## HIGH — false incorrect

9. **Increasing \(x^3\) is treated as two intervals with a missing point.** [solution_sets.py:108](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/solution_sets.py:108>) equates “increasing” with \(f'(x)>0\). Context: `f(x)=x^3.` Statement: `On what intervals is f increasing?` Student: `(-\infty,\infty)`. **Code result:** `incorrect`, `sympy_computed`, against \((-\infty,0)\cup(0,\infty)\). **Correct:** \(x^3\) is strictly increasing on all real numbers, including across its stationary point at zero.

10. **A cusp’s horizontal tangent is excluded because both implicit-derivative parts vanish.** [equations.py:413](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/equations.py:413>) and [equations.py:428](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/equations.py:428>) discard a candidate when the denominator is zero. Context: `The curve is given by y^2=x^3.` Statement: `Find all points where the tangent is horizontal.` Student: `(0,0)`. **Code-traced result:** `incorrect`, `sympy_computed`, against the empty set. **Correct:** The cusp at \((0,0)\) has horizontal tangent \(y=0\).

11. **Scientific notation is parsed as arithmetic with Euler’s number.** [latex_reader.py:129](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/latex_reader.py:129>) tokenizes `1e-3` as `1`, `e`, `-`, `3`, which the expression reader treats as \(e-3\). Statement: `Find $f'(0)$ for $f(x) = 0.001x$.` Student: `1e-3`. **Code result:** `incorrect`, `sympy_computed`. **Correct:** In standard scientific notation, `1e-3` is \(0.001\).

## MEDIUM — crash or misleading evidence

12. **A nonreal interval endpoint can escape the student-answer reader as an exception.** [solution_sets.py:125](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/solution_sets.py:125>) accepts any symbol-free expression as an endpoint, and [solution_sets.py:143](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/solution_sets.py:143>) constructs a SymPy interval without catching endpoint errors. For a set question such as `Solve x=1`, submit `(\sqrt{-1},1)`. **Code-traced result:** `sp.Interval(I, 1)` is attempted and its construction error propagates instead of producing a mark. **Correct behavior:** Return an unreadable or unsure result. The exception from this SymPy version is runtime unverified.

13. **The “independent AI solve agreed” claim can rest on one side of a contradictory reply.** [sympy_task.py:510](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/sympy_task.py:510>) tries equality-separated reply segments last-first, and [sympy_task.py:533](<C:/Users/joshu/Documents/VS Code/math-problem-generator/echo/core/sympy_task.py:533>) labels a match as agreement. Statement: `Find $f'(0)$ for $f(x) = x$.` Student: `1`; a `FakeSolver` cross-check reply of `0=1`. **Code result:** The mark remains `correct`, `sympy_computed`, with “An independent AI solve agreed with SymPy’s answer.” **Correct evidence label:** The reply is internally contradictory; matching its final `1` does not establish that the solve agreed.