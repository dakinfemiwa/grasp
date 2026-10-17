"""QUAD-RECT-AREA: construct and solve a quadratic model from a rectangle's dimensions.

"A rectangle has a length 4 cm greater than its width. Its area is 96 cm². Form an equation
that can be used to find its dimensions, and determine the dimensions."
Model: width x, length x + 4, x(x + 4) = 96, x = 8 or x = -12, reject -12, 8 cm by 12 cm.

Generation picks the intended positive width and the difference, then derives the area, so
every instance has a known positive integer solution and a negative root to reject.
"""

import math
import random
import re
from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.catalogue import Domain
from app.engine.base import (
    Bounds,
    Constraint,
    FieldKind,
    Hint,
    MarkedStep,
    MarkingCriterion,
    QuestionTemplate,
    ResponseField,
    ReviewStatus,
    ValidationCategory,
    ValidationCheck,
    WorkedStep,
)
from app.engine.expr import (
    ExpressionError,
    compile_equation,
    compile_expression,
    equivalent,
    proportional,
    satisfies,
)
from app.engine.registry import register
from app.models.enums import StepOutcome

TOLERANCE = 0.01
MAX_AREA = 500
Variable = Literal["width", "length"]


class RectangleParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    width: int = Field(ge=2, le=20, description="Intended positive solution: the rectangle's width.")
    difference: int = Field(ge=1, le=12, description="How much longer the length is than the width.")
    area: int = Field(ge=1, description="Derived: width × (width + difference).", json_schema_extra={"derived": True})

    @property
    def length(self) -> int:
        return self.width + self.difference


class RectangleSlots(BaseModel):
    """Wording a scenario supplies, e.g. subject "A rectangular garden", unit "m"."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1, max_length=80)
    unit: Literal["mm", "cm", "m"]
    lead_in: str | None = Field(default=None, max_length=200)  # optional sentence before the subject


class RectangleResponse(BaseModel):
    """Structured response: each part evidences a different modelling step."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    variable: Variable | None = None
    other_side: str | None = Field(default=None, max_length=120)
    equation: str | None = Field(default=None, max_length=120)
    roots: list[float] | None = Field(default=None, max_length=4)
    width: float | None = None
    length: float | None = None


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=TOLERANCE)


def _same_roots(given: list[float], expected: tuple[float, float]) -> bool:
    return len(given) == 2 and all(_close(g, e) for g, e in zip(sorted(given), sorted(expected), strict=True))


def _signed(n: int) -> str:
    return f"+ {n}" if n >= 0 else f"- {-n}"


