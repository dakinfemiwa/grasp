import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalogue import load_catalogue
from app.catalogue.schema import validate_catalogue
from app.models import (
    Evidence,
    EvidenceObjective,
    InstanceObjective,
    LearningObjective,
    QuestionInstance,
    StudentProgress,
    User,
    objective_prerequisites,
)
from app.models.enums import EvidenceOutcome, StepOutcome
from app.seed import SeedError, sync_catalogue


def make_objective(db: Session, code: str = "MOD-99") -> LearningObjective:
    objective = LearningObjective(code=code, domain_area="T", title="Obj", description="d", catalogue_version=1)
    db.add(objective)
    db.flush()
    return objective


def make_instance(db: Session, objective: LearningObjective, **overrides: object) -> QuestionInstance:
    fields: dict[str, object] = dict(
        template_id="T-1",
        template_version=1,
        seed=1,
        parameters={"a": 1},
        prompt="p",
        expected_answer={"x": 1},
        worked_solution=[],
        validation=[],
        difficulty=2,
        objectives=[InstanceObjective(objective_id=objective.id, is_primary=True)],
    )
    fields.update(overrides)
    instance = QuestionInstance(**fields)
    db.add(instance)
    db.flush()
    return instance


def test_instance_evidence_and_progress_round_trip(db: Session) -> None:
    user = User(external_auth_id="user_1")
    db.add(user)
    objective = make_objective(db)
    instance = make_instance(db, objective)
    db.add(
        Evidence(
            user_id=user.id,
            instance_id=instance.id,
            attempt_number=1,
            response={"x": 1},
            outcome=EvidenceOutcome.CORRECT,
            marking=[],
            objectives=[EvidenceObjective(objective_id=objective.id, outcome=StepOutcome.CORRECT)],
        )
    )
    db.add(StudentProgress(user_id=user.id, learning_objective_id=objective.id, attempts=1, correct_attempts=1))
    db.commit()

    evidence = db.scalar(select(Evidence))
    assert evidence is not None and evidence.outcome is EvidenceOutcome.CORRECT
    assert evidence.instance.objectives[0].objective.code == "MOD-99"
    assert evidence.objectives[0].outcome is StepOutcome.CORRECT
    progress = db.get(StudentProgress, (user.id, objective.id))
    assert progress is not None and progress.current_difficulty == 1


@pytest.mark.parametrize("overrides", [{"difficulty": 6}, {"difficulty": 0}])
def test_instance_constraints(db: Session, overrides: dict[str, object]) -> None:
    with pytest.raises(IntegrityError):
        make_instance(db, make_objective(db), **overrides)


def test_instance_seed_is_unique_per_template_version(db: Session) -> None:
    objective = make_objective(db)
    make_instance(db, objective)
    make_instance(db, objective, template_version=2, objectives=[])
    with pytest.raises(IntegrityError):
        make_instance(db, objective, objectives=[])


def test_attempt_number_is_unique_and_positive(db: Session) -> None:
    user = User(external_auth_id="user_1")
    db.add(user)
    instance = make_instance(db, make_objective(db))

    def evidence(n: int) -> Evidence:
        return Evidence(
            user_id=user.id, instance_id=instance.id, attempt_number=n, response={}, outcome=EvidenceOutcome.CORRECT, marking=[]
        )

    db.add(evidence(1))
    db.flush()
    db.add(evidence(1))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_progress_rejects_more_correct_than_attempts(db: Session) -> None:
    user = User(external_auth_id="user_1")
    db.add(user)
    objective = make_objective(db)
    db.add(StudentProgress(user_id=user.id, learning_objective_id=objective.id, attempts=1, correct_attempts=2))
    with pytest.raises(IntegrityError):
        db.flush()


def test_catalogue_sync_is_idempotent(db: Session) -> None:
    catalogue = load_catalogue()
    assert sync_catalogue(db, catalogue) == 11
    first = {o.code: o.id for o in db.scalars(select(LearningObjective))}
    edges = db.scalar(select(func.count()).select_from(objective_prerequisites))

    sync_catalogue(db, catalogue)

    assert {o.code: o.id for o in db.scalars(select(LearningObjective))} == first
    assert db.scalar(select(func.count()).select_from(objective_prerequisites)) == edges == 9
    mod05 = db.scalar(select(LearningObjective).where(LearningObjective.code == "MOD-05"))
    assert mod05 is not None and sorted(p.code for p in mod05.prerequisites) == ["MOD-02", "MOD-03"]


def test_catalogue_sync_reflects_prerequisite_changes_and_removals(db: Session) -> None:
    sync_catalogue(db, load_catalogue())
    data = load_catalogue().model_dump(mode="json")
    data["objectives"] = [o for o in data["objectives"] if o["id"] != "MOD-11"]
    for o in data["objectives"]:
        if o["id"] == "MOD-07":
            o["prerequisites"] = ["MOD-05", "MOD-06"]

    sync_catalogue(db, validate_catalogue(data))

    mod07 = db.scalar(select(LearningObjective).where(LearningObjective.code == "MOD-07"))
    assert mod07 is not None and sorted(p.code for p in mod07.prerequisites) == ["MOD-05", "MOD-06"]
    assert db.scalar(select(LearningObjective).where(LearningObjective.code == "MOD-11")) is None


def test_catalogue_sync_refuses_to_delete_referenced_objective(db: Session) -> None:
    sync_catalogue(db, load_catalogue())
    mod11 = db.scalar(select(LearningObjective).where(LearningObjective.code == "MOD-11"))
    assert mod11 is not None
    make_instance(db, mod11)
    db.commit()
    data = load_catalogue().model_dump(mode="json")
    data["objectives"] = [o for o in data["objectives"] if o["id"] != "MOD-11"]

    with pytest.raises(SeedError, match="MOD-11"):
        sync_catalogue(db, validate_catalogue(data))


def test_self_prerequisite_is_rejected_by_database(db: Session) -> None:
    objective = make_objective(db)
    with pytest.raises(IntegrityError):
        db.execute(objective_prerequisites.insert().values(objective_id=objective.id, prerequisite_id=objective.id))
