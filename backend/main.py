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
from pydantic import BaseModel, Field

from prompts import SYSTEM_PROMPT

load_dotenv(Path(__file__).resolve().parent / ".env")  # always backend/.env, whatever folder uvicorn starts from
log = logging.getLogger("bear-light"); logging.basicConfig(level=logging.INFO)
app = FastAPI()
ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500,http://127.0.0.1:5500").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])

# ---------- providers ----------
OPENAI_COMPAT = {  # name: (base_url, key env, model env, default model). Defaults are overridden by backend/.env
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY", "MISTRAL_MODEL", "mistral-small-latest"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "GROQ_MODEL", "openai/gpt-oss-120b"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
}
GEMINI_DEFAULT_MODEL = "gemini-3.6-flash"
TIER1, TIER2 = ["gemini", "mistral"], ["groq", "openrouter"]  # providers with no key in .env are skipped automatically
TIMEOUT_SECONDS = 90
RATE_LIMIT_COOLDOWN, DEAD_COOLDOWN = 60, 600  # 429 -> 1 min; 401/403/404 (bad key / wrong model ID) -> 10 min
cooldown_until: dict[str, float] = {}  # provider -> unix time when it may be tried again


def key_for(name: str) -> str:
    return os.getenv("GEMINI_API_KEY" if name == "gemini" else OPENAI_COMPAT[name][1], "").strip()


def model_for(name: str) -> str:
    if name == "gemini": return os.getenv("GEMINI_MODEL", GEMINI_DEFAULT_MODEL)
    return os.getenv(OPENAI_COMPAT[name][2], OPENAI_COMPAT[name][3])


def parse_json(text: str) -> dict:
    """Models sometimes wrap JSON in ``` fences or add chatter. Strip that, then require an object."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        out = json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a == -1 or b <= a: raise ValueError("model did not return JSON")
        out = json.loads(t[a:b + 1])
    if not isinstance(out, dict): raise ValueError("model JSON is not an object")
    return out


def call_provider(name: str, system: str, user: str) -> tuple[dict, int]:
    """Returns (parsed_json, total_tokens). Raises on failure."""
    key = key_for(name)
    if not key: raise RuntimeError(f"{name}: API key is missing")
    if name == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000))  # timeout is in ms
        r = client.models.generate_content(model=model_for(name), contents=user,
                                           config={"system_instruction": system, "response_mime_type": "application/json"})
        return parse_json(r.text), (getattr(r.usage_metadata, "total_token_count", 0) or 0)
    base = OPENAI_COMPAT[name][0]
    r = OpenAI(base_url=base, api_key=key, timeout=TIMEOUT_SECONDS, max_retries=0).chat.completions.create(  # max_retries=0: OUR fallback handles failures
        model=model_for(name), response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return parse_json(r.choices[0].message.content), (r.usage.total_tokens if r.usage else 0)


def status_of(err: Exception):
    return getattr(err, "status_code", None) or getattr(err, "code", None)  # openai SDK: status_code, google-genai: code


def is_rate_limit(err: Exception) -> bool:
    m = str(err).lower()
    return status_of(err) == 429 or any(k in m for k in ("429", "rate limit", "quota", "resource_exhausted"))


def cooldown_for(err: Exception) -> int:
    if is_rate_limit(err): return RATE_LIMIT_COOLDOWN
    return DEAD_COOLDOWN if status_of(err) in (401, 403, 404) else 0


def provider_order(provider: str, task: str) -> list[str]:
    seq = [p for p in ((TIER2 + TIER1) if task == "partial_edit" else (TIER1 + TIER2)) if key_for(p)]
    if provider != "auto" and provider in seq: seq = [provider] + [p for p in seq if p != provider]
    now = time.time()  # providers on cooldown go last instead of being hammered
    ready = [p for p in seq if cooldown_until.get(p, 0) <= now]
    return ready + [p for p in seq if p not in ready]


@app.get("/api/health")
def health():
    """Open http://localhost:8000/api/health to check which keys loaded and which models are set. Never returns keys."""
    now = time.time()
    return {"ok": True, "providers": {p: {"configured": bool(key_for(p)), "model": model_for(p), "cooldown_seconds": max(0, int(cooldown_until.get(p, 0) - now))} for p in TIER1 + TIER2}}


# ---------- generate ----------
def S(n: int = 300):
    return Field("", max_length=n)


class GenerateRequest(BaseModel):
    gradeLevel: str = S(); subjectArea: str = S(); quarter: str = S(50); weekNumber: str = S(50); topic: str = S(3000)
    provider: str = S(30); taskType: str = S(30)
    schoolName: str = S(); teacherName: str = S(); region: str = S(); division: str = S(); teachingDates: str = S(); noOfSessions: str = S(100)
    references: str = S(3000); declarationOfAiUse: str = S(3000)
    leftLogoUrl: str = S(7_500_000); rightLogoUrl: str = S(7_500_000)  # base64 data URLs (5 MB images)
    attachedFile: dict | None = None


SECTIONS = {  # section -> keys that must exist (strings); missing ones are filled with ""
    "objectives": ["contentStandard", "performanceStandard"], "content": ["topic", "subtopic", "integrationValues", "hotsSkills"],
    "resources": ["teacherGuidePages", "learnerMaterialPages", "textbookPages", "additionalMaterials"],
    "procedures": [f"{c}_{n}" for c, n in zip("abcdefghi", ["review", "purpose", "examples", "discussion", "mastery", "application", "generalization", "evaluation", "remediation"])],
    "remarks": ["notes"], "reflection": ["learners80Percent", "learnersNeedingRemediation", "remediationEffective", "learnersContinuingRemediation", "effectiveTeachingStrategies", "difficultiesEncountered", "innovationsUsed"],
}
HEADER_FIELDS = ["schoolName", "teacherName", "gradeLevel", "quarter", "weekNumber", "division", "region", "teachingDates", "noOfSessions", "references", "declarationOfAiUse"]


