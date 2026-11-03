"""Run: python -m pip install pytest httpx  then  python -m pytest -q   (from backend/). No API keys needed: providers are faked."""
import json
import pipeline

MODULE = ("Araling Panlipunan 9 Module. Paikot na Daloy ng Ekonomiya. " * 5 +
          "Learning Competency: Naipapaliwanag ang kahulugan ng paikot na daloy ng ekonomiya. Content Standard: Naipamamalas ang pag-unawa sa paikot na daloy. "
          "Objectives: Natutukoy ang mga sektor sa paikot na daloy. Naiuugnay ang daloy sa pang-araw-araw na buhay. References: Ekonomiks Module 3, DepEd 2026. " * 2)
COMP = "Naipapaliwanag ang kahulugan ng paikot na daloy ng ekonomiya."
STD = "Naipamamalas ang pag-unawa sa paikot na daloy."
OBJ = "Natutukoy ang mga sektor sa paikot na daloy."
OBJ2 = "Naiuugnay ang daloy sa pang-araw-araw na buhay."
CONF = {"competencies": [COMP], "standards": [STD], "objectives": [OBJ], "references": ["Ekonomiks Module 3, DepEd 2026."]}
ANS = {"lessonTitle": "Paikot na Daloy", "learningArea": "AP 9", "teacherName": "G. Cruz", "gradeSection": "9-A", "noOfSessions": "2",
       "preLesson": "balik aral sa kita", "flow": ["session 1 pangkatang gawain", "session 2 pagtalakay"], "formative": "", "learnerContext": "mahilig sila sa group work"}


def fake(extract=None, organize=None, grammar=None):
    def call(task, system, user):
        if task == "logic" and "EXTRACT" in system: return extract or {}
        if task == "logic": return organize or {}
        if task == "grammar": return grammar if grammar is not None else {"fields": json.loads(user)}
        raise AssertionError(task)
    return call


def test_extract_drops_quotes_not_in_module():
    out = pipeline.extract_intentions(MODULE, fake(extract={"competencies": [COMP, "Isang competency na gawa-gawa lang ng AI."], "standards": [STD], "objectives": [OBJ]}))
    assert out["competencies"] == [COMP] and out["standards"] == [STD] and out["objectives"] == [OBJ] and out["dropped"] == 1


def test_blank_answer_stays_blank_even_if_ai_fills_it():
    org = {"preLesson": "Balik-aral sa kita ng mga mag-aaral.", "formative": "AI wrote a quiz nobody asked for", "flow": ["Session 1: pangkatang gawain", "Session 2: pagtalakay"]}
    r = pipeline.build_draft(CONF, ANS, MODULE, fake(organize=org))
    assert r["draft"]["assessment"]["formative"]["text"] == ""
    assert any(f["field"] == "assessment.formative" for f in r["check"]["flags"])
    assert r["draft"]["experience"]["preLesson"]["source"] == "ai-organized"


def test_draft_follows_template_sections_and_has_no_invented_fields():
    d = pipeline.build_draft(CONF, ANS, MODULE, fake())["draft"]
    assert list(d) == ["mode", "header", "intentions", "experience", "assessment", "waysForward"]
    assert list(d["header"]) == ["lessonTitle", "learningArea", "teacherName", "gradeSection", "noOfSessions", "schoolName", "division", "region", "teachingDates", "references"]
    assert list(d["intentions"]) == ["competencies", "standards", "objectives", "learnerContext"]
    assert list(d["experience"]) == ["preLesson", "flow", "learningResources", "integration"]


def test_ai_added_number_is_rejected_and_teacher_text_kept():
    r = pipeline.build_draft(CONF, ANS, MODULE, fake(organize={"preLesson": "Balik-aral sa kita ng 85 porsyento", "flow": ["a", "b"]}))
    assert r["draft"]["experience"]["preLesson"]["text"] == "balik aral sa kita"
    assert any(n["field"] == "preLesson" for n in r["notes"])


def test_flow_length_mismatch_falls_back_to_teacher():
    r = pipeline.build_draft(CONF, ANS, MODULE, fake(organize={"flow": ["only one"]}))
    assert [x["text"] for x in r["draft"]["experience"]["flow"]] == ANS["flow"]


