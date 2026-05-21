"""Player-name corrections to apply on top of scraped NZWIHL data."""
from __future__ import annotations

# (team_id, jersey_number) -> (override_last, override_first | None)
SURNAME_OVERRIDES: dict[tuple[int, str], tuple[str, str | None]] = {}


def _smart_title(text: str) -> str:
    if not text:
        return text
    is_all_lower = text == text.lower()
    is_all_upper = text == text.upper()
    if not (is_all_lower or is_all_upper):
        return text

    def cap_part(part: str) -> str:
        if not part:
            return part
        return part[0].upper() + part[1:].lower()

    return " ".join(
        "-".join(cap_part(seg) for seg in word.split("-"))
        for word in text.split(" ")
    )


def normalize_name(first: str, last: str, team_id: int, jersey: str) -> tuple[str, str]:
    first_clean = _smart_title(first.strip())
    last_clean = _smart_title(last.strip())

    override = SURNAME_OVERRIDES.get((team_id, jersey))
    if override:
        override_last, override_first = override
        last_clean = override_last
        if override_first is not None:
            first_clean = override_first

    return first_clean, last_clean