@register
class QuadraticRectangleArea(QuestionTemplate[RectangleParams, RectangleSlots, RectangleResponse]):
    id = "QUAD-RECT-AREA"
    version = 1
    title = "Rectangle dimensions from area"
    domain = Domain.QUADRATIC
    primary_objective = "MOD-05"
    secondary_objectives = ("MOD-02", "MOD-07", "MOD-09", "MOD-08")
    spec_refs = ("2.3", "OT3.1", "OT2.3")
    # Authored by the engine developer; needs a teacher's review before it is APPROVED.
    review_status = ReviewStatus.DRAFT
    params_model = RectangleParams
    slots_model = RectangleSlots
    response_model = RectangleResponse
    default_scenario = "SCN-RECT-ABSTRACT"
    difficulty_notes = "Difficulty grows with the area: ≤100 → 1, ≤250 → 2, otherwise 3."

    constraints = (
        Constraint(
            "area_derived",
            "area must equal width × (width + difference)",
            lambda p: p.area == p.width * (p.width + p.difference),
        ),
        Constraint("area_range", f"area must be at most {MAX_AREA}", lambda p: p.area <= MAX_AREA),
    )

    marking_criteria = (
        MarkingCriterion("define_variables", "MOD-02", "States what x represents and writes the other side in terms of x."),
        MarkingCriterion("form_equation", "MOD-05", "Forms an equation equivalent to width × length = area."),
        MarkingCriterion("solve", "MOD-07", "Finds both solutions of the equation."),
        MarkingCriterion("reject_invalid_root", "MOD-09", "Rejects the negative solution as a physical dimension."),
        MarkingCriterion("interpret_dimensions", "MOD-08", "States the width and length in context."),
    )

    response_fields = (
        ResponseField("variable", "Let x be the…", FieldKind.CHOICE, options=("width", "length")),
        ResponseField("other_side", "The other side, in terms of x", FieldKind.EXPRESSION, help="e.g. x + 3"),
        ResponseField("equation", "Equation", FieldKind.EQUATION, help="Use x, e.g. x(x + 3) = 40"),
        ResponseField("roots", "Solutions of your equation", FieldKind.NUMBER_LIST, help="Give every solution"),
        ResponseField("width", "Width", FieldKind.NUMBER),
        ResponseField("length", "Length", FieldKind.NUMBER),
    )

    hints = (
        Hint("variables", "MOD-02", "Call one side x. How much longer or shorter is the other side?"),
        Hint("area", "MOD-05", "The area of a rectangle is width × length."),
        Hint("solve", "MOD-07", "Rearrange so that one side is 0, then factorise."),
    )

    def fields(self, s: RectangleSlots) -> tuple[ResponseField, ...]:
        with_unit = {"other_side", "width", "length"}
        return tuple(replace(f, unit=s.unit) if f.name in with_unit else f for f in self.response_fields)

    def sample(self, rng: random.Random, bounds: Bounds) -> RectangleParams:
        width = rng.randint(*bounds["width"])
        difference = rng.randint(*bounds["difference"])
        return RectangleParams(width=width, difference=difference, area=width * (width + difference))

    def render_prompt(self, p: RectangleParams, s: RectangleSlots) -> str:
        lead_in = f"{s.lead_in} " if s.lead_in else ""
        return (
            f"{lead_in}{s.subject} has a length that is {p.difference} {s.unit} greater than its width. "
            f"Its area is {p.area} {s.unit}². "
            "Form an equation that can be used to find its dimensions, and determine the dimensions."
        )

    def expected_answer(self, p: RectangleParams, s: RectangleSlots) -> RectangleResponse:
        return RectangleResponse(
            variable="width",
            other_side=f"x + {p.difference}",
            equation=f"x(x + {p.difference}) = {p.area}",
            roots=[p.width, -p.length],
            width=p.width,
            length=p.length,
        )

    def worked_solution(self, p: RectangleParams, s: RectangleSlots) -> list[WorkedStep]:
        w, d, a, length = p.width, p.difference, p.area, p.length
        return [
            WorkedStep("MOD-02", "Define the variables", f"Let the width be x {s.unit}. Then the length is (x + {d}) {s.unit}."),
            WorkedStep(
                "MOD-05",
                "Form the equation",
                f"Area = width × length, so x(x + {d}) = {a}, which rearranges to x² {_signed(d)}x - {a} = 0.",
            ),
            WorkedStep("MOD-07", "Solve", f"(x - {w})(x + {length}) = 0, so x = {w} or x = -{length}."),
            WorkedStep("MOD-09", "Reject the invalid solution", f"A width cannot be negative, so reject x = -{length}."),
            WorkedStep("MOD-08", "Interpret", f"The width is {w} {s.unit} and the length is {length} {s.unit}."),
            WorkedStep(
                "MOD-09",
                "Check against the original conditions",
                f"{length} - {w} = {d} ✓ and {w} × {length} = {a} ✓",
            ),
        ]

    def difficulty(self, p: RectangleParams) -> int:
        return 1 if p.area <= 100 else 2 if p.area <= 250 else 3

    # --- marking -----------------------------------------------------------------------

    def _model(self, p: RectangleParams, variable: Variable) -> tuple[float, float]:
        """(shift, area) such that the model is x(x + shift) = area for that choice of x."""
        return (p.difference if variable == "width" else -p.difference), p.area

    def _roots(self, p: RectangleParams, variable: Variable) -> tuple[float, float]:
        return (p.width, -p.length) if variable == "width" else (p.length, -p.width)

    def mark(self, p: RectangleParams, s: RectangleSlots, r: RectangleResponse) -> list[MarkedStep]:
        steps: list[MarkedStep] = []
        candidates: list[Variable] = [r.variable] if r.variable else ["width", "length"]

        def add(step: str, outcome: StepOutcome, feedback: str) -> None:
            objective = next(c.objective for c in self.marking_criteria if c.step == step)
            steps.append(MarkedStep(step, objective, outcome, feedback))

        # MOD-02: define variables
        if r.variable is None or not r.other_side:
            add("define_variables", StepOutcome.MISSING, "Say what x represents and write the other side in terms of x.")
        else:
            other = "length" if r.variable == "width" else "width"
            shift, _ = self._model(p, r.variable)
            try:
                ok = equivalent(compile_expression(r.other_side), lambda x: x + shift)
                feedback = (
                    f"Correct: if x is the {r.variable}, the {other} is x {_signed(int(shift))}."
                    if ok
                    else f"If x is the {r.variable}, how does the {other} compare? Use the {p.difference} {s.unit} difference."
                )
            except ExpressionError as exc:
                ok, feedback = False, str(exc)
            add("define_variables", StepOutcome.CORRECT if ok else StepOutcome.INCORRECT, feedback)

        # MOD-05: form the equation
        equation = None
        model_variable: Variable | None = None
        if not r.equation:
            add("form_equation", StepOutcome.MISSING, "Write an equation in x that the dimensions satisfy.")
        else:
            try:
                equation = compile_equation(r.equation)
                lhs, rhs = equation
                for v in candidates:
                    shift, area = self._model(p, v)
                    if proportional(lambda x: lhs(x) - rhs(x), lambda x, k=shift, a=area: x * (x + k) - a):
                        model_variable = v
                        break
                if model_variable:
                    add("form_equation", StepOutcome.CORRECT, "Correct: your equation represents width × length = area.")
                else:
                    add("form_equation", StepOutcome.INCORRECT, "Your equation does not represent width × length = area.")
            except ExpressionError as exc:
                add("form_equation", StepOutcome.INCORRECT, str(exc))

        # MOD-07: solve (follow-through: a correctly solved wrong equation still earns this step)
        if not r.roots:
            add("solve", StepOutcome.MISSING, "Give the solutions of your equation.")
        elif model_variable and _same_roots(r.roots, self._roots(p, model_variable)):
            add("solve", StepOutcome.CORRECT, "Correct: both solutions found.")
        elif equation and not model_variable and len(r.roots) == 2 and not _close(*r.roots) and all(
            satisfies(equation, x) for x in r.roots
        ):
            add("solve", StepOutcome.CORRECT, "You solved your equation correctly, but the equation itself needs fixing.")
        elif model_variable and len(r.roots) == 1 and any(_close(r.roots[0], x) for x in self._roots(p, model_variable)):
            add("solve", StepOutcome.INCORRECT, "This quadratic has two solutions. Find both before deciding which is valid.")
        else:
            add("solve", StepOutcome.INCORRECT, "These are not the solutions. Check by substituting them into your equation.")

        # MOD-09: reject the negative root
        if r.width is None or r.length is None:
            add("reject_invalid_root", StepOutcome.MISSING, "Give the width and the length.")
        elif r.width <= 0 or r.length <= 0:
            add(
                "reject_invalid_root",
                StepOutcome.INCORRECT,
                "A length or width cannot be negative or zero: reject the negative solution.",
            )
        else:
            add("reject_invalid_root", StepOutcome.CORRECT, "Correct: the negative solution is not a valid dimension.")

        # MOD-08: interpret in context
        if r.width is None or r.length is None:
            add("interpret_dimensions", StepOutcome.MISSING, "State the width and length of the rectangle.")
        elif _close(r.width, p.width) and _close(r.length, p.length):
            add("interpret_dimensions", StepOutcome.CORRECT, f"Correct: {p.width} {s.unit} by {p.length} {s.unit}.")
        elif _close(r.width, p.length) and _close(r.length, p.width):
            add("interpret_dimensions", StepOutcome.INCORRECT, "You have swapped them: the length is the longer side.")
        else:
            add(
                "interpret_dimensions",
                StepOutcome.INCORRECT,
                f"Check: the length should be {p.difference} {s.unit} more than the width, "
                f"and width × length should be {p.area} {s.unit}².",
            )

        return steps

    # --- template-specific validation ----------------------------------------------------

    def checks(self, p: RectangleParams, s: RectangleSlots, prompt: str) -> list[ValidationCheck]:
        M, PED, PRES = ValidationCategory.MATHEMATICAL, ValidationCategory.PEDAGOGICAL, ValidationCategory.PRESENTATION
        answer = self.expected_answer(p, s)
        assert answer.width is not None and answer.length is not None
        model = (lambda x: x * (x + p.difference), lambda _x: float(p.area))
        negative = -p.length
        marked_negative = self.mark(p, s, answer.model_copy(update={"width": float(negative)}))
        reject_step = next(m for m in marked_negative if m.step == "reject_invalid_root")
        numbers = {int(n) for n in re.findall(r"\d+", prompt.replace("²", ""))}

        def check(name: str, category: ValidationCategory, passed: bool, message: str) -> ValidationCheck:
            return ValidationCheck(name, category, passed, "" if passed else message)

        return [
            check("positive_solution_exists", M, p.width > 0 and satisfies(model, p.width), "no positive solution"),
            check(
                "answer_satisfies_conditions",
                M,
                answer.width * answer.length == p.area and answer.length - answer.width == p.difference,
                "expected dimensions do not satisfy the given area and difference",
            ),
            check(
                "extraneous_root_rejected",
                M,
                negative < 0 and satisfies(model, negative) and reject_step.outcome is StepOutcome.INCORRECT,
                "the negative root is not rejected by marking",
            ),
            check(
                "units_consistent",
                M,
                f"{p.difference} {s.unit} " in prompt and f"{p.area} {s.unit}²" in prompt,
                f"lengths must be in {s.unit} and the area in {s.unit}²",
            ),
            check(
                "given_values_present",
                PRES,
                numbers == {p.difference, p.area},
                f"prompt must state exactly the difference and the area, found {sorted(numbers)}",
            ),
            check(
                "prompt_does_not_reveal_model",
                PED,
                re.search(r"\bx\b", prompt) is None and numbers <= {p.difference, p.area},
                "the prompt names the variable or states a solution",
            ),
        ]
