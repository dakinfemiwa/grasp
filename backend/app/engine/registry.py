from app.engine.base import AnyTemplate

_TEMPLATES: dict[tuple[str, int], AnyTemplate] = {}


class UnknownTemplate(LookupError):
    pass


def register[T: type[AnyTemplate]](cls: T) -> T:
    key = (cls.id, cls.version)
    if key in _TEMPLATES:
        raise ValueError(f"Template {cls.id} v{cls.version} is already registered; bump the version.")
    _TEMPLATES[key] = cls()
    return cls


def get_template(template_id: str, version: int | None = None) -> AnyTemplate:
    """The given version, or the latest registered version when version is None."""
    if version is None:
        versions = [v for (tid, v) in _TEMPLATES if tid == template_id]
        if not versions:
            raise UnknownTemplate(f"Unknown template {template_id}")
        version = max(versions)
    try:
        return _TEMPLATES[(template_id, version)]
    except KeyError:
        raise UnknownTemplate(f"Unknown template {template_id} v{version}") from None


def all_templates() -> list[AnyTemplate]:
    return [_TEMPLATES[k] for k in sorted(_TEMPLATES)]
