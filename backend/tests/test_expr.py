import pytest

from app.engine.expr import (
    ExpressionError,
    compile_equation,
    compile_expression,
    equivalent,
    proportional,
    satisfies,
)


@pytest.mark.parametrize(
    ("text", "x", "expected"),
    [
        ("x + 4", 2, 6),
        ("2x", 3, 6),
        ("x(x+4)", 8, 96),
        ("(x - 8)(x + 12)", 8, 0),
        ("x^2 + 4x - 96", 8, 0),
        ("x²", 3, 9),
        ("3 × x", 2, 6),
        ("−x", 2, -2),
        ("x / 2", 3, 1.5),
        ("2(x)(x)", 3, 18),
    ],
)
def test_compiles_and_evaluates(text: str, x: float, expected: float) -> None:
    assert compile_expression(text)(x) == pytest.approx(expected)


@pytest.mark.parametrize(
    "text",
    ["", "y + 1", "__import__('os')", "x.real", "abs(x)", "x ** x", "x ^ 9", "x ^ 0.5", "1e9", "(x + 1", "x" * 200],
)
def test_rejects_unsafe_or_invalid(text: str) -> None:
    with pytest.raises(ExpressionError):
        compile_expression(text)


@pytest.mark.parametrize("text", ["x + 1", "x = 1 = 2"])
def test_equation_needs_exactly_one_equals(text: str) -> None:
    with pytest.raises(ExpressionError):
        compile_equation(text)


def test_equivalence_and_proportionality() -> None:
    assert equivalent(compile_expression("x(x+4)"), compile_expression("x^2 + 4x"))
    assert not equivalent(compile_expression("x(x+4)"), compile_expression("x^2 + 4"))
    lhs, rhs = compile_equation("96 = x(x + 4)")
    target = compile_expression("x^2 + 4x - 96")
    assert proportional(lambda x: lhs(x) - rhs(x), target)  # k = -1
    assert not proportional(compile_expression("x + 4"), target)
    assert not proportional(compile_expression("0"), target)


def test_satisfies_tolerates_rounding_but_not_errors() -> None:
    equation = compile_equation("x(x + 4) = 96")
    assert satisfies(equation, 8) and satisfies(equation, -12)
    assert not satisfies(equation, 9)
    assert not satisfies(compile_equation("1/x = 1"), 0)  # division by zero is just "no"
