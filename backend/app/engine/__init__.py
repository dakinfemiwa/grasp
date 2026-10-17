"""Deterministic question-generation engine (no LLM at runtime)."""

import app.engine.templates  # noqa: F401  (registers templates)
from app.engine.generator import build, generate
from app.engine.registry import UnknownTemplate, all_templates, get_template

__all__ = ["UnknownTemplate", "all_templates", "build", "generate", "get_template"]
