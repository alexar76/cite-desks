import hashlib
import io
import zipfile

from fastapi.testclient import TestClient

from app.citepack import build_cite_pack
from app.seed import BRIEF_ID, DEMO_EMAIL, DEMO_PASSWORD


def test_cite_pack_zip_has_checksums() -> None:
    brief = {
        "id": "brf_x",
        "run_id": "run_x",
        "generated_at": "2026-08-16T00:00:00+00:00",
        "evidence_status": "live_evidence",
        "live_fire_detection_count": 1,
        "summary": "One LIVE point.",
        "legal_strip": "Monitoring aid only.",
        "badges": ["NOT A PERIMETER"],
        "hotspots": [{"id": "a", "lat": 37.1, "lon": -121.1, "brightness_k": 350, "confidence": 80, "satellite": "N20"}],
        "watch": {"name": "Box", "bbox": {"west": -122, "south": 36, "east": -121, "north": 38}},
        "receipt": {"digest": "abc", "signature_status": "signed", "emberline_verified": False},
        "delta": {"kind": "first_run", "summary": "No prior completed brief on this watch."},
    }
    blob = build_cite_pack(brief=brief, raw_fire_weather={"ok": True}, raw_watchbox=None)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = set(archive.namelist())
        assert {
            "00-README.txt",
            "01-cover.pdf",
            "02-brief.json",
            "03-delta.json",
            "04-receipt.json",
            "raw/fire_weather.json",
            "raw/watchbox.json",
            "SHA256SUMS",
        } <= names
        assert archive.read("01-cover.pdf")[:4] == b"%PDF"
        listed = archive.read("SHA256SUMS").decode()
        for line in listed.splitlines():
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    again = build_cite_pack(brief=brief, raw_fire_weather={"ok": True}, raw_watchbox=None)
    assert again == blob


def test_cite_pack_requires_auth(client: TestClient) -> None:
    assert client.get(f"/api/briefs/{BRIEF_ID}/cite-pack").status_code == 401


def test_cite_pack_download(client: TestClient) -> None:
    token = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}).json()["access_token"]
    response = client.get(f"/api/briefs/{BRIEF_ID}/cite-pack", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert client.get("/api/public/sample-cite-pack").status_code == 200
