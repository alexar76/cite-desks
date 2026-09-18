import json
from pathlib import Path

from app.briefs import BADGES, build_brief, evidence_status, live_hotspots, should_alert, sku_cogs

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


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


def test_live_brief_strips_sim_and_keeps_receipt() -> None:
    snapshot = json.loads((FIXTURES / "fire_weather_live.json").read_text())
    brief = build_brief(
        watch=_watch(),
        snapshot=snapshot,
        run_id="run_1",
        brief_id="brf_1",
        skus_used=["atlas.watchbox.check@v1", "atlas.fire.weather@v1"],
    )
    assert brief["evidence_status"] == "live_evidence"
    assert all(h["mode"] == "live" for h in brief["hotspots"])
    assert not any(h["id"] == "sim-should-never-appear" for h in brief["hotspots"])
    assert brief["receipt"]["digest"]
    assert "emberline_verified" in brief["receipt"]
    assert brief["badges"] == list(BADGES)
    assert "not an emergency service" in " ".join(brief["limitations"]).lower()
    assert brief["cogs_usd"] == 0.10
    assert brief["brightest"]["brightness_k"] == 367.0
    assert brief["weather"]["place"] == "SFO Airport"


def test_empty_snapshot_is_fail_closed() -> None:
    snapshot = json.loads((FIXTURES / "fire_weather_empty.json").read_text())
    assert evidence_status(snapshot) == "no_live_evidence"
    assert live_hotspots(snapshot) == []
    brief = build_brief(
        watch=_watch(),
        snapshot=snapshot,
        run_id="run_2",
        brief_id="brf_2",
        skus_used=["atlas.fire.weather@v1"],
    )
    assert brief["evidence_status"] == "no_live_evidence"
    assert brief["hotspots"] == []
    assert brief["live_fire_detection_count"] == 0
    assert not should_alert(brief, live_hotspots_threshold=1, brightness_k=0)


def test_alert_respects_brightness_threshold() -> None:
    snapshot = json.loads((FIXTURES / "fire_weather_live.json").read_text())
    brief = build_brief(
        watch=_watch(),
        snapshot=snapshot,
        run_id="run_3",
        brief_id="brf_3",
        skus_used=["atlas.fire.weather@v1"],
    )
    assert should_alert(brief, live_hotspots_threshold=1, brightness_k=360)
    assert not should_alert(brief, live_hotspots_threshold=1, brightness_k=400)


def test_cogs_table() -> None:
    assert sku_cogs(["atlas.fire.weather@v1"]) == 0.08
    assert sku_cogs(["atlas.watchbox.check@v1"]) == 0.02
