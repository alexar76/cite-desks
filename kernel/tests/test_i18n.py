from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("HUB_MODE", "fixture")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SEED_DEMO", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-must-be-at-least-32b")
os.environ.setdefault("PAY_MODE", "fixture")
os.environ.setdefault("DESK_MODE", "live")
os.environ.setdefault("DESK_ID", "tideline")

from desk_kernel.claim import EMBERLINE, PLINTH, SEAMARK, SOLRECORD, TIDELINE
from desk_kernel.i18n import catalog_for, pick_locale


def test_locale_sets_match_geography() -> None:
    assert EMBERLINE.locales == ("en", "es", "fr") and EMBERLINE.host_region == "us"
    assert TIDELINE.locales == ("en", "nl", "fr", "de") and TIDELINE.host_region == "nl"
    assert SOLRECORD.locales == ("en", "es", "de") and SOLRECORD.host_region == "us"
    assert SEAMARK.locales == ("en", "fi", "nb") and SEAMARK.host_region == "nl"
    assert PLINTH.locales == ("en", "es", "de") and PLINTH.host_region == "us"
    assert PLINTH.brief_preset == "campus"
    assert "sv" not in SEAMARK.locales


def test_negotiate_accept_language() -> None:
    assert pick_locale(TIDELINE, None, "nl-NL,en;q=0.8") == "nl"
    assert pick_locale(SEAMARK, None, "no") == "nb"
    assert pick_locale(SEAMARK, "sv", "sv") == "en"
    assert pick_locale(EMBERLINE, "fr", None) == "fr"


def test_catalogs_have_guides() -> None:
    for claim in (TIDELINE, SOLRECORD, SEAMARK, PLINTH):
        for locale in claim.locales:
            pack = catalog_for(claim, locale)
            assert pack["ui"]["cta_guide"]
            assert pack["ui"]["cta_sample"]
            assert pack["guide"]["sections"]
            assert pack["host_region"] == claim.host_region
            assert pack["landing"]["sell"]
            assert pack["press"]["boilerplate"]
            assert pack["legal"]["p1"]


def test_every_locale_can_render_checkout() -> None:
    """A payment page is the worst place to leak an untranslated key or an empty label."""
    from desk_kernel.i18n.catalogs import PAY_UI

    keys = set(PAY_UI["en"])
    for claim in (TIDELINE, SOLRECORD, SEAMARK, PLINTH):
        for locale in claim.locales:
            ui = catalog_for(claim, locale)["ui"]
            missing = [key for key in keys if not ui.get(key)]
            assert not missing, f"{claim.id}/{locale} cannot render checkout: {missing}"


def test_no_desk_still_claims_there_is_no_self_serve_signup() -> None:
    """The kernel sells prepaid access unattended; a guide saying otherwise is now a lie."""
    from desk_kernel.i18n.catalogs import CATALOGS

    for desk_id, locales in CATALOGS.items():
        for locale, pack in locales.items():
            text = " ".join(
                paragraph
                for section in pack["guide"]["sections"]
                for paragraph in section["body"]
            ).lower()
            for phrase in ("no self-serve", "geen self-serve", "pas d’inscription libre", "kein self-serve"):
                assert phrase not in text, f"{desk_id}/{locale} still denies self-serve checkout"
