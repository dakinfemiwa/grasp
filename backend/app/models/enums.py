from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class ReviewStatus(StrEnum):
    """Review state of authored content (templates, scenarios)."""

    DRAFT = "draft"  # authored, not yet reviewed by a person
    REVIEWED = "reviewed"  # reviewed, changes may be pending
    APPROVED = "approved"  # cleared for the normal student question bank


class StepOutcome(StrEnum):
    """Outcome of one marked modelling step, and of the objective-level evidence it yields."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    MISSING = "missing"  # the student left this part blank


class EvidenceOutcome(StrEnum):
    """Overall outcome of an attempt. Objective-level detail lives in evidence_objectives."""

    CORRECT = "correct"  # every step correct
    PARTIAL = "partial"  # some steps correct
    INCORRECT = "incorrect"  # no step correct
