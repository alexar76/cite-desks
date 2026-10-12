import pytest

from app.geo import BBoxError, is_live_hotspot, point_in_bbox, validate_bbox


def test_valid_bbox() -> None:
    box = validate_bbox(-125, 32, -114, 42)
    assert box["west"] == -125


def test_rejects_inverted_bbox() -> None:
    with pytest.raises(BBoxError):
        validate_bbox(-114, 32, -125, 42)


def test_rejects_oversized_bbox() -> None:
    with pytest.raises(BBoxError):
        validate_bbox(-130, 20, -70, 55)


def test_point_in_bbox() -> None:
    box = validate_bbox(-125, 32, -114, 42)
    assert point_in_bbox(37.6, -121.3, box)
    assert not point_in_bbox(10.0, -121.3, box)


def test_sim_hotspot_is_not_live() -> None:
    assert is_live_hotspot({"live": True, "mode": "live"})
    assert not is_live_hotspot({"live": False, "mode": "sim"})
    assert not is_live_hotspot({"live": True, "mode": "sim"})