def test_grammar_cannot_change_content():
    bad = {"fields": {"learnerContext": "mahilig sila sa group work at may 40 na mag-aaral sa klase na ito"}}
    r = pipeline.build_draft(CONF, ANS, MODULE, fake(grammar=bad))
    assert r["draft"]["intentions"]["learnerContext"]["text"] == "mahilig sila sa group work"


def test_locked_fields_are_the_confirmed_text_and_tampering_fails_check():
    d = pipeline.build_draft(CONF, ANS, MODULE, fake())["draft"]
    assert d["intentions"]["competencies"]["text"] == COMP and d["intentions"]["competencies"]["source"] == "extracted"
    d["intentions"]["competencies"]["text"] = "AI rewrote this competency"
    chk = pipeline.check_draft(d, pipeline.make_conf(CONF), MODULE)
    assert chk["status"] == "fail" and any(f["field"] == "intentions.competencies" for f in chk["flags"])


def test_daily_mode_splits_by_day_and_locks_each_day():
    conf = {"competencies": [[COMP], [COMP], [], [], []], "standards": [[STD], [], [], [], []], "objectives": [[OBJ], [OBJ2], [], [], []]}
    r = pipeline.build_draft(conf, ANS, MODULE, fake(), mode="daily")
    c = r["draft"]["intentions"]["competencies"]
    assert r["draft"]["mode"] == "daily" and c["days"] == [COMP, COMP, "", "", ""]
    assert r["draft"]["intentions"]["objectives"]["days"][1] == OBJ2
    assert not any(f["level"] == "fail" and f["field"].startswith("intentions") for f in r["check"]["flags"])
    r["draft"]["intentions"]["objectives"]["days"][1] = "AI changed day 2"
    assert pipeline.check_draft(r["draft"], pipeline.make_conf(conf, "daily"), MODULE)["status"] == "fail"


def test_daily_mode_rejects_flat_lists():
    try: pipeline.build_draft(CONF, ANS, MODULE, fake(), mode="daily"); assert False
    except ValueError: pass


def test_cannot_draft_without_confirmed_competency():
    try: pipeline.build_draft({"competencies": [], "objectives": [OBJ]}, ANS, MODULE, fake()); assert False
    except ValueError: pass


def test_providers_down_still_returns_teacher_text():
    def boom(*a): raise RuntimeError("down")
    r = pipeline.build_draft(CONF, ANS, MODULE, boom)
    assert r["draft"]["experience"]["preLesson"]["text"] == "balik aral sa kita" and len(r["notes"]) == 2


def test_review_unverifiable_quote_is_never_a_hard_fail():
    r = pipeline.build_draft(CONF, ANS, MODULE, fake())["draft"]
    out = pipeline.review_draft(r, lambda t, s, u: {"flags": [{"level": "fail", "field": "x", "quote": "text that is not in the draft", "message": "m"}]})
    assert out["flags"][0]["level"] == "warn" and out["flags"][0]["quote_verified"] is False


def test_endpoints(monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setattr(main, "call_task", fake(extract={"competencies": [COMP], "objectives": [OBJ]}))
    c = TestClient(main.app)
    assert c.post("/api/extract-intentions", json={"moduleText": MODULE}).json()["competencies"] == [COMP]
    assert c.post("/api/extract-intentions", json={"moduleText": "short"}).status_code == 400
    r = c.post("/api/draft", json={"confirmed": CONF, "answers": ANS, "moduleText": MODULE}).json()
    assert r["check"]["status"] in ("fail", "review", "pass") and "draft" in r
    assert c.post("/api/draft", json={"confirmed": {}, "answers": ANS}).status_code == 400
    assert c.post("/api/check-draft", json={"draft": r["draft"], "confirmed": CONF, "moduleText": MODULE}).json()["flags"] is not None
    daily = {"competencies": [[COMP]] * 5, "standards": [[STD]] * 5, "objectives": [[OBJ]] * 5}
    rd = c.post("/api/draft", json={"confirmed": daily, "answers": ANS, "moduleText": MODULE, "mode": "daily"}).json()
    assert rd["draft"]["mode"] == "daily"
    assert c.post("/api/check-draft", json={"draft": rd["draft"], "confirmed": daily, "mode": "daily", "moduleText": MODULE}).json()["fail"] >= 0