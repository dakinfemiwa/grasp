"""Safe parsing of a student's single-variable expression or equation.

Not a computer algebra system: expressions are compiled to a numeric function of x via a
whitelisted AST, and equivalence is tested by evaluating at fixed sample points. That is
enough to recognise x(x+4)=96, x^2+4x-96=0 and 96=x(x+4) as the same model.
"""

import ast
import math
import re
from collections.abc import Callable

Fn = Callable[[float], float]

MAX_LENGTH = 120
MAX_POWER = 4
# Non-integers, away from any root a template would produce.
SAMPLE_POINTS = (-7.31, -3.17, -0.53, 0.71, 2.39, 5.83, 11.47)

_ALLOWED_CHARS = re.compile(r"[0-9x+\-*/().\s]*")
_IMPLICIT_MULTIPLY = (
    (re.compile(r"(\d)\s*([x(])"), r"\1*\2"),  # 2x, 2(
    (re.compile(r"\)\s*([\dx(])"), r")*\1"),  # )(, )x, )2
    (re.compile(r"x\s*([\dx(])"), r"x*\1"),  # x(, x2
)


class ExpressionError(ValueError):
    pass


def _normalise(text: str) -> str:
    s = text.strip().lower()
    for old, new in (("^", "**"), ("×", "*"), ("·", "*"), ("−", "-"), ("²", "**2"), ("÷", "/")):
        s = s.replace(old, new)
    if not s:
        raise ExpressionError("The expression is empty.")
    if len(s) > MAX_LENGTH:
        raise ExpressionError("The expression is too long.")
    if not _ALLOWED_CHARS.fullmatch(s):
        raise ExpressionError("Use only numbers, x, + - × ÷ ^ and brackets.")
    for pattern, repl in _IMPLICIT_MULTIPLY:
        while (new := pattern.sub(repl, s)) != s:
            s = new
    return s


def _build(node: ast.AST) -> Fn:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        value = float(node.value)
        return lambda _x: value
    if isinstance(node, ast.Name) and node.id == "x":
        return lambda x: x
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        inner = _build(node.operand)
        return (lambda x: -inner(x)) if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp):
        left, right = _build(node.left), _build(node.right)
        match node.op:
            case ast.Add():
                return lambda x: left(x) + right(x)
            case ast.Sub():
                return lambda x: left(x) - right(x)
            case ast.Mult():
                return lambda x: left(x) * right(x)
            case ast.Div():
                return lambda x: left(x) / right(x)
            case ast.Pow():
                exponent = node.right
                if not (isinstance(exponent, ast.Constant) and type(exponent.value) is int):
                    raise ExpressionError("Powers must be whole numbers, e.g. x^2.")
                if not 0 <= exponent.value <= MAX_POWER:
                    raise ExpressionError(f"Powers must be between 0 and {MAX_POWER}.")
                return lambda x: left(x) ** right(x)
    raise ExpressionError("That is not a valid expression in x.")


def compile_expression(text: str) -> Fn:
    try:
        tree = ast.parse(_normalise(text), mode="eval")
    except SyntaxError as exc:
        raise ExpressionError("That expression could not be read. Check the brackets and operators.") from exc
    return _build(tree.body)


def compile_equation(text: str) -> tuple[Fn, Fn]:
    if text.count("=") != 1:
        raise ExpressionError("An equation needs exactly one '=' sign.")
    left, right = text.split("=")
    return compile_expression(left), compile_expression(right)


def _evaluate(f: Fn, x: float) -> float | None:
    try:
        value = f(x)
    except (ZeroDivisionError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def equivalent(f: Fn, g: Fn) -> bool:
    """f(x) == g(x) at every sample point."""
    for x in SAMPLE_POINTS:
        a, b = _evaluate(f, x), _evaluate(g, x)
        if a is None or b is None or not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
            return False
    return True


def proportional(f: Fn, g: Fn) -> bool:
    """f = k·g for one non-zero constant k (the same equation, rearranged or scaled)."""
    ratios = []
    for x in SAMPLE_POINTS:
        a, b = _evaluate(f, x), _evaluate(g, x)
        if a is None or b is None or b == 0:
            return False
        ratios.append(a / b)
    k = ratios[0]
    return abs(k) > 1e-12 and all(math.isclose(r, k, rel_tol=1e-9) for r in ratios)


def satisfies(equation: tuple[Fn, Fn], x: float, tolerance: float = 1e-6) -> bool:
    lhs, rhs = equation
    a, b = _evaluate(lhs, x), _evaluate(rhs, x)
    return a is not None and b is not None and math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