def build_dll(req: GenerateRequest, parsed: dict, provider: str, fallback: bool) -> dict:
    # Header comes ONLY from what the teacher typed. Model-written header values are ignored, so a blank
    # Teacher/School field stays blank instead of showing an invented name.
    header = {k: getattr(req, k) for k in HEADER_FIELDS}
    header.update(learningArea=req.subjectArea, leftLogoUrl=req.leftLogoUrl, rightLogoUrl=req.rightLogoUrl)
    topic = req.topic.strip()
    dll = {"id": f"dll-{int(time.time() * 1000)}", "title": f"{req.gradeLevel} {req.subjectArea} - {topic[:35]}{'...' if len(topic) > 35 else ''}",
           "dateCreated": date.today().isoformat(), "providerUsed": provider, "tierUsed": "tier1" if provider in TIER1 else "tier2",
           "fallbackOccurred": fallback, "header": header}
    for sec, keys in SECTIONS.items():
        got = parsed.get(sec) if isinstance(parsed.get(sec), dict) else {}
        dll[sec] = {k: str(got.get(k, "") or "") for k in keys}
    obj = parsed.get("objectives") if isinstance(parsed.get("objectives"), dict) else {}
    comps = obj.get("learningCompetencies") or []
    dll["objectives"]["learningCompetencies"] = [str(c) for c in comps] if isinstance(comps, list) else [str(comps)]
    if not dll["content"]["topic"]: dll["content"]["topic"] = topic
    if req.attachedFile: dll["resources"]["attachedFileName"] = str(req.attachedFile.get("name", ""))[:200]
    return dll


def build_user_prompt(req: GenerateRequest) -> str:
    lines = [f"- Grade Level: {req.gradeLevel}", f"- Subject / Learning Area: {req.subjectArea}", f"- Term: {req.quarter}",
             f"- Week Number: {req.weekNumber}", f"- Topic / Competency Prompt: {req.topic}"]
    if req.schoolName: lines.append(f"- School Name: {req.schoolName}")
    if req.teacherName: lines.append(f"- Teacher Name: {req.teacherName}")
    user = "Create a DepEd MATATAG Daily Lesson Log (DLL) for:\n" + "\n".join(lines)
    user += "\n\nDo not invent school names, teacher names, dates, or competency codes. Use an empty string for any header field you were not given."
    if req.attachedFile:
        f = req.attachedFile
        user += f"\n\nATTACHED REFERENCE DOCUMENT (Uploaded by Teacher):\nFilename: {str(f.get('name', ''))[:200]}"
        if f.get("textContent"): user += f"\nExtracted File Snippet:\n\"\"\"{str(f['textContent'])[:8000]}\"\"\""
        user += "\nPlease integrate relevant concepts, activity ideas, and references from this file into the procedures and resources."
    return user


@app.post("/api/generate-dll")
def generate(req: GenerateRequest):
    if not req.topic.strip():
        return JSONResponse({"error": "Pakilagay ang paksa o competency."}, status_code=400)
    order = provider_order(req.provider, req.taskType)
    if not order:
        log.error("No provider has an API key. Check backend/.env (open /api/health to see what loaded).")
        return JSONResponse({"error": "Walang naka-set na AI provider. Ilagay ang API key sa backend/.env at i-restart ang server."}, status_code=503)
    user, tried = build_user_prompt(req), []
    for i, p in enumerate(order):
        t0 = time.time()
        try:
            parsed, tokens = call_provider(p, SYSTEM_PROMPT, user)
            log.info("provider=%s model=%s ok latency_ms=%d tokens=%d fallback=%s", p, model_for(p), (time.time() - t0) * 1000, tokens, i > 0)
            return build_dll(req, parsed, p, i > 0)
        except Exception as e:
            cd = cooldown_for(e)
            if cd: cooldown_until[p] = time.time() + cd
            tried.append({"provider": p, "reason": "rate_limited" if is_rate_limit(e) else "error"})
            log.warning("provider=%s model=%s FAILED latency_ms=%d rate_limited=%s cooldown_s=%d err=%s", p, model_for(p), (time.time() - t0) * 1000, is_rate_limit(e), cd, str(e)[:200])
    return JSONResponse({"error": "Hindi maiproseso ang DLL ngayon dahil lahat ng AI provider ay hindi available o naabot ang limitasyon. Subukan muli mamaya.", "tried": tried}, status_code=503)


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
            d = Document(BytesIO(data))
            text = "\n".join([p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])  # include table cells
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
    doc = Document(); h = dll.get("header") or {}
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
    o = dll.get("objectives") or {}
    table("Intentions", [("Content Standard", o.get("contentStandard")), ("Performance Standard", o.get("performanceStandard")),
                         ("Learning Competencies", "\n".join(str(c) for c in (o.get("learningCompetencies") or [])))])
    for sec, title in [("content", "Nilalaman"), ("resources", "Learning Resources"), ("procedures", "Learning Experience"), ("remarks", "Remarks"), ("reflection", "Reflection")]:
        table(title, list((dll.get(sec) or {}).items()))
    buf = BytesIO(); doc.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": 'attachment; filename="Bear-Light-DLL.docx"'})


FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND.exists(): app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")  # keep LAST