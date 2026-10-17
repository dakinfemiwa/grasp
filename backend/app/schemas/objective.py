from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.catalogue import Domain, EvidenceType


class ObjectiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(validation_alias="code", description="Grasp-internal id, e.g. MOD-05 (not an Edexcel id)")
    title: str
    description: str
    domain_area: str
    success_criteria: list[str]
    prerequisites: list[str]
    domains: list[Domain]
    evidence_types: list[EvidenceType]
    spec_refs: list[str] = Field(description="Pearson Edexcel 9MA0 (Issue 4) theme or content numbers")
    catalogue_version: int

    @field_validator("prerequisites", mode="before")
    @classmethod
    def prerequisite_codes(cls, value: list[object]) -> list[str]:
        return sorted(getattr(p, "code", p) for p in value)  # type: ignore[misc]
