"""Worksheet wordings of derivative and limit problems read into tasks; anything else is refused."""

import pytest

from core.sympy_task import DERIVATIVE, LIMIT, Task, parse_task


@pytest.mark.parametrize(
    "statement, expected",
    [
        ("Find $f'(x)$ if $f(x) = 3x^4 + 2x - 7$", Task(DERIVATIVE, "3x^4 + 2x - 7", None)),
        ("Find $f'(x)$ for $f(x) = x^{5} - 4x^{2}$.", Task(DERIVATIVE, "x^{5} - 4x^{2}", None)),
        ("Compute $f'(2)$ when $f(x) = x^3 - x$.", Task(DERIVATIVE, "x^3 - x", "2")),
        ("Find the derivative of $f(x) = 5x^3 - x$.", Task(DERIVATIVE, "5x^3 - x", None)),
        ("Find the derivative of $x^2 + 1$.", Task(DERIVATIVE, "x^2 + 1", None)),
        ("Differentiate $f(x) = 4x^3$", Task(DERIVATIVE, "4x^3", None)),
        ("Find $\\frac{dy}{dx}$ if $y = x^4 - 3x$", Task(DERIVATIVE, "x^4 - 3x", None)),
        ("Evaluate $\\lim_{x\\to 3} \\frac{x^2 - 9}{x - 3}$", Task(LIMIT, "\\frac{x^2 - 9}{x - 3}", "3")),
    ],
)
def test_worksheet_wordings_become_tasks(statement: str, expected: Task) -> None:
    assert parse_task(statement) == expected


@pytest.mark.parametrize(
    "statement, expected",
    [
        ("\\text{Find } f'(x) \\text{ if } f(x) = 3x^4 + 2x", Task(DERIVATIVE, "3x^4 + 2x", None)),
        ("\\text{Find } f'(x) \\text{ for } f(x) = x^5 - 4x^2", Task(DERIVATIVE, "x^5 - 4x^2", None)),
        (
            "\\text{Evaluate } \\lim_{x\\to 3} \\frac{x^2 - 9}{x - 3}",
            Task(LIMIT, "\\frac{x^2 - 9}{x - 3}", "3"),
        ),
        ("\\mathrm{Differentiate } f(x) = 4x^3", Task(DERIVATIVE, "4x^3", None)),
    ],
)
def test_text_wrapped_statements_become_tasks(statement: str, expected: Task) -> None:
    assert parse_task(statement) == expected


@pytest.mark.parametrize(
    "statement",
    [
        "Solve $2x + 3 = 7$.",
        "Find the area under $y = x^2$ from 0 to 1.",
        "Integrate $\\int 2x\\,dx$",
        "Find $f'(x)$ if $f(x)$ is the cost of a taxi ride.",
        "",
        None,
    ],
)
def test_other_statements_are_refused(statement: object) -> None:
    assert parse_task(statement) is None
