# helpers/serde.py
from typing import Any


def to_dict(obj: Any) -> Any:
    """Recursively convert an object to a dictionary, handling nested objects and lists.

    Args:
        obj: The object to convert

    Returns:
        A JSON-serializable representation of the object, with all nested
        objects also converted to dicts.
    """
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (list, tuple)):
        return [to_dict(item) for item in obj]

    if isinstance(obj, dict):
        return {key: to_dict(value) for key, value in obj.items()}

    if hasattr(obj, '__dict__'):
        return {key: to_dict(value) for key, value in obj.__dict__.items()}

    return str(obj)
