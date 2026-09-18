from copy import deepcopy

from app.briefs import build_brief
from app.delta import compare_briefs, first_run_delta


def _watch() -> dict:
    return {
        "id": "wat_x",
        "name": "Test Box",
        "west": -125,
        "south": 32,
        "east": -114,
        "north": 42,
        "timezone": "UTC",
    }


def _brief(hotspots: list[dict], *, brief_id: str, count: int) -> dict:
    snapshot = {
        "summary": "test",
        "evidence": {"live_fire_detection_count": count},
        "hotspots": hotspots,
        "limitations": [],
    }
    return build_brief(
        watch=_watch(),
        snapshot=snapshot,
        run_id=f"run_{brief_id}",
        brief_id=brief_id,
        skus_used=["atlas.fire.weather@v1"],
        previous_brief=None,
    )


def _live(ident: str, lat: float, lon: float, k: float) -> dict:
    return {
        "id": ident,
        "lat": lat,
        "lon": lon,
        "live": True,
        "mode": "live",
        "values": {"brightness_k": k, "confidence": 80},
        "satellite": "N20",
    }


def test_first_run_has_no_versus() -> None:
    delta = first_run_delta()
    assert delta["kind"] == "first_run"
    assert delta["versus_brief_id"] is None


def test_compare_appeared_disappeared_and_brightened() -> None:
    prior = _brief(
        [_live("a", 37.1, -121.1, 350), _live("b", 37.2, -121.2, 340)],
        brief_id="brf_prior",
        count=2,
    )
    current = _brief(
        [_live("a", 37.1, -121.1, 362), _live("c", 37.3, -121.3, 355)],
        brief_id="brf_now",
        count=4,
    )
    # strip auto first_run so we control previous
    current.pop("delta")
    delta = compare_briefs(current, prior)
    assert delta["kind"] == "versus_prior"
    assert delta["live_count"] == {"from": 2, "to": 4, "delta": 2}
    assert [row["id"] for row in delta["appeared"]] == ["c"]
    assert [row["id"] for row in delta["disappeared"]] == ["b"]
    assert delta["brightened"][0]["id"] == "a"
    assert delta["brightened"][0]["delta_k"] == 12.0
    assert "not a fire perimeter" in " ".join(delta["limitations"]).lower()


def test_build_brief_embeds_delta() -> None:
    prior = _brief([_live("a", 37.1, -121.1, 350)], brief_id="p", count=1)
    current_snapshot = {
        "summary": "later",
        "evidence": {"live_fire_detection_count": 2},
        "hotspots": [_live("a", 37.1, -121.1, 350), _live("n", 38.0, -120.0, 360)],
        "limitations": [],
    }
    brief = build_brief(
        watch=_watch(),
        snapshot=current_snapshot,
        run_id="run_n",
        brief_id="brf_n",
        skus_used=["atlas.fire.weather@v1"],
        previous_brief=prior,
    )
    assert brief["delta"]["kind"] == "versus_prior"
    assert len(brief["delta"]["appeared"]) == 1


def test_lat_lon_fallback_and_dimmed() -> None:
    prior = {
        "id": "p",
        "run_id": "rp",
        "generated_at": "2026-08-16T00:00:00+00:00",
        "evidence_status": "live_evidence",
        "live_fire_detection_count": 1,
        "hotspots": [{"lat": 37.12345, "lon": -121.12345, "brightness_k": 360}],
    }
    current = {
        "id": "n",
        "run_id": "rn",
        "generated_at": "2026-08-16T00:30:00+00:00",
        "evidence_status": "live_evidence",
        "live_fire_detection_count": 1,
        "hotspots": [{"lat": 37.12341, "lon": -121.12349, "brightness_k": 348}],
    }
    delta = compare_briefs(current, prior)
    assert delta["appeared"] == []
    assert delta["disappeared"] == []
    assert delta["dimmed"][0]["delta_k"] == -12.0
    assert delta["match"]["fallback"] == "lat_lon_rounded_4dp"


def test_small_kelvin_change_is_unchanged() -> None:
    prior = _brief([_live("a", 37.1, -121.1, 350)], brief_id="p", count=1)
    current = deepcopy(prior)
    current["id"] = "n"
    current["hotspots"][0]["brightness_k"] = 352
    current.pop("delta")
    delta = compare_briefs(current, prior)
    assert delta["brightened"] == []
    assert delta["unchanged_count"] == 1
