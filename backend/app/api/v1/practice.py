import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.engine import UnknownTemplate, all_templates, generate, get_template
from app.engine.base import AnyTemplate, ReviewStatus
from app.models import QuestionInstance, User
from app.schemas.practice import (
    MAX_SEED,
    AttemptIn,
    AttemptOut,
    CreateInstanceIn,
    HintOut,
    InstanceOut,
    MarkedStepOut,
    ObjectiveTag,
    ResponseFieldOut,
    TemplateOut,
    WorkedStepOut,
)
from app.services.practice import get_or_create_instance, objective_outcomes, record_attempt

router = APIRouter(tags=["practice"])


def servable(template: AnyTemplate, settings: Settings) -> bool:
    """Only approved templates reach students; development also serves drafts for testing."""
    return template.review_status is ReviewStatus.APPROVED or settings.environment == "development"


def template_out(t: AnyTemplate) -> TemplateOut:
    return TemplateOut(
        id=t.id,
        version=t.version,
        title=t.title,
        domain=t.domain.value,
        primary_objective=t.primary_objective,
        secondary_objectives=list(t.secondary_objectives),
        review_status=t.review_status,
    )


def instance_out(instance: QuestionInstance, template: AnyTemplate) -> InstanceOut:
    return InstanceOut(
        id=instance.id,
        template_id=instance.template_id,
        template_version=instance.template_version,
        prompt=instance.prompt,
        difficulty=instance.difficulty,
        objectives=[ObjectiveTag(id=o.objective.code, is_primary=o.is_primary) for o in instance.objectives],
        response_fields=[
            ResponseFieldOut(name=f.name, label=f.label, kind=f.kind, help=f.help, options=list(f.options), unit=f.unit)
            for f in template.response_fields
        ],
        hints=[HintOut(id=h.id, objective=h.objective, text=h.text) for h in template.hints],
    )


def load_instance(db: Session, instance_id: int) -> tuple[QuestionInstance, AnyTemplate]:
    instance = db.get(QuestionInstance, instance_id)
    if instance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question instance not found.")
    try:
        template = get_template(instance.template_id, instance.template_version)
    except UnknownTemplate:
        raise HTTPException(status.HTTP_409_CONFLICT, "This question's template is no longer available.") from None
    return instance, template


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(
    settings: Settings = Depends(get_settings), _user: User = Depends(get_current_user)
) -> list[TemplateOut]:
    return [template_out(t) for t in all_templates() if servable(t, settings)]


@router.post("/practice/instances", response_model=InstanceOut, status_code=status.HTTP_201_CREATED)
def create_instance(
    body: CreateInstanceIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _user: User = Depends(get_current_user),
) -> InstanceOut:
    candidates = [t for t in all_templates() if servable(t, settings)]
    if body.template_id is not None:
        candidates = [t for t in candidates if t.id == body.template_id]
    if not candidates:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No question template is available.")
    # Latest version of the requested template, or a random template.
    template = max(candidates, key=lambda t: t.version) if body.template_id else secrets.choice(candidates)
    seed = body.seed if body.seed is not None else secrets.randbelow(MAX_SEED + 1)
    instance = get_or_create_instance(db, generate(template, seed))
    return instance_out(instance, template)


@router.get("/practice/instances/{instance_id}", response_model=InstanceOut)
def read_instance(
    instance_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> InstanceOut:
    instance, template = load_instance(db, instance_id)
    return instance_out(instance, template)


@router.post(
    "/practice/instances/{instance_id}/attempts", response_model=AttemptOut, status_code=status.HTTP_201_CREATED
)
def submit_attempt(
    instance_id: int,
    body: AttemptIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptOut:
    instance, template = load_instance(db, instance_id)
    try:
        response = template.response_model.model_validate(body.response)
    except ValidationError as exc:
        raise RequestValidationError(
            [{**e, "loc": ("body", "response", *e["loc"])} for e in exc.errors(include_url=False)]
        ) from exc
    unknown_hints = set(body.hints_used) - {h.id for h in template.hints}
    if unknown_hints:
        raise RequestValidationError(
            [{"loc": ("body", "hints_used"), "msg": f"Unknown hints {sorted(unknown_hints)}", "type": "value_error"}]
        )

    evidence, steps = record_attempt(db, user, instance, template, response, body.hints_used, body.time_taken_ms)
    return AttemptOut(
        evidence_id=evidence.id,
        attempt_number=evidence.attempt_number,
        outcome=evidence.outcome,
        steps=[MarkedStepOut(step=s.step, objective=s.objective, outcome=s.outcome, feedback=s.feedback) for s in steps],
        objective_outcomes=objective_outcomes(steps),
        expected_answer=instance.expected_answer,
        worked_solution=[WorkedStepOut(**s) for s in instance.worked_solution],
    )
