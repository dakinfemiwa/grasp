import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalogue import load_catalogue
from app.catalogue.schema import validate_catalogue
from app.models import Attempt, LearningObjective, Question, StudentProgress, User, objective_prerequisites
from app.models.enums import Correctness, ErrorType, Representation
from app.seed import SeedError, sync_catalogue


def make_objective(db: Session) -> LearningObjective:
    objective = LearningObjective(
        code="MOD-99", domain_area="T", title="Obj", description="d", catalogue_version=1
    )
    db.add(objective)
    db.flush()
    return objective


def make_question(db: Session, objective: LearningObjective, **overrides: object) -> Question:
    fields: dict[str, object] = dict(
        code="t-001",
        learning_objective_id=objective.id,
        difficulty=2,
        representation=Representation.WORD,
        context="car",
        prompt="p",
        expected_answer=1.0,
        tolerance=0.1,
        explanation="e",
    )
    fields.update(overrides)
    question = Question(**fields)
    db.add(question)
    db.flush()
    return question


def test_attempt_and_progress_round_trip(db: Session) -> None:
    user = User(external_auth_id="user_1")
    db.add(user)
    objective = make_objective(db)
    question = make_question(db, objective, extra={"common_errors": [{"answer": 2}]})
    db.add(
        Attempt(
            user_id=user.id,
            question_id=question.id,
            submitted_answer="1.0",
            parsed_answer=1.0,
            correctness=Correctness.CORRECT,
            error_type=ErrorType.CORRECT,
        )
    )
    db.add(StudentProgress(user_id=user.id, learning_objective_id=objective.id, attempts=1, correct_attempts=1))
    db.commit()

    attempt = db.scalar(select(Attempt))
    assert attempt is not None
    assert attempt.correctness is Correctness.CORRECT
    assert attempt.question.extra == {"common_errors": [{"answer": 2}]}
    progress = db.get(StudentProgress, (user.id, objective.id))
    assert progress is not None and progress.current_difficulty == 1


@pytest.mark.parametrize("overrides", [{"difficulty": 6}, {"difficulty": 0}, {"tolerance": -1.0}])
def test_question_constraints(db: Session, overrides: dict[str, object]) -> None:
    with pytest.raises(IntegrityError):
        make_question(db, make_objective(db), **overrides)


def test_progress_rejects_more_correct_than_attempts(db: Session) -> None:
    user = User(external_auth_id="user_1")
    db.add(user)
    objective = make_objective(db)
    db.add(StudentProgress(user_id=user.id, learning_objective_id=objective.id, attempts=1, correct_attempts=2))
    with pytest.raises(IntegrityError):
        db.flush()


def test_question_requires_existing_objective(db: Session) -> None:
    with pytest.raises(IntegrityError):
        make_question(db, LearningObjective(id=999))


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
    make_question(db, mod11)
    db.commit()
    data = load_catalogue().model_dump(mode="json")
    data["objectives"] = [o for o in data["objectives"] if o["id"] != "MOD-11"]

    with pytest.raises(SeedError, match="MOD-11"):
        sync_catalogue(db, validate_catalogue(data))


def test_self_prerequisite_is_rejected_by_database(db: Session) -> None:
    objective = make_objective(db)
    with pytest.raises(IntegrityError):
        db.execute(objective_prerequisites.insert().values(objective_id=objective.id, prerequisite_id=objective.id))
