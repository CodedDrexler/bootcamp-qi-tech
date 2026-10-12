from uuid import UUID


def canonical_uuid(value):
    """Normalize UUID identity without changing the existing 404 for invalid lookup keys."""
    if not isinstance(value, str):
        return value
    try:
        return str(UUID(value))
    except ValueError:
        return value
