from __future__ import annotations

from copy import deepcopy
from typing import Any

INTERNAL_BLUEPRINT_CONTENT_KEYS = frozenset({"accepted_book_id"})


def public_blueprint_content(content: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in content.items()
        if key not in INTERNAL_BLUEPRINT_CONTENT_KEYS
    }
