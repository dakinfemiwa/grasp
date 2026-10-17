"""LIN-TWO-POINT: build a straight-line model from two data points, use it and judge it.

Edexcel 9MA0 3.1: "Be able to use straight line models in a variety of contexts" (e.g.
converting °C to °F, distance against time for constant speed).

"A journey of 4 miles costs £11 and a journey of 10 miles costs £23. Model the cost, £y, of
a journey of x miles as a linear function. Use your model to estimate the cost of a journey
of 7 miles, and comment on the reliability of your estimate."
Model: m = (23 - 11)/(10 - 4) = 2, c = 3, y = 2x + 3, estimate £17, within the data.

Generation picks the gradient (in tenths), intercept and x-values, then derives the y-values.
x-values are multiples of a step chosen so every y-value is a whole number.
"""

import math
import random
import re
from dataclasses import replace
from string import Formatter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
from app.engine.expr import ExpressionError, compile_relation, proportional2
from app.engine.registry import register
from app.models.enums import StepOutcome

TOLERANCE = 0.01
MAX_Y = 10_000
Reliability = Literal["within the data", "beyond the data"]


def _derived() -> dict[str, bool]:
    return {"derived": True}


class LinearParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    gradient_tenths: int = Field(ge=1, le=500, description="Gradient × 10, so 18 means 1.8.")
    intercept: int = Field(ge=0, le=500, description="y when x = 0.")
    x1: int = Field(ge=0, le=200)
    gap: int = Field(ge=1, le=200, description="x2 - x1.")
    extrapolate: int = Field(ge=0, le=1, description="1: predict beyond the data; 0: within it.")
    x2: int = Field(ge=0, json_schema_extra=_derived())
    x3: int = Field(ge=0, description="Where the prediction is made.", json_schema_extra=_derived())
    y1: int = Field(ge=0, json_schema_extra=_derived())
    y2: int = Field(ge=0, json_schema_extra=_derived())
    y3: int = Field(ge=0, json_schema_extra=_derived())

    @property
    def gradient(self) -> float:
        return self.gradient_tenths / 10

    def y(self, x: int) -> float:
        return self.gradient_tenths * x / 10 + self.intercept


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name}


