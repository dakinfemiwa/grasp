"""Safe parsing of a student's expression, equation or two-variable relation.

Not a computer algebra system: input is tokenised against a whitelist (numbers, the allowed
variable letters, + - * / ^ and brackets), implicit multiplication is made explicit, and the
result is compiled to a numeric function via a whitelisted AST. Equivalence is tested by
evaluating at fixed sample points. That is enough to recognise x(x+4)=96, x^2+4x-96=0 and
96=x(x+4) as one model, or y = 2x + 3 and 2x - y + 3 = 0 as one line.
"""

import ast
import math
import re
from collections.abc import Callable, Sequence

Fn = Callable[[float], float]
Fn2 = Callable[[float, float], float]
_EnvFn = Callable[[dict[str, float]], float]

MAX_LENGTH = 120
MAX_POWER = 4
# Non-integers, away from any root a template would produce.
SAMPLE_POINTS = (-7.31, -3.17, -0.53, 0.71, 2.39, 5.83, 11.47)

_ALLOWED_CHARS = re.compile(r"[0-9a-z+\-*/().\s]*")
_TOKEN = re.compile(r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<name>[a-z]+)|(?P<op>\*\*|[-+*/()]))")


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
        raise ExpressionError("Use only numbers, the variables, + - × ÷ ^ and brackets.")
    return s


def _split_name(word: str, variables: Sequence[str]) -> list[tuple[str, str]]:
    """'xx' -> x, x. Anything that is not an allowed variable letter is rejected."""
    out = []
    for ch in word:
        if ch not in variables:
            raise ExpressionError(f"Unknown name '{word}'. Use only {', '.join(variables)}.")
        out.append(("var", ch))
    return out


def _tokenise(s: str, variables: Sequence[str]) -> str:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if m is None or m.end() == pos:
            raise ExpressionError("That expression could not be read. Check the brackets and operators.")
        pos = m.end()
        if m["num"]:
            tokens.append(("num", m["num"]))
        elif m["name"]:
            tokens.extend(_split_name(m["name"], variables))
        else:
            tokens.append(("op", m["op"]))
    # Implicit multiplication: 2x, 2(, x(, )(, )x, x2.
    out: list[str] = []
    for i, (kind, text) in enumerate(tokens):
        if i:
            prev_kind, prev_text = tokens[i - 1]
            ends_value = prev_kind in ("num", "var") or prev_text == ")"
            starts_value = kind in ("num", "var") or text == "("
            if ends_value and starts_value:
                out.append("*")
        out.append(text)
    return " ".join(out)


def _build(node: ast.AST) -> _EnvFn:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        value = float(node.value)
        return lambda _env: value
    if isinstance(node, ast.Name):
        name = node.id
        return lambda env: env[name]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        inner = _build(node.operand)
        return (lambda env: -inner(env)) if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp):
        left, right = _build(node.left), _build(node.right)
        match node.op:
            case ast.Add():
                return lambda env: left(env) + right(env)
            case ast.Sub():
                return lambda env: left(env) - right(env)
            case ast.Mult():
                return lambda env: left(env) * right(env)
            case ast.Div():
                return lambda env: left(env) / right(env)
            case ast.Pow():
                exponent = node.right
                if not (isinstance(exponent, ast.Constant) and type(exponent.value) is int):
                    raise ExpressionError("Powers must be whole numbers, e.g. x^2.")
                if not 0 <= exponent.value <= MAX_POWER:
                    raise ExpressionError(f"Powers must be between 0 and {MAX_POWER}.")
                return lambda env: left(env) ** right(env)
    raise ExpressionError("That is not a valid expression.")


def _compile(text: str, variables: Sequence[str]) -> _EnvFn:
    source = _tokenise(_normalise(text), variables)
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError("That expression could not be read. Check the brackets and operators.") from exc
    return _build(tree.body)


def _sides(text: str) -> tuple[str, str]:
    if text.count("=") != 1:
        raise ExpressionError("An equation needs exactly one '=' sign.")
    left, right = text.split("=")
    return left, right


def compile_expression(text: str, variable: str = "x") -> Fn:
    f = _compile(text, (variable,))
    return lambda v: f({variable: v})


def compile_equation(text: str, variable: str = "x") -> tuple[Fn, Fn]:
    left, right = _sides(text)
    return compile_expression(left, variable), compile_expression(right, variable)


def compile_relation(text: str, variables: tuple[str, str] = ("x", "y")) -> Fn2:
    """An equation in two variables, as g(a, b) = lhs - rhs (zero exactly on the relation)."""
    left, right = _sides(text)
    lhs, rhs = _compile(left, variables), _compile(right, variables)
    a, b = variables
    return lambda u, v: lhs({a: u, b: v}) - rhs({a: u, b: v})


def _evaluate(f: Callable[..., float], *args: float) -> float | None:
    try:
        value = f(*args)
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


def _constant_ratio(pairs: list[tuple[float | None, float | None]]) -> bool:
    ratios = []
    for a, b in pairs:
        if a is None or b is None or b == 0:
            return False
        ratios.append(a / b)
    k = ratios[0]
    return abs(k) > 1e-12 and all(math.isclose(r, k, rel_tol=1e-9) for r in ratios)


def proportional(f: Fn, g: Fn) -> bool:
    """f = k·g for one non-zero constant k (the same equation, rearranged or scaled)."""
    return _constant_ratio([(_evaluate(f, x), _evaluate(g, x)) for x in SAMPLE_POINTS])


def proportional2(f: Fn2, g: Fn2) -> bool:
    """Two-variable version of proportional, over a grid of sample pairs."""
    pairs = [(u, v) for u in SAMPLE_POINTS[::2] for v in SAMPLE_POINTS[1::2]]
    return _constant_ratio([(_evaluate(f, u, v), _evaluate(g, u, v)) for u, v in pairs])


def satisfies(equation: tuple[Fn, Fn], x: float, tolerance: float = 1e-6) -> bool:
    lhs, rhs = equation
    a, b = _evaluate(lhs, x), _evaluate(rhs, x)
    return a is not None and b is not None and math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
