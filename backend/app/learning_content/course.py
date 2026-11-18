"""Android CoursePlan-compatible 30/7/24 grouping over existing source items."""

CAPS = {"vocabulary": 30, "grammar": 7, "kanji": 24}


def group_course_items[T](by_type: dict[str, list[T]]) -> list[dict[str, list[T]]]:
    """Chunk each type independently; preserve the caller's verified source order."""
    if any(kind not in CAPS for kind in by_type):
        raise ValueError("Unsupported content type")
    count = max((len(by_type.get(kind, [])) + cap - 1) // cap for kind, cap in CAPS.items())
    return [
        {kind: by_type.get(kind, [])[index * cap : (index + 1) * cap] for kind, cap in CAPS.items()}
        for index in range(count)
    ]
