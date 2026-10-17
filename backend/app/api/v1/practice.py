import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.engine import UnknownTemplate, all_templates, generate, get_template
from app.engine.base import AnyTemplate
from app.engine.scenarios import UnknownScenario, compatible_scenarios, get_scenario, pick_scenario, slots_for
from app.models import QuestionInstance, User
from app.models.enums import ReviewStatus
from app.scenarios import Scenario
from app.schemas.practice import (
    MAX_SEED,
    AttemptIn,
    AttemptOut,
    CreateInstanceIn,
    EvidenceSummaryOut,
    HintOut,
    InstanceOut,
    MarkedStepOut,
    ObjectiveEvidenceOut,
    ObjectiveTag,
    RecentAttemptOut,
    ResponseFieldOut,
    ScenarioOut,
    TemplateOut,
    WorkedStepOut,
)
from app.services.practice import evidence_summary, get_or_create_instance, objective_outcomes, record_attempt

router = APIRouter(tags=["practice"])


def servable(content: AnyTemplate | Scenario, settings: Settings) -> bool:
    """Only approved templates and scenarios reach students; development also serves drafts."""
    return content.review_status is ReviewStatus.APPROVED or settings.environment == "development"


def servable_scenarios(template: AnyTemplate, settings: Settings) -> list[Scenario]:
    return [s for s in compatible_scenarios(template) if servable(s, settings)]


def scenario_out(s: Scenario) -> ScenarioOut:
    return ScenarioOut(
        id=s.id, version=s.version, title=s.title, presentation=s.presentation, review_status=s.review_status
    )


def template_out(t: AnyTemplate, settings: Settings) -> TemplateOut:
    return TemplateOut(
        id=t.id,
        version=t.version,
        title=t.title,
        domain=t.domain.value,
        primary_objective=t.primary_objective,
        secondary_objectives=list(t.secondary_objectives),
        spec_refs=list(t.spec_refs),
        review_status=t.review_status,
        scenarios=[scenario_out(s) for s in servable_scenarios(t, settings)],
    )


def instance_out(instance: QuestionInstance, template: AnyTemplate, scenario: Scenario) -> InstanceOut:
    return InstanceOut(
        id=instance.id,
        template_id=instance.template_id,
        template_version=instance.template_version,
        scenario=scenario_out(scenario),
        prompt=instance.prompt,
        difficulty=instance.difficulty,
        objectives=[ObjectiveTag(id=o.objective.code, is_primary=o.is_primary) for o in instance.objectives],
        response_fields=[
            ResponseFieldOut(name=f.name, label=f.label, kind=f.kind, help=f.help, options=list(f.options), unit=f.unit)
            for f in template.fields(slots_for(template, scenario))
        ],
        hints=[HintOut(id=h.id, objective=h.objective, text=h.text) for h in template.hints],
    )


def load_instance(db: Session, instance_id: int) -> tuple[QuestionInstance, AnyTemplate, Scenario]:
    instance = db.get(QuestionInstance, instance_id)
    if instance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question instance not found.")
    try:
        template = get_template(instance.template_id, instance.template_version)
        scenario = get_scenario(instance.scenario_id, instance.scenario_version)
    except (UnknownTemplate, UnknownScenario):
        raise HTTPException(status.HTTP_409_CONFLICT, "This question's template or scenario is no longer available.") from None
    return instance, template, scenario


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(
    settings: Settings = Depends(get_settings), _user: User = Depends(get_current_user)
) -> list[TemplateOut]:
    return [template_out(t, settings) for t in all_templates() if servable(t, settings)]


@router.post("/practice/instances", response_model=InstanceOut, status_code=status.HTTP_201_CREATED)
def create_instance(
    body: CreateInstanceIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _user: User = Depends(get_current_user),
) -> InstanceOut:
    templates = [t for t in all_templates() if servable(t, settings) and servable_scenarios(t, settings)]
    if body.template_id is not None:
        templates = [t for t in templates if t.id == body.template_id]
    if not templates:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No question template is available.")
    # Latest version of the requested template, or a random template.
    template = max(templates, key=lambda t: t.version) if body.template_id else secrets.choice(templates)

    scenarios = servable_scenarios(template, settings)
    if body.scenario_id is not None:
        scenarios = [s for s in scenarios if s.id == body.scenario_id]
        if not scenarios:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "That scenario is not available for this template.")
    seed = body.seed if body.seed is not None else secrets.randbelow(MAX_SEED + 1)
    scenario = pick_scenario(template, seed, scenarios)

    instance = get_or_create_instance(db, generate(template, seed, scenario))
    return instance_out(instance, template, scenario)


@router.get("/practice/instances/{instance_id}", response_model=InstanceOut)
def read_instance(
    instance_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> InstanceOut:
    return instance_out(*load_instance(db, instance_id))


@router.post(
    "/practice/instances/{instance_id}/attempts", response_model=AttemptOut, status_code=status.HTTP_201_CREATED
)
def submit_attempt(
    instance_id: int,
    body: AttemptIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptOut:
    instance, template, scenario = load_instance(db, instance_id)
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

    slots = slots_for(template, scenario)
    evidence, steps = record_attempt(
        db, user, instance, template, slots, response, body.hints_used, body.time_taken_ms
    )
    return AttemptOut(
        evidence_id=evidence.id,
        attempt_number=evidence.attempt_number,
        outcome=evidence.outcome,
        steps=[MarkedStepOut(step=s.step, objective=s.objective, outcome=s.outcome, feedback=s.feedback) for s in steps],
        objective_outcomes=objective_outcomes(steps),
        expected_answer=instance.expected_answer,
        worked_solution=[WorkedStepOut(**s) for s in instance.worked_solution],
    )


def _titles(template_id: str, version: int, scenario_id: str, scenario_version: int) -> tuple[str, str]:
    try:
        template_title = get_template(template_id, version).title
    except UnknownTemplate:
        template_title = template_id
    try:
        scenario_title = get_scenario(scenario_id, scenario_version).title
    except UnknownScenario:
        scenario_title = scenario_id
    return template_title, scenario_title


@router.get("/practice/evidence/summary", response_model=EvidenceSummaryOut)
def read_evidence_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> EvidenceSummaryOut:
    summary = evidence_summary(db, user)
    recent = []
    for e in summary["recent"]:
        i = e.instance
        template_title, scenario_title = _titles(i.template_id, i.template_version, i.scenario_id, i.scenario_version)
        recent.append(
            RecentAttemptOut(
                evidence_id=e.id,
                instance_id=i.id,
                template_id=i.template_id,
                template_title=template_title,
                scenario_title=scenario_title,
                attempt_number=e.attempt_number,
                outcome=e.outcome,
                created_at=e.created_at,
            )
        )
    return EvidenceSummaryOut(
        total_attempts=summary["total_attempts"],
        objectives=[ObjectiveEvidenceOut(**o) for o in summary["objectives"]],
        recent=recent,
    )
