from __future__ import annotations

from typing import Any

from desk_kernel.citepack import build_cite_pack as kernel_pack
from desk_kernel.claim import EMBERLINE

from .delta import compare_briefs


def build_cite_pack(
    *,
    brief: dict[str, Any],
    raw_fire_weather: dict[str, Any] | None,
    raw_watchbox: dict[str, Any] | None,
) -> bytes:
    if "delta" not in brief:
        brief = {**brief, "delta": brief.get("delta") or compare_briefs(brief, None)}
    return kernel_pack(
        claim=EMBERLINE,
        brief=brief,
        raw={"fire_weather": raw_fire_weather, "watchbox": raw_watchbox},
    )
