"""API-level tests: DOCX export (letterhead + logos), abuse guard, security headers. No API keys needed.
Run from backend/:  python -m pytest -q"""
import base64, zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
import pipeline
from test_pipeline import ANS, CONF, MODULE, fake

client = TestClient(main.app)


def png_data_url(color=(193, 98, 43), size=(60, 60)) -> str:
    buf = BytesIO(); Image.new("RGB", size, color).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def draft_with(**header):
    return pipeline.build_draft(CONF, {**ANS, **header}, MODULE, fake())["draft"]


def docx_of(draft, logos=None):
    r = client.post("/api/export-docx", json={**draft, **({"logos": logos} if logos is not None else {})})
    assert r.status_code == 200, r.text
    z = zipfile.ZipFile(BytesIO(r.content))
    return z.read("word/document.xml").decode("utf-8"), [n for n in z.namelist() if n.startswith("word/media/")]


@pytest.fixture(autouse=True)
def clean_limits():
    main._ip_hits.clear(); main._all_hits.clear()
    yield
    main._ip_hits.clear(); main._all_hits.clear()


def test_new_header_text_fields_survive_the_pipeline_as_teacher_text():
    h = draft_with(schoolName="Castillejos National High School", division="Zambales", region="Region III", teachingDates="Nov 3-7")["header"]
    assert h["schoolName"] == {"text": "Castillejos National High School", "source": "teacher"}
    assert h["teachingDates"]["text"] == "Nov 3-7"


def test_export_includes_letterhead_text_and_both_logos():
    xml, media = docx_of(draft_with(schoolName="Castillejos National High School", division="Zambales", region="Region III"), {"left": png_data_url(), "right": png_data_url((20, 60, 160))})
    assert "Republic of the Philippines" in xml and "Department of Education" in xml
    assert "Castillejos National High School" in xml and "Region III" in xml
    assert len(media) == 2


def test_export_without_letterhead_info_has_no_letterhead_and_still_works():
    xml, media = docx_of(draft_with())
    assert "Republic of the Philippines" not in xml and media == []
    assert "Lesson Title" in xml and "Prepared by" in xml


def test_teaching_dates_row_only_appears_when_filled():
    assert "Teaching Dates" not in docx_of(draft_with())[0]
    assert "Teaching Dates" in docx_of(draft_with(teachingDates="Nov 3-7"))[0]


@pytest.mark.parametrize("bad", ["", "javascript:alert(1)", "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=", "data:image/png;base64,@@@not-base64@@@", "data:image/png;base64," + "A" * 3_100_000, "data:image/png;base64," + base64.b64encode(b"not an image").decode()])
def test_bad_logos_are_skipped_not_fatal(bad):
    xml, media = docx_of(draft_with(schoolName="CNHS"), {"left": bad, "right": bad})
    assert media == [] and "CNHS" in xml


def test_export_rejects_non_draft():
    assert client.post("/api/export-docx", json={"nope": 1}).status_code == 400


def test_ai_endpoints_are_rate_limited_per_ip(monkeypatch):
    monkeypatch.setattr(main, "RATE_PER_IP", 3)
    codes = [client.post("/api/draft", json={}).status_code for _ in range(5)]
    assert codes[:3] == [400, 400, 400] and codes[3:] == [429, 429]  # 400 = reached the handler (empty body), 429 = blocked first
    assert client.post("/api/export-docx", json={"nope": 1}).status_code == 400  # cheap endpoints are not counted


def test_global_limit_holds_even_when_every_request_claims_a_new_ip(monkeypatch):
    monkeypatch.setattr(main, "RATE_GLOBAL", 3)
    codes = [client.post("/api/draft", json={}, headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(5)]
    assert codes == [400, 400, 400, 429, 429]


def test_security_headers_present():
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY" and r.headers["referrer-policy"] == "same-origin"


def test_debug_surface_is_closed_when_debug_is_off(monkeypatch):
    monkeypatch.setattr(main, "DEBUG", False)  # your local backend/.env may have DEBUG_ENDPOINTS=1; production must not
    assert client.get("/api/debug/probe-all").status_code == 404
    assert client.get("/api/debug/provider/gemini").status_code == 404
    assert "last_error" not in next(iter(client.get("/api/health").json()["providers"].values()))
