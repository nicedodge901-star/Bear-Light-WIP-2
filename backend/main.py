"""Bear-Light backend. Run: uvicorn main:app --reload --port 8000  (from backend/)
Serves the API and the static frontend, so http://localhost:8000 is the whole app."""
import base64, json, logging, os, re, time
from datetime import date
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

from prompts import SYSTEM_PROMPT

load_dotenv()
log = logging.getLogger("bear-light"); logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # dev only: restrict before deploy

# ---------- providers ----------
OPENAI_COMPAT = {  # name: (base_url, key env, model env, default model)
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "GROQ_MODEL", "llama-3.3-70b-versatile"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "CEREBRAS_MODEL", "llama-3.3-70b"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
}
TIER1, TIER2 = ["gemini", "groq"], ["cerebras", "openrouter"]
COOLDOWN_SECONDS = 60
cooldown_until: dict[str, float] = {}  # provider -> unix time when it may be tried again


def call_provider(name: str, system: str, user: str) -> tuple[dict, int]:
    """Returns (parsed_json, total_tokens). Raises on failure."""
    if name == "gemini":
        from google import genai
        key = os.getenv("GEMINI_API_KEY")
        if not key: raise RuntimeError("GEMINI_API_KEY is missing")
        r = genai.Client(api_key=key).models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"), contents=user,
            config={"system_instruction": system, "response_mime_type": "application/json"})
        tokens = getattr(r.usage_metadata, "total_token_count", 0) or 0
        return json.loads(re.sub(r"^```json\s*|```\s*$", "", (r.text or "").strip())), tokens
    base, key_env, model_env, default = OPENAI_COMPAT[name]
    key = os.getenv(key_env)
    if not key: raise RuntimeError(f"{key_env} is missing")
    r = OpenAI(base_url=base, api_key=key).chat.completions.create(
        model=os.getenv(model_env, default), response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return json.loads(r.choices[0].message.content), (r.usage.total_tokens if r.usage else 0)


def is_rate_limit(err: Exception) -> bool:
    m = str(err).lower()
    return getattr(err, "status_code", None) == 429 or any(k in m for k in ("429", "rate limit", "quota", "resource_exhausted"))


def provider_order(provider: str, task: str) -> list[str]:
    seq = (TIER2 + TIER1) if task == "partial_edit" else (TIER1 + TIER2)
    if provider != "auto" and provider in seq: seq = [provider] + [p for p in seq if p != provider]
    now = time.time()  # rate-limit aware: providers on cooldown go last instead of being hammered
    return [p for p in seq if cooldown_until.get(p, 0) <= now] + [p for p in seq if cooldown_until.get(p, 0) > now]


# ---------- generate ----------
class GenerateRequest(BaseModel):
    gradeLevel: str = ""; subjectArea: str = ""; quarter: str = ""; weekNumber: str = ""; topic: str = ""
    provider: str = "auto"; taskType: str = "full_generation"
    schoolName: str = ""; teacherName: str = ""; region: str = ""; division: str = ""; teachingDates: str = ""
    noOfSessions: str = ""; references: str = ""; declarationOfAiUse: str = ""
    leftLogoUrl: str = ""; rightLogoUrl: str = ""
    attachedFile: dict | None = None


SECTIONS = {  # section -> keys that must exist (strings); missing ones are filled with ""
    "objectives": ["contentStandard", "performanceStandard"], "content": ["topic", "subtopic", "integrationValues", "hotsSkills"],
    "resources": ["teacherGuidePages", "learnerMaterialPages", "textbookPages", "additionalMaterials"],
    "procedures": [f"{c}_{n}" for c, n in zip("abcdefghi", ["review", "purpose", "examples", "discussion", "mastery", "application", "generalization", "evaluation", "remediation"])],
    "remarks": ["notes"], "reflection": ["learners80Percent", "learnersNeedingRemediation", "remediationEffective", "learnersContinuingRemediation", "effectiveTeachingStrategies", "difficultiesEncountered", "innovationsUsed"],
}


def build_dll(req: GenerateRequest, parsed: dict, provider: str, fallback: bool) -> dict:
    user_header = {k: getattr(req, k) for k in ["schoolName", "teacherName", "gradeLevel", "quarter", "weekNumber", "division", "region", "teachingDates", "noOfSessions", "references", "declarationOfAiUse"] if getattr(req, k)}
    header = {**{k: "" for k in user_header}, **(parsed.get("header") or {}), **user_header,  # user input WINS over model output
              "learningArea": req.subjectArea, "leftLogoUrl": req.leftLogoUrl, "rightLogoUrl": req.rightLogoUrl}
    dll = {"id": f"dll-{int(time.time() * 1000)}", "title": f"{req.gradeLevel} {req.subjectArea} - {req.topic[:35]}...",
           "dateCreated": date.today().isoformat(), "providerUsed": provider, "tierUsed": "tier1" if provider in TIER1 else "tier2",
           "fallbackOccurred": fallback, "header": header}
    for sec, keys in SECTIONS.items():
        got = parsed.get(sec) if isinstance(parsed.get(sec), dict) else {}
        dll[sec] = {k: str(got.get(k, "") or "") for k in keys}
    comps = (parsed.get("objectives") or {}).get("learningCompetencies") or []
    dll["objectives"]["learningCompetencies"] = [str(c) for c in comps] if isinstance(comps, list) else [str(comps)]
    if not dll["content"]["topic"]: dll["content"]["topic"] = req.topic
    if req.attachedFile: dll["resources"]["attachedFileName"] = req.attachedFile.get("name", "")
    return dll


@app.post("/api/generate-dll")
def generate(req: GenerateRequest):
    if not req.topic.strip():
        return JSONResponse({"error": "Pakilagay ang paksa o competency."}, status_code=400)
    user = (f"Create a DepEd MATATAG Daily Lesson Log (DLL) for:\n- Grade Level: {req.gradeLevel}\n- Subject / Learning Area: {req.subjectArea}\n"
            f"- Term: {req.quarter}\n- Week Number: {req.weekNumber}\n- Topic / Competency Prompt: {req.topic}\n- School Name: {req.schoolName}\n- Teacher Name: {req.teacherName}")
    if req.attachedFile:
        f = req.attachedFile
        user += f"\n\nATTACHED REFERENCE DOCUMENT (Uploaded by Teacher):\nFilename: {f.get('name')}"
        if f.get("textContent"): user += f"\nExtracted File Snippet:\n\"\"\"{f['textContent']}\"\"\""
        user += "\nPlease integrate relevant concepts, activity ideas, and references from this file into the procedures and resources."
    for i, p in enumerate(provider_order(req.provider, req.taskType)):
        t0 = time.time()
        try:
            parsed, tokens = call_provider(p, SYSTEM_PROMPT, user)
            log.info("provider=%s ok latency_ms=%d tokens=%d fallback=%s", p, (time.time() - t0) * 1000, tokens, i > 0)
            return build_dll(req, parsed, p, i > 0)
        except Exception as e:
            if is_rate_limit(e): cooldown_until[p] = time.time() + COOLDOWN_SECONDS
            log.warning("provider=%s FAILED latency_ms=%d rate_limited=%s err=%s", p, (time.time() - t0) * 1000, is_rate_limit(e), str(e)[:200])
    return JSONResponse({"error": "Hindi maiproseso ang DLL ngayon dahil lahat ng AI provider ay hindi available o naabot ang limitasyon. Subukan muli mamaya."}, status_code=503)


# ---------- reference-file text extraction ----------
@app.post("/api/extract-text")
async def extract_text(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 20 * 1024 * 1024: return JSONResponse({"error": "Masyadong malaki ang file (max 20MB)."}, status_code=413)
    name = (file.filename or "").lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            text = "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(data)).pages[:30])
        elif name.endswith(".docx"):
            from docx import Document
            text = "\n".join(p.text for p in Document(BytesIO(data)).paragraphs)
        elif name.endswith(".pptx"):
            from pptx import Presentation
            text = "\n".join(sh.text_frame.text for s in Presentation(BytesIO(data)).slides for sh in s.shapes if sh.has_text_frame)
        elif name.endswith((".txt", ".md", ".csv", ".json")):
            text = data.decode("utf-8", errors="ignore")
        else:
            return JSONResponse({"error": "Hindi suportado ang file na ito (.doc/.ppt na luma). I-save bilang .docx/.pptx."}, status_code=415)
    except Exception as e:
        return JSONResponse({"error": f"Hindi mabasa ang file: {str(e)[:100]}"}, status_code=422)
    return {"name": file.filename, "textContent": text.strip()[:8000]}


# ---------- DOCX export (simplified layout: NOT identical to the original docx-export.ts) ----------
@app.post("/api/export-docx")
def export_docx(dll: dict):
    from docx import Document
    from docx.shared import Inches
    doc = Document(); h = dll.get("header", {})
    for key in ("leftLogoUrl", "rightLogoUrl"):
        m = re.match(r"data:image/\w+;base64,(.+)", h.get(key) or "")
        if m:
            try: doc.add_picture(BytesIO(base64.b64decode(m.group(1))), width=Inches(0.9))
            except Exception: pass  # skip unsupported image types (e.g. svg/webp)
    doc.add_heading("Daily Lesson Log", 0)

    def table(title, rows):
        doc.add_heading(title, 2); t = doc.add_table(rows=0, cols=2); t.style = "Table Grid"
        for label, val in rows:
            c = t.add_row().cells; c[0].text, c[1].text = label, str(val or "")
    table("Header", [("Paaralan", h.get("schoolName")), ("Guro", h.get("teacherName")), ("Antas", h.get("gradeLevel")), ("Asignatura", h.get("learningArea")),
                     ("Term / Week", f"{h.get('quarter', '')} / {h.get('weekNumber', '')}"), ("Petsa", h.get("teachingDates")), ("Division", h.get("division")),
                     ("Region", h.get("region")), ("Sesyon", h.get("noOfSessions")), ("References", h.get("references")), ("Declaration of AI use", h.get("declarationOfAiUse"))])
    o = dll.get("objectives", {})
    table("Intentions", [("Content Standard", o.get("contentStandard")), ("Performance Standard", o.get("performanceStandard")), ("Learning Competencies", "\n".join(o.get("learningCompetencies", [])))])
    for sec, title in [("content", "Nilalaman"), ("resources", "Learning Resources"), ("procedures", "Learning Experience"), ("remarks", "Remarks"), ("reflection", "Reflection")]:
        table(title, list((dll.get(sec) or {}).items()))
    buf = BytesIO(); doc.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": 'attachment; filename="Bear-Light-DLL.docx"'})


FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND.exists(): app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")  # keep LAST