class LinearSlots(BaseModel):
    """Scenario wording. `data` must use {x1} {y1} {x2} {y2}; `prediction` must use {x3}."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lead_in: str | None = Field(default=None, max_length=200)
    data: str = Field(min_length=1, max_length=300)
    model: str = Field(min_length=1, max_length=200)  # defines x and y, e.g. "Model the cost, £y, ..."
    prediction: str = Field(min_length=1, max_length=200)
    x_unit: str = Field(min_length=1, max_length=20)
    y_unit: str = Field(min_length=1, max_length=20)
    gradient_meaning: str = Field(min_length=1, max_length=80)
    intercept_meaning: str = Field(min_length=1, max_length=80)
    distractor: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def wording_is_well_formed(self) -> "LinearSlots":
        if _placeholders(self.data) != {"x1", "y1", "x2", "y2"}:
            raise ValueError("data must use exactly {x1}, {y1}, {x2} and {y2}")
        if _placeholders(self.prediction) != {"x3"}:
            raise ValueError("prediction must use exactly {x3}")
        if _placeholders(self.model) or _placeholders(self.lead_in or ""):
            raise ValueError("model and lead_in take no placeholders")
        if len({self.gradient_meaning, self.intercept_meaning, self.distractor}) != 3:
            raise ValueError("gradient_meaning, intercept_meaning and distractor must differ")
        return self

    @property
    def meaning_options(self) -> tuple[str, ...]:
        # Sorted, so the correct option's position gives nothing away.
        return tuple(sorted((self.gradient_meaning, self.intercept_meaning, self.distractor)))


class LinearResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    gradient: float | None = None
    equation: str | None = Field(default=None, max_length=120)
    gradient_meaning: str | None = Field(default=None, max_length=80)
    prediction: float | None = None
    reliability: Reliability | None = None


def _num(value: float) -> str:
    """1.8 -> '1.8', 2.0 -> '2'."""
    return f"{value:g}"


def _step(gradient_tenths: int) -> int:
    """Smallest x-step that keeps gradient_tenths * x / 10 a whole number."""
    return 10 // math.gcd(gradient_tenths, 10)


def _aligned(rng: random.Random, lo: int, hi: int, step: int) -> int | None:
    k_lo, k_hi = -(-lo // step), hi // step
    return step * rng.randint(k_lo, k_hi) if k_lo <= k_hi else None


@register
class LinearTwoPoint(QuestionTemplate[LinearParams, LinearSlots, LinearResponse]):
    id = "LIN-TWO-POINT"
    version = 1
    title = "Straight-line model from two data points"
    domain = Domain.LINEAR
    primary_objective = "MOD-05"
    secondary_objectives = ("MOD-07", "MOD-08", "MOD-10")
    spec_refs = ("3.1", "OT3.2", "OT3.3", "OT3.4")
    review_status = ReviewStatus.DRAFT
    params_model = LinearParams
    slots_model = LinearSlots
    response_model = LinearResponse
    default_scenario = "SCN-LIN-TAXI"
    difficulty_notes = "1: whole-number gradient, interpolation. +1 for a decimal gradient, +1 for extrapolation."

    constraints = (
        Constraint("x2_derived", "x2 must equal x1 + gap", lambda p: p.x2 == p.x1 + p.gap),
        Constraint(
            "points_on_line",
            "y1, y2 and y3 must lie on y = mx + c",
            lambda p: all(y == p.y(x) for x, y in ((p.x1, p.y1), (p.x2, p.y2), (p.x3, p.y3))),
        ),
        Constraint(
            "prediction_position",
            "x3 must lie strictly between x1 and x2 for interpolation, or beyond x2 for extrapolation",
            lambda p: p.x3 > p.x2 if p.extrapolate else p.x1 < p.x3 < p.x2,
        ),
        Constraint("y_range", f"y-values must be at most {MAX_Y}", lambda p: max(p.y1, p.y2, p.y3) <= MAX_Y),
    )

    marking_criteria = (
        MarkingCriterion("find_gradient", "MOD-07", "Calculates the gradient from the two data points."),
        MarkingCriterion("form_equation", "MOD-05", "Forms the equation of the line, y = mx + c."),
        MarkingCriterion("interpret_gradient", "MOD-08", "Explains what the gradient means in context."),
        MarkingCriterion("predict", "MOD-07", "Uses the model to make the prediction."),
        MarkingCriterion("judge_reliability", "MOD-10", "Judges reliability: interpolation or extrapolation."),
    )

    response_fields = (
        ResponseField("gradient", "Gradient, m", FieldKind.NUMBER),
        ResponseField("equation", "Equation of the model", FieldKind.EQUATION, help="In x and y, e.g. y = 2x + 3"),
        ResponseField("gradient_meaning", "In context, the gradient represents…", FieldKind.CHOICE),
        ResponseField("prediction", "Estimate", FieldKind.NUMBER),
        ResponseField(
            "reliability",
            "Your estimate is…",
            FieldKind.CHOICE,
            options=("within the data", "beyond the data"),
            help="Is the prediction inside the range of the given data?",
        ),
    )

    hints = (
        Hint("gradient", "MOD-07", "Gradient = change in y ÷ change in x."),
        Hint("intercept", "MOD-05", "Substitute one data point into y = mx + c to find c."),
        Hint("reliability", "MOD-10", "Is the prediction inside the range of x-values you were given?"),
    )

    def fields(self, s: LinearSlots) -> tuple[ResponseField, ...]:
        out = []
        for f in self.response_fields:
            if f.name == "gradient_meaning":
                f = replace(f, options=s.meaning_options)
            elif f.name == "prediction":
                f = replace(f, unit=s.y_unit)
            out.append(f)
        return tuple(out)

    def sample(self, rng: random.Random, bounds: Bounds) -> LinearParams:
        gt = rng.randint(*bounds["gradient_tenths"])
        c = rng.randint(*bounds["intercept"])
        step = _step(gt)
        x1 = _aligned(rng, *bounds["x1"], step)
        gap = _aligned(rng, max(bounds["gap"][0], 2 * step), bounds["gap"][1], step)
        extrapolate = rng.randint(*bounds["extrapolate"])
        if x1 is None or gap is None:  # no aligned values in range: invalid sample, constraints reject it
            x1, gap = bounds["x1"][0], 0
        x2 = x1 + gap
        if extrapolate:
            x3 = x2 + (_aligned(rng, step, max(step, gap), step) or step)
        else:
            x3 = _aligned(rng, x1 + step, x2 - step, step) or x1
        values = {"x1": x1, "x2": x2, "x3": x3}
        ys = {f"y{i}": round(gt * values[f"x{i}"] / 10 + c) for i in (1, 2, 3)}
        return LinearParams(
            gradient_tenths=gt, intercept=c, x1=x1, gap=max(gap, 1), extrapolate=extrapolate, x2=x2, x3=x3, **ys
        )

    def render_prompt(self, p: LinearParams, s: LinearSlots) -> str:
        parts = [
            s.lead_in,
            s.data.format(x1=p.x1, y1=p.y1, x2=p.x2, y2=p.y2),
            s.model,
            s.prediction.format(x3=p.x3) + " Comment on the reliability of your estimate.",
        ]
        return " ".join(part for part in parts if part)

    def _equation_text(self, p: LinearParams) -> str:
        return f"y = {_num(p.gradient)}x" + (f" + {p.intercept}" if p.intercept else "")

    def expected_answer(self, p: LinearParams, s: LinearSlots) -> LinearResponse:
        return LinearResponse(
            gradient=p.gradient,
            equation=self._equation_text(p),
            gradient_meaning=s.gradient_meaning,
            prediction=p.y3,
            reliability="beyond the data" if p.extrapolate else "within the data",
        )

    def worked_solution(self, p: LinearParams, s: LinearSlots) -> list[WorkedStep]:
        m = _num(p.gradient)
        position = "beyond" if p.extrapolate else "within"
        caution = (
            "This is extrapolation: the linear pattern may not continue outside the data, so it is less reliable."
            if p.extrapolate
            else "This is interpolation, so it is reasonably reliable if the relationship is linear."
        )
        return [
            WorkedStep(
                "MOD-07",
                "Find the gradient",
                f"m = ({p.y2} - {p.y1}) ÷ ({p.x2} - {p.x1}) = {p.y2 - p.y1} ÷ {p.gap} = {m}",
            ),
            WorkedStep(
                "MOD-05",
                "Form the model",
                f"{p.y1} = {m} × {p.x1} + c, so c = {p.intercept}. The model is {self._equation_text(p)}.",
            ),
            WorkedStep("MOD-08", "Interpret the gradient", f"The gradient {m} is {s.gradient_meaning} ({s.y_unit} per {s.x_unit})."),
            WorkedStep("MOD-07", "Predict", f"y = {m} × {p.x3} + {p.intercept} = {p.y3} {s.y_unit}"),
            WorkedStep("MOD-10", "Evaluate", f"x = {p.x3} is {position} the data ({p.x1} to {p.x2}). {caution}"),
        ]

    def difficulty(self, p: LinearParams) -> int:
        return 1 + (p.gradient_tenths % 10 != 0) + p.extrapolate

    def mark(self, p: LinearParams, s: LinearSlots, r: LinearResponse) -> list[MarkedStep]:
        steps: list[MarkedStep] = []

        def add(step: str, outcome: StepOutcome, feedback: str) -> None:
            objective = next(c.objective for c in self.marking_criteria if c.step == step)
            steps.append(MarkedStep(step, objective, outcome, feedback))

        # MOD-07: gradient from two points
        if r.gradient is None:
            add("find_gradient", StepOutcome.MISSING, "Calculate the gradient from the two data points.")
        elif math.isclose(r.gradient, p.gradient, abs_tol=TOLERANCE):
            add("find_gradient", StepOutcome.CORRECT, f"Correct: m = {_num(p.gradient)}.")
        elif math.isclose(r.gradient, 1 / p.gradient, abs_tol=TOLERANCE):
            add("find_gradient", StepOutcome.INCORRECT, "Gradient is change in y ÷ change in x, not the other way round.")
        else:
            add("find_gradient", StepOutcome.INCORRECT, "Gradient = change in y ÷ change in x. Check your subtraction.")

        # MOD-05: equation of the line (any rearrangement)
        relation = None
        if not r.equation:
            add("form_equation", StepOutcome.MISSING, "Write the equation of your model in x and y.")
        else:
            try:
                relation = compile_relation(r.equation)
                line = lambda x, y: y - p.gradient * x - p.intercept  # noqa: E731
                if proportional2(relation, line):
                    add("form_equation", StepOutcome.CORRECT, f"Correct: {self._equation_text(p)}.")
                else:
                    add("form_equation", StepOutcome.INCORRECT, "Your equation does not pass through both data points.")
            except ExpressionError as exc:
                add("form_equation", StepOutcome.INCORRECT, str(exc))

        # MOD-08: meaning of the gradient
        if r.gradient_meaning is None:
            add("interpret_gradient", StepOutcome.MISSING, "Say what the gradient represents in this context.")
        elif r.gradient_meaning == s.gradient_meaning:
            add("interpret_gradient", StepOutcome.CORRECT, f"Correct: the gradient is {s.gradient_meaning}.")
        elif r.gradient_meaning == s.intercept_meaning:
            add("interpret_gradient", StepOutcome.INCORRECT, f"That is the intercept: {s.intercept_meaning}.")
        else:
            add("interpret_gradient", StepOutcome.INCORRECT, "The gradient is the rate of change of y with x.")

        # MOD-07: prediction (follow-through from the student's own equation)
        if r.prediction is None:
            add("predict", StepOutcome.MISSING, "Use your model to make the estimate.")
        elif math.isclose(r.prediction, p.y3, abs_tol=TOLERANCE):
            add("predict", StepOutcome.CORRECT, f"Correct: {_num(p.y3)} {s.y_unit}.")
        elif relation is not None and abs(relation(p.x3, r.prediction)) < 1e-6:
            add("predict", StepOutcome.CORRECT, "You used your equation correctly, but the equation itself needs fixing.")
        else:
            add("predict", StepOutcome.INCORRECT, f"Substitute x = {p.x3} into your equation.")

        # MOD-10: reliability
        expected: Reliability = "beyond the data" if p.extrapolate else "within the data"
        if r.reliability is None:
            add("judge_reliability", StepOutcome.MISSING, "Comment on how reliable your estimate is.")
        elif r.reliability == expected:
            add(
                "judge_reliability",
                StepOutcome.CORRECT,
                "Correct: extrapolation is less reliable." if p.extrapolate else "Correct: this is interpolation.",
            )
        else:
            add("judge_reliability", StepOutcome.INCORRECT, f"Compare x = {p.x3} with the data range {p.x1} to {p.x2}.")

        return steps

    def checks(self, p: LinearParams, s: LinearSlots, prompt: str) -> list[ValidationCheck]:
        M, PED, PRES = ValidationCategory.MATHEMATICAL, ValidationCategory.PEDAGOGICAL, ValidationCategory.PRESENTATION
        numbers = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", prompt)}
        given = {float(v) for v in (p.x1, p.y1, p.x2, p.y2, p.x3)}
        static = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", " ".join(filter(None, (s.lead_in, s.model))))}
        full = self.expected_answer(p, s)
        flipped = full.model_copy(
            update={"reliability": "within the data" if p.extrapolate else "beyond the data"}
        )
        reliability_step = next(m for m in self.mark(p, s, flipped) if m.step == "judge_reliability")

        def check(name: str, category: ValidationCategory, passed: bool, message: str) -> ValidationCheck:
            return ValidationCheck(name, category, passed, "" if passed else message)

        return [
            check("distinct_x_values", M, p.x1 < p.x2, "the two data points need different x-values"),
            check(
                "gradient_from_data",
                M,
                math.isclose((p.y2 - p.y1) / (p.x2 - p.x1), p.gradient),
                "the data points do not give the template's gradient",
            ),
            check(
                "reliability_marking_discriminates",
                M,
                reliability_step.outcome is StepOutcome.INCORRECT,
                "the wrong reliability judgement is not marked incorrect",
            ),
            check(
                "given_values_present",
                PRES,
                given <= numbers and numbers <= given | static,
                f"prompt must state the data and prediction point, found {sorted(numbers)}",
            ),
            check(
                "prompt_does_not_reveal_model",
                PED,
                "gradient" not in prompt.lower() and "intercept" not in prompt.lower(),
                "the prompt names the gradient or intercept",
            ),
        ]
