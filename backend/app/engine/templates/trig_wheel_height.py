"""TRIG-WHEEL-HEIGHT: model the height of a point on a rotating wheel and solve for times.

Edexcel 9MA0 5.9: "Use trigonometric functions to solve problems in context ... the height of
a point on a vertical circular wheel"; 5.7: solve trigonometric equations in an interval;
2.11: use of functions in modelling.

"A Ferris wheel has a radius of 20 m and its lowest point is 2 m above the ground. It makes one
complete revolution every 12 minutes. A passenger car starts at the lowest point. Form a model
for the height, h m, of the car t minutes after it starts, and find all the times during the
first revolution when the car is 32 m above the ground. State one assumption your model makes."
Model: h = 22 - 20cos(30t) (degrees); cos(30t) = -0.5, so 30t = 120 or 240, t = 4 or 8;
assumption: the wheel turns at a constant speed.

Generation picks the period from divisors of 360 and a target angle from {60, 90, 120} whose
cosine is exact and whose time is a whole number, then derives the target height and times.
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
from app.engine.expr import ExpressionError, compile_expression, equivalent
from app.engine.registry import register
from app.models.enums import StepOutcome

TOLERANCE = 0.01
ANGLES = (60, 90, 120)  # exact cosines: 0.5, 0, -0.5
COS = {60: 0.5, 90: 0.0, 120: -0.5}
CORRECT_ASSUMPTION = "The wheel turns at a constant speed."
ASSUMPTIONS = tuple(
    sorted(
        (
            CORRECT_ASSUMPTION,
            "The height of the point does not change.",
            "The wheel speeds up during each revolution.",
        )
    )
)


def _derived() -> dict[str, bool]:
    return {"derived": True}


class WheelParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    radius: int = Field(ge=2, le=80)
    clearance: int = Field(ge=1, le=80, description="Height of the lowest point above the ground.")
    period: int = Field(ge=4, le=120, description="Time for one revolution; a divisor of 360.")
    angle: int = Field(ge=60, le=120, description="Angle turned (degrees) when the target height is first reached.")
    centre: int = Field(ge=1, json_schema_extra=_derived())
    target_height: int = Field(ge=0, json_schema_extra=_derived())
    t1: int = Field(ge=0, json_schema_extra=_derived())
    t2: int = Field(ge=0, json_schema_extra=_derived())

    @property
    def k(self) -> int:
        """Degrees turned per unit time."""
        return 360 // self.period

    def height(self, t: float) -> float:
        return self.centre - self.radius * math.cos(math.radians(self.k * t))


class WheelSlots(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lead_in: str | None = Field(default=None, max_length=200)
    subject: str = Field(min_length=1, max_length=80)  # "A Ferris wheel"
    point: str = Field(min_length=1, max_length=40)  # "passenger car"
    datum: str = Field(default="the ground", min_length=1, max_length=60)  # what heights are measured from
    length_unit: Literal["cm", "m"]
    time_unit: Literal["seconds", "minutes"]


class WheelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    amplitude: float | None = None
    centre_height: float | None = None
    period: float | None = None
    model: str | None = Field(default=None, max_length=120)
    times: list[float] | None = Field(default=None, max_length=6)
    assumption: str | None = Field(default=None, max_length=120)


def _strip_lhs(text: str) -> str:
    """Allow 'h = 22 - 20cos(36t)' as well as '22 - 20cos(36t)'."""
    return re.sub(r"^\s*h\s*=", "", text)


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=TOLERANCE)


@register
class TrigWheelHeight(QuestionTemplate[WheelParams, WheelSlots, WheelResponse]):
    id = "TRIG-WHEEL-HEIGHT"
    version = 1
    title = "Height of a point on a rotating wheel"
    domain = Domain.TRIGONOMETRIC
    primary_objective = "MOD-05"
    secondary_objectives = ("MOD-01", "MOD-07", "MOD-09", "MOD-04")
    spec_refs = ("5.9", "5.7", "2.11", "OT3.5")
    review_status = ReviewStatus.DRAFT
    params_model = WheelParams
    slots_model = WheelSlots
    response_model = WheelResponse
    default_scenario = "SCN-WHEEL-FERRIS"
    difficulty_notes = "2 when the target is the centre height (cos = 0); 3 otherwise (cos = ±0.5)."

    constraints = (
        Constraint("centre_derived", "centre must equal radius + clearance", lambda p: p.centre == p.radius + p.clearance),
        Constraint("period_divides_360", "the period must divide 360", lambda p: 360 % p.period == 0),
        Constraint("exact_angle", f"angle must be one of {ANGLES}", lambda p: p.angle in ANGLES),
        Constraint("whole_times", "angle × period must be a multiple of 360", lambda p: p.angle * p.period % 360 == 0),
        Constraint(
            "whole_height", "radius must be even unless the angle is 90°", lambda p: p.angle == 90 or p.radius % 2 == 0
        ),
        Constraint(
            "target_derived",
            "target_height must equal centre - radius × cos(angle)",
            lambda p: p.angle in COS and p.target_height == p.centre - p.radius * COS[p.angle],
        ),
        Constraint(
            "times_derived",
            "t1 = angle × period / 360 and t2 = period - t1",
            lambda p: p.t1 * 360 == p.angle * p.period and p.t2 == p.period - p.t1,
        ),
    )

    marking_criteria = (
        MarkingCriterion("extract_features", "MOD-01", "Identifies the amplitude, centre height and period."),
        MarkingCriterion("form_model", "MOD-05", "Forms a trigonometric model for the height."),
        MarkingCriterion("solve", "MOD-07", "Solves the model for the first time the height is reached."),
        MarkingCriterion("validate_times", "MOD-09", "Gives every time in the first revolution and no others."),
        MarkingCriterion("state_assumption", "MOD-04", "Identifies an assumption the model makes."),
    )

    response_fields = (
        ResponseField("amplitude", "Amplitude", FieldKind.NUMBER),
        ResponseField("centre_height", "Height of the centre", FieldKind.NUMBER),
        ResponseField("period", "Period", FieldKind.NUMBER),
        ResponseField(
            "model", "h =", FieldKind.EXPRESSION, help="In t, with angles in degrees, e.g. 10 - 8cos(30t)"
        ),
        ResponseField("times", "Times in the first revolution", FieldKind.NUMBER_LIST, help="Give every time"),
        ResponseField("assumption", "One assumption of the model", FieldKind.CHOICE, options=ASSUMPTIONS),
    )

    hints = (
        Hint("features", "MOD-01", "The amplitude is the radius; the midline is the height of the centre."),
        Hint("start", "MOD-05", "At t = 0 the point is at its lowest, so the model starts at a minimum: use −cos."),
        Hint("solve", "MOD-07", "Rearrange to cos(kt) = …, then find every angle between 0° and 360°."),
    )

    def fields(self, s: WheelSlots) -> tuple[ResponseField, ...]:
        units = {"amplitude": s.length_unit, "centre_height": s.length_unit, "period": s.time_unit, "times": s.time_unit}
        return tuple(replace(f, unit=units.get(f.name, f.unit)) for f in self.response_fields)

    def sample(self, rng: random.Random, bounds: Bounds) -> WheelParams:
        lo, hi = bounds["period"]
        periods = [d for d in range(max(lo, 1), hi + 1) if 360 % d == 0] or [lo]
        period = rng.choice(periods)
        a_lo, a_hi = bounds["angle"]
        angles = [a for a in ANGLES if a_lo <= a <= a_hi and a * period % 360 == 0] or [a_lo]
        angle = rng.choice(angles)
        r_lo, r_hi = bounds["radius"]
        if angle == 90:
            radius = rng.randint(r_lo, r_hi)
        else:
            evens = list(range(r_lo + r_lo % 2, r_hi + 1, 2)) or [r_lo]
            radius = rng.choice(evens)
        clearance = rng.randint(*bounds["clearance"])
        centre = radius + clearance
        target = round(centre - radius * COS.get(angle, 0.0))
        t1 = angle * period // 360
        return WheelParams(
            radius=radius,
            clearance=clearance,
            period=period,
            angle=angle,
            centre=centre,
            target_height=target,
            t1=t1,
            t2=period - t1,
        )

    def render_prompt(self, p: WheelParams, s: WheelSlots) -> str:
        L, T = s.length_unit, s.time_unit
        parts = [
            s.lead_in,
            f"{s.subject} has a radius of {p.radius} {L}, and its lowest point is {p.clearance} {L} above {s.datum}.",
            f"It makes one complete revolution every {p.period} {T}.",
            f"A {s.point} starts at the lowest point of the wheel.",
            f"Form a model for the height, h {L}, of the {s.point} above {s.datum} t {T} after it starts,",
            f"and find all the times during the first revolution when the {s.point} is {p.target_height} {L}"
            f" above {s.datum}.",
            "State one assumption your model makes.",
        ]
        return " ".join(part for part in parts if part)

    def _model_text(self, p: WheelParams) -> str:
        return f"{p.centre} - {p.radius}cos({p.k}t)"

    def expected_answer(self, p: WheelParams, s: WheelSlots) -> WheelResponse:
        return WheelResponse(
            amplitude=p.radius,
            centre_height=p.centre,
            period=p.period,
            model=self._model_text(p),
            times=[p.t1, p.t2],
            assumption=CORRECT_ASSUMPTION,
        )

    def worked_solution(self, p: WheelParams, s: WheelSlots) -> list[WorkedStep]:
        L, T = s.length_unit, s.time_unit
        cos_value = COS[p.angle]
        return [
            WorkedStep(
                "MOD-01",
                "Extract the features",
                f"Amplitude = radius = {p.radius} {L}. Centre height = {p.radius} + {p.clearance} = {p.centre} {L}. "
                f"Period = {p.period} {T}, so the wheel turns 360 ÷ {p.period} = {p.k}° per {T[:-1]}.",
            ),
            WorkedStep(
                "MOD-05",
                "Form the model",
                f"The {s.point} starts at the lowest point, so h = {self._model_text(p)} (angles in degrees).",
            ),
            WorkedStep(
                "MOD-07",
                "Solve",
                f"{self._model_text(p)} = {p.target_height}, so cos({p.k}t) = ({p.centre} - {p.target_height}) ÷ "
                f"{p.radius} = {cos_value:g}. So {p.k}t = {p.angle}° or {360 - p.angle}°, giving t = {p.t1} or "
                f"t = {p.t2}.",
            ),
            WorkedStep(
                "MOD-09",
                "Check the times",
                f"Both {p.t1} and {p.t2} {T} lie within the first revolution (0 to {p.period} {T}); the next "
                f"solutions, {p.t1 + p.period} and {p.t2 + p.period}, are in the second revolution.",
            ),
            WorkedStep(
                "MOD-04",
                "State an assumption",
                f"{CORRECT_ASSUMPTION} (The model also treats the {s.point} as a point on a perfect circle.)",
            ),
        ]

    def difficulty(self, p: WheelParams) -> int:
        return 2 if p.angle == 90 else 3

    def mark(self, p: WheelParams, s: WheelSlots, r: WheelResponse) -> list[MarkedStep]:
        steps: list[MarkedStep] = []

        def add(step: str, outcome: StepOutcome, feedback: str) -> None:
            objective = next(c.objective for c in self.marking_criteria if c.step == step)
            steps.append(MarkedStep(step, objective, outcome, feedback))

        # MOD-01: features
        given = {"amplitude": r.amplitude, "centre height": r.centre_height, "period": r.period}
        expected = {"amplitude": p.radius, "centre height": p.centre, "period": p.period}
        if all(v is None for v in given.values()):
            add("extract_features", StepOutcome.MISSING, "Give the amplitude, centre height and period.")
        else:
            wrong = [name for name, v in given.items() if v is None or not _close(v, expected[name])]
            if not wrong:
                add("extract_features", StepOutcome.CORRECT, "Correct: amplitude, centre height and period.")
            elif "centre height" in wrong and r.centre_height is not None and _close(r.centre_height, p.radius):
                add("extract_features", StepOutcome.INCORRECT, "The centre is the radius plus the height of the lowest point.")
            else:
                add("extract_features", StepOutcome.INCORRECT, f"Check the {' and '.join(wrong)}.")

        # MOD-05: model (any equivalent form, e.g. a phase-shifted sine)
        if not r.model:
            add("form_model", StepOutcome.MISSING, "Write h in terms of t.")
        else:
            try:
                f = compile_expression(_strip_lhs(r.model), variable="t", trig=True)
                if equivalent(f, p.height):
                    add("form_model", StepOutcome.CORRECT, f"Correct: h = {self._model_text(p)}.")
                elif equivalent(f, lambda t: p.centre + p.radius * math.cos(math.radians(p.k * t))):
                    add("form_model", StepOutcome.INCORRECT, "At t = 0 your model gives the highest point, not the lowest.")
                else:
                    add("form_model", StepOutcome.INCORRECT, "Your model does not match the wheel's height over time.")
            except ExpressionError as exc:
                add("form_model", StepOutcome.INCORRECT, str(exc))

        # MOD-07: first solution; MOD-09: exactly the solutions in the first revolution
        times = r.times or []
        if not times:
            add("solve", StepOutcome.MISSING, "Give the times when the height is reached.")
            add("validate_times", StepOutcome.MISSING, "Give every time in the first revolution.")
        else:
            if any(_close(t, p.t1) for t in times):
                add("solve", StepOutcome.CORRECT, f"Correct: the first time is t = {p.t1}.")
            else:
                add("solve", StepOutcome.INCORRECT, f"Rearrange to cos({p.k}t) = … and use inverse cosine.")
            outside = [t for t in times if not 0 <= t <= p.period]
            matched = sorted(t for t in times if _close(t, p.t1) or _close(t, p.t2))
            if outside:
                add("validate_times", StepOutcome.INCORRECT, f"Only times from 0 to {p.period} are in the first revolution.")
            elif len(matched) == 2 and len(times) == 2 and not _close(*matched):
                add("validate_times", StepOutcome.CORRECT, "Correct: two times in the first revolution.")
            elif len(times) == 1:
                add("validate_times", StepOutcome.INCORRECT, "The height is reached twice per revolution: once rising, once falling.")
            else:
                add("validate_times", StepOutcome.INCORRECT, "Check each time by substituting it into your model.")

        # MOD-04: assumption
        if r.assumption is None:
            add("state_assumption", StepOutcome.MISSING, "Choose an assumption the model makes.")
        elif r.assumption == CORRECT_ASSUMPTION:
            add("state_assumption", StepOutcome.CORRECT, "Correct: a sinusoidal model needs a constant rate of turning.")
        else:
            add("state_assumption", StepOutcome.INCORRECT, "Which assumption makes the height repeat smoothly every period?")

        return steps

    def checks(self, p: WheelParams, s: WheelSlots, prompt: str) -> list[ValidationCheck]:
        M, PED, PRES = ValidationCategory.MATHEMATICAL, ValidationCategory.PEDAGOGICAL, ValidationCategory.PRESENTATION
        numbers = {int(n) for n in re.findall(r"\d+", prompt)}
        static = {int(n) for n in re.findall(r"\d+", " ".join(filter(None, (s.lead_in, s.subject, s.point, s.datum))))}
        given = {p.radius, p.clearance, p.period, p.target_height}
        answer = self.expected_answer(p, s)
        second_revolution = answer.model_copy(update={"times": [p.t1, p.t2, p.t1 + p.period]})
        validate_step = next(m for m in self.mark(p, s, second_revolution) if m.step == "validate_times")

        def check(name: str, category: ValidationCategory, passed: bool, message: str) -> ValidationCheck:
            return ValidationCheck(name, category, passed, "" if passed else message)

        return [
            check(
                "two_solutions_exist",
                M,
                p.clearance < p.target_height < p.clearance + 2 * p.radius,
                "the target height must lie strictly between the lowest and highest points",
            ),
            check(
                "solutions_satisfy_model",
                M,
                0 < p.t1 < p.t2 < p.period and all(_close(p.height(t), p.target_height) for t in (p.t1, p.t2)),
                "the derived times do not give the target height",
            ),
            check(
                "extraneous_times_rejected",
                M,
                validate_step.outcome is StepOutcome.INCORRECT,
                "a time from the second revolution is not rejected",
            ),
            check(
                "units_consistent",
                M,
                f"{p.radius} {s.length_unit}" in prompt and f"{p.period} {s.time_unit}" in prompt,
                "lengths and times must be stated with the scenario's units",
            ),
            check(
                "given_values_present",
                PRES,
                given <= numbers <= given | static,
                f"prompt must state the radius, clearance, period and target height, found {sorted(numbers)}",
            ),
            check(
                "prompt_does_not_reveal_model",
                PED,
                not re.search(r"\b(sin|cos|constant)", prompt.lower()),
                "the prompt names the trig function or states the constant-speed assumption",
            ),
        ]
