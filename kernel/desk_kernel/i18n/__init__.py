from __future__ import annotations

from typing import Any

from desk_kernel.claim import ClaimClass

from .catalogs import CATALOGS, LOCALE_NAMES, PAY_UI

LANG_COOKIE = "desk_lang"

# Public IA Emberline already has. Sibling desks inherit English, then overlay locale.
LANDING_UI = {
    "cta_sample": "Sample brief",
    "nav_sample": "Sample",
    "nav_press": "Press",
    "nav_legal": "Terms",
    "nav_status": "Status",
    "nav_guide": "Guide",
    "cta_guide": "User guide",
    "cta_desk": "Open the desk",
    "sell_kicker": "We sell",
    "refuse_kicker": "We refuse",
    "beyond_kicker": "Why a desk",
    "product_kicker": "The product",
    "meta_fail": "Fail-closed",
    "meta_fail_p": "empty LIVE stays empty",
    "meta_cite": "Cite pack",
    "meta_cite_p": "PDF · JSON · SHA256",
    "meta_box": "Named box",
    "meta_box_p": "a person owns it",
    "press_kicker": "Press kit",
    "press_h1": "In one paragraph",
    "legal_h1": "Terms",
    "status_h1": "Status",
    "shared_brief": "Brief",
    "brief_gone": "Brief unavailable",
}


def pick_locale(claim: ClaimClass, requested: str | None = None, accept_language: str | None = None) -> str:
    allowed = set(claim.locales)
    default = claim.default_locale if claim.default_locale in allowed else claim.locales[0]
    for candidate in (requested, _from_accept(accept_language)):
        if not candidate:
            continue
        code = candidate.lower().replace("_", "-")
        if code in allowed:
            return code
        primary = code.split("-", 1)[0]
        if primary == "no" and "nb" in allowed:
            return "nb"
        if primary in allowed:
            return primary
    return default


def _from_accept(header: str | None) -> str | None:
    if not header:
        return None
    first = header.split(",", 1)[0].split(";", 1)[0].strip()
    return first or None


def catalog_for(claim: ClaimClass, locale: str) -> dict[str, Any]:
    desk = CATALOGS.get(claim.id) or {}
    en_pack = desk.get("en") or {}
    pack = desk.get(locale) or desk.get(claim.default_locale) or en_pack
    ui = {
        **PAY_UI.get("en", {}),
        **LANDING_UI,
        **PAY_UI.get(locale, PAY_UI["en"]),
        **(en_pack.get("ui") or {}),
        **(pack.get("ui") or {}),
    }
    press = {**(en_pack.get("press") or {}), **(pack.get("press") or {})}
    legal = {**(en_pack.get("legal") or {}), **(pack.get("legal") or {})}
    landing = {**(en_pack.get("landing") or {}), **(pack.get("landing") or {})}
    return {
        "desk_id": claim.id,
        "locale": locale if locale in claim.locales else claim.default_locale,
        "locales": [
            {"code": code, "name": LOCALE_NAMES.get(code, code)}
            for code in claim.locales
        ],
        "host_region": claim.host_region,
        "placement_note": claim.placement_note,
        "ui": ui,
        "guide": pack.get("guide") or en_pack.get("guide") or {"title": "", "lede": "", "sections": []},
        "press": press,
        "legal": legal,
        "landing": landing,
    }
