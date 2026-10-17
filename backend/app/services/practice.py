"""Persist generated instances and record marked student evidence."""

from dataclasses import asdict
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.engine.base import AnyTemplate, GeneratedQuestion, MarkedStep
from app.engine.generator import check_dicts
from app.models import Evidence, EvidenceObjective, InstanceObjective, LearningObjective, QuestionInstance, User
from app.models.enums import EvidenceOutcome, StepOutcome


class CatalogueNotSeeded(RuntimeError):
    pass


def objective_ids(db: Session, codes: set[str]) -> dict[str, int]:
    rows = db.execute(select(LearningObjective.code, LearningObjective.id).where(LearningObjective.code.in_(codes)))
    found = {code: id_ for code, id_ in rows}
    missing = codes - found.keys()
    if missing:
        raise CatalogueNotSeeded(f"Objectives {sorted(missing)} are not in the database; run `python -m app.seed`.")
    return found


def get_or_create_instance(db: Session, q: GeneratedQuestion) -> QuestionInstance:
    """Instances are deterministic, so (template, scenario, their versions, seed) identifies one row."""
    if q.seed is None:
        raise ValueError("Only seeded instances are persisted, so they can be regenerated.")
    existing = db.scalar(
        select(QuestionInstance).where(
            QuestionInstance.template_id == q.template_id,
            QuestionInstance.template_version == q.template_version,
            QuestionInstance.scenario_id == q.scenario_id,
            QuestionInstance.scenario_version == q.scenario_version,
            QuestionInstance.seed == q.seed,
        )
    )
    if existing is not None:
        return existing

    ids = objective_ids(db, {q.primary_objective, *q.secondary_objectives})
    instance = QuestionInstance(
        template_id=q.template_id,
        template_version=q.template_version,
        seed=q.seed,
        scenario_id=q.scenario_id,
        scenario_version=q.scenario_version,
        parameters=q.parameters,
        prompt=q.prompt,
        expected_answer=q.expected_answer,
        worked_solution=[asdict(s) for s in q.worked_solution],
        validation=check_dicts(q.validation),
        difficulty=q.difficulty,
        objectives=[
            InstanceObjective(objective_id=ids[code], is_primary=code == q.primary_objective)
            for code in (q.primary_objective, *q.secondary_objectives)
        ],
    )
    db.add(instance)
    db.commit()
    return instance


def overall_outcome(steps: list[MarkedStep]) -> EvidenceOutcome:
    correct = sum(s.outcome is StepOutcome.CORRECT for s in steps)
    if correct == len(steps):
        return EvidenceOutcome.CORRECT
    return EvidenceOutcome.PARTIAL if correct else EvidenceOutcome.INCORRECT


def objective_outcomes(steps: list[MarkedStep]) -> dict[str, StepOutcome]:
    """Per objective: correct if every step for it is, missing if every step is, else incorrect."""
    by_objective: dict[str, list[StepOutcome]] = {}
    for s in steps:
        by_objective.setdefault(s.objective, []).append(s.outcome)
    result = {}
    for code, outcomes in by_objective.items():
        if all(o is StepOutcome.CORRECT for o in outcomes):
            result[code] = StepOutcome.CORRECT
        elif all(o is StepOutcome.MISSING for o in outcomes):
            result[code] = StepOutcome.MISSING
        else:
            result[code] = StepOutcome.INCORRECT
    return result


def record_attempt(
    db: Session,
    user: User,
    instance: QuestionInstance,
    template: AnyTemplate,
    slots: BaseModel,
    response: BaseModel,
    hints_used: list[str],
    time_taken_ms: int | None,
) -> tuple[Evidence, list[MarkedStep]]:
    params = template.params_model.model_validate(instance.parameters)
    steps = template.mark(params, slots, response)
    per_objective = objective_outcomes(steps)
    ids = objective_ids(db, set(per_objective))
    previous = db.scalar(
        select(func.max(Evidence.attempt_number)).where(
            Evidence.user_id == user.id, Evidence.instance_id == instance.id
        )
    )
    marking: list[dict[str, Any]] = [asdict(s) for s in steps]
    evidence = Evidence(
        user_id=user.id,
        instance_id=instance.id,
        attempt_number=(previous or 0) + 1,
        response=response.model_dump(mode="json"),
        outcome=overall_outcome(steps),
        marking=marking,
        hints_used=hints_used,
        time_taken_ms=time_taken_ms,
        objectives=[EvidenceObjective(objective_id=ids[code], outcome=o) for code, o in per_objective.items()],
    )
    db.add(evidence)
    db.commit()
    return evidence, steps


def evidence_summary(db: Session, user: User, recent_limit: int = 5) -> dict[str, Any]:
    """Per-objective evidence counts and the latest attempts, for one user.

    Deliberately transparent: raw counts and the last outcome, no mastery estimate and no
    prerequisite diagnosis (a single wrong answer says little on its own).
    """
    objectives = list(db.scalars(select(LearningObjective).order_by(LearningObjective.code)))
    counts: dict[tuple[int, StepOutcome], int] = {
        (objective_id, outcome): n
        for objective_id, outcome, n in db.execute(
            select(EvidenceObjective.objective_id, EvidenceObjective.outcome, func.count())
            .join(Evidence, Evidence.id == EvidenceObjective.evidence_id)
            .where(Evidence.user_id == user.id)
            .group_by(EvidenceObjective.objective_id, EvidenceObjective.outcome)
        )
    }
    last: dict[int, tuple[StepOutcome, Any]] = {}
    for objective_id, outcome, created_at in db.execute(
        select(EvidenceObjective.objective_id, EvidenceObjective.outcome, Evidence.created_at)
        .join(Evidence, Evidence.id == EvidenceObjective.evidence_id)
        .where(Evidence.user_id == user.id)
        .order_by(Evidence.created_at.desc(), Evidence.id.desc())
    ):
        last.setdefault(objective_id, (outcome, created_at))

    recent = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.user_id == user.id)
            .order_by(Evidence.created_at.desc(), Evidence.id.desc())
            .limit(recent_limit)
        )
    )
    total = db.scalar(select(func.count()).select_from(Evidence).where(Evidence.user_id == user.id)) or 0
    return {
        "total_attempts": total,
        "objectives": [
            {
                "id": o.code,
                "title": o.title,
                "correct": counts.get((o.id, StepOutcome.CORRECT), 0),
                "incorrect": counts.get((o.id, StepOutcome.INCORRECT), 0),
                "missing": counts.get((o.id, StepOutcome.MISSING), 0),
                "last_outcome": last.get(o.id, (None, None))[0],
                "last_at": last.get(o.id, (None, None))[1],
            }
            for o in objectives
        ],
        "recent": recent,
    }
