"""Bear-Light ILAW pipeline: extract -> organize -> grammar -> check.
Structure follows the school-issued ILAW template (HEADER, Intentions, Learning Experience, Assessment, Ways Forward),
Weekly or Daily (Daily splits competency/standards/objectives into Day 1-5).
Rules are enforced in CODE, not only in prompts:
  * competencies/standards/objectives come ONLY from the module (verbatim quotes, verified) and are locked
  * a blank teacher answer stays blank: the AI is never asked to fill it
  * the AI may not add numbers; the grammar pass may not add or drop content
`call(task, system, user) -> dict` is injected (main.py supplies it), so this file runs in tests with no API keys."""
import json, re

from prompts import EXTRACT_PROMPT, ORGANIZE_PROMPT, GRAMMAR_PROMPT, REVIEW_ILAW_PROMPT

ORGANIZABLE = ["preLesson", "learningResources", "integration", "formative", "extendedLearning"]
TEACHER_ONLY = ["learnerContext", "reflections"]
HEADER = ["lessonTitle", "learningArea", "teacherName", "gradeSection", "noOfSessions"]
LOCKED = ("competencies", "standards", "objectives")
PLACEHOLDER = re.compile(r"^\s*(string|tbd|todo|lorem ipsum.*|\[.*\]|\.\.\.)\s*$", re.I)  # "N/A" is a legitimate answer, so it is NOT here
NUM = re.compile(r"\d+(?:[.,]\d+)?")
MODULE_CHARS = 60000  # how much module text the extractor sees
NOTE = "Istruktura at integridad lang ang sinusuri. Hindi nito pinapatunayan ang kalidad ng nilalaman o ang opisyal na pag-apruba ng DepEd."


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def toks(s) -> list[str]:
    return re.findall(r"\w+", str(s or "").lower())


def new_numbers(allowed_text: str, new_text: str) -> set:
    return set(NUM.findall(new_text)) - set(NUM.findall(allowed_text))


def _clean_list(v) -> list[str]:
    if isinstance(v, str): v = [v]
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def _by_day(v) -> list[list[str]]:
    if not isinstance(v, list) or any(not isinstance(x, list) for x in v):  # a flat list of strings would silently become one item per day
        raise ValueError("Sa Daily format, kailangan ng listahan para sa bawat araw (Day 1 hanggang Day 5).")
    days = [_clean_list(x) for x in v][:5]
    return days + [[] for _ in range(5 - len(days))]


def make_conf(confirmed: dict, mode: str = "weekly") -> dict:
    """Normalize the teacher-confirmed items. Daily mode: competencies/standards/objectives are 5 lists (Day 1-5)."""
    c, daily = confirmed or {}, mode == "daily"
    conf = {"mode": "daily" if daily else "weekly", "references": _clean_list(c.get("references")), "topic": _clean_list(c.get("topic"))}
    for k in LOCKED:
        if daily: conf[k + "_days"] = _by_day(c.get(k) or []); conf[k] = [x for d in conf[k + "_days"] for x in d]
        else: conf[k + "_days"] = None; conf[k] = _clean_list(c.get(k))
    return conf


# ---------- stage 1: extract (module -> verified verbatim quotes) ----------
def extract_intentions(module_text: str, call) -> dict:
    text = (module_text or "").strip()
    if len(text) < 200: raise ValueError("Masyadong maikli o hindi mabasa ang module. Subukan ang ibang file.")
    parsed = call("logic", EXTRACT_PROMPT, 'MODULE TEXT:\n"""\n' + text[:MODULE_CHARS] + '\n"""')
    hay, out, dropped = norm(text), {}, 0
    for key in ("topic", "competencies", "standards", "objectives", "references"):
        keep, seen = [], set()
        for q in _clean_list(parsed.get(key))[:12]:
            n = norm(q)
            if len(q) <= 600 and n in hay and n not in seen: keep.append(q); seen.add(n)  # must literally exist in the module
            else: dropped += 1
        out[key] = keep
    out["dropped"] = dropped
    return out


# ---------- stage 2: organize (teacher answers -> clearer text, nothing invented) ----------
def organize(seed: dict, flow_in: list, locked: dict, call) -> tuple[dict, list]:
    """Returns (organized, notes). Falls back to the teacher's own text whenever the AI output breaks a rule."""
    organized, notes = {}, []
    if not seed and not flow_in: return organized, notes
    payload = json.dumps({"locked_context": locked, "teacher_answers": {**seed, "flow": flow_in}}, ensure_ascii=False)
    allowed = payload + " " + " ".join(str(i + 1) for i in range(len(flow_in)))  # session numbers 1..n are allowed
    parsed = call("logic", ORGANIZE_PROMPT, payload)
    for k, own in seed.items():
        v = parsed.get(k)
        if not isinstance(v, str) or not v.strip(): continue
        v = v.strip()
        if new_numbers(allowed, v): notes.append({"field": k, "message": "Nagdagdag ang AI ng numero na wala sa sagot mo. Pinanatili ang orihinal mong teksto."})
        elif len(toks(v)) > 2.5 * len(toks(own)) + 10: notes.append({"field": k, "message": "Masyadong humaba ang gawa ng AI. Pinanatili ang orihinal mong teksto."})
        else: organized[k] = v
    if flow_in:
        fl = parsed.get("flow")
        ok = isinstance(fl, list) and len(fl) == len(flow_in) and all(isinstance(x, str) and x.strip() for x in fl)
        if ok and not any(new_numbers(allowed, x) for x in fl): organized["flow"] = [x.strip() for x in fl]
        else: notes.append({"field": "flow", "message": "Hindi tugma ang resulta ng AI sa mga sesyon mo. Pinanatili ang orihinal mong teksto."})
    return organized, notes


# ---------- stage 3: grammar (may fix words, may not change content) ----------
def grammar_ok(old: str, new: str) -> bool:
    if new_numbers(old, new): return False
    o, n = toks(old), toks(new)
    if not o or not n or not 0.75 <= len(n) / len(o) <= 1.3: return False
    so, sn = set(o), set(n)
    return len(so & sn) / len(so) >= 0.6 and len(sn - so) / len(sn) <= 0.4


def grammar_pass(texts: dict, call) -> tuple[dict, list]:
    if not texts: return {}, []
    parsed = call("grammar", GRAMMAR_PROMPT, json.dumps(texts, ensure_ascii=False))
    got = parsed.get("fields") if isinstance(parsed.get("fields"), dict) else parsed
    out, notes = {}, []
    for k, old in texts.items():
        new = got.get(k)
        if isinstance(new, str) and new.strip() and grammar_ok(old, new.strip()): out[k] = new.strip()
        else:
            out[k] = old
            if isinstance(new, str) and new.strip() and new.strip() != old: notes.append({"field": k, "message": "Binago ng grammar check ang nilalaman, kaya hindi ito tinanggap."})
    return out, notes


# ---------- assemble ----------
def build_draft(confirmed: dict, answers: dict, module_text: str, call, mode: str = "weekly") -> dict:
    conf = make_conf(confirmed, mode)
    if not conf["competencies"] or not conf["objectives"]:
        raise ValueError("Kumpirmahin muna ang Learning Competency at Learning Objectives mula sa module.")
    answers = answers or {}
    own = lambda k: str(answers.get(k) or "").strip()
    seed = {k: own(k) for k in ORGANIZABLE if own(k)}
    flow_in = _clean_list(answers.get("flow"))
    notes = []

    try: organized, n = organize(seed, flow_in, {k: conf[k] for k in LOCKED}, call); notes += n
    except Exception: organized = {}; notes.append({"field": "*", "message": "Hindi gumana ang AI sa pag-aayos. Ang mismong sagot mo ang ginamit."})

    texts = {k: organized.get(k) or seed[k] for k in ORGANIZABLE if k in seed}
    texts.update({k: own(k) for k in TEACHER_ONLY if own(k)})
    for i, s in enumerate(organized.get("flow") or flow_in): texts[f"flow.{i}"] = s
    try: fixed, n = grammar_pass(texts, call); notes += n
    except Exception: fixed = dict(texts); notes.append({"field": "*", "message": "Hindi gumana ang grammar check. Hindi naayos ang baybay at balarila."})

    def leaf(key, fallback, ai_text=None):
        base = ai_text or fallback
        return {"text": fixed.get(key, base), "source": "ai-organized" if ai_text else "teacher", "grammarFixed": fixed.get(key, base) != base}

    hay = norm(module_text)
    in_module = lambda items: (not hay) or all(norm(x) in hay for x in items)

    def locked_leaf(k):
        src = "extracted" if in_module(conf[k]) else "teacher-edited"
        if conf[k + "_days"] is not None: return {"text": "", "days": ["\n".join(d) for d in conf[k + "_days"]], "source": src}
        return {"text": "\n".join(conf[k]), "source": src}

    flow_ai = organized.get("flow")
    flow = [leaf(f"flow.{i}", s, flow_ai[i] if flow_ai else None) for i, s in enumerate(flow_ai or flow_in)]
    refs_own = own("references")
    draft = {
        "mode": conf["mode"],
        "header": {**{k: {"text": own(k), "source": "teacher"} for k in HEADER},
                   "references": {"text": refs_own or "\n".join(conf["references"]), "source": "teacher" if refs_own else "extracted"}},
        "intentions": {**{k: locked_leaf(k) for k in LOCKED}, "learnerContext": leaf("learnerContext", own("learnerContext"))},
        "experience": {"preLesson": leaf("preLesson", own("preLesson"), organized.get("preLesson")), "flow": flow,
                       "learningResources": leaf("learningResources", own("learningResources"), organized.get("learningResources")),
                       "integration": leaf("integration", own("integration"), organized.get("integration"))},
        "assessment": {"formative": leaf("formative", own("formative"), organized.get("formative"))},
        "waysForward": {"extendedLearning": leaf("extendedLearning", own("extendedLearning"), organized.get("extendedLearning")),
                        "reflections": leaf("reflections", own("reflections"))},
    }
    return {"draft": draft, "notes": notes, "check": check_draft(draft, conf, module_text)}


# ---------- stage 4: deterministic check (no AI) ----------
def check_draft(draft: dict, conf: dict, module_text: str = "") -> dict:
    flags = []
    flag = lambda level, field, msg: flags.append({"level": level, "field": field, "message": msg})
    g = lambda s, k: (draft.get(s) or {}).get(k) or {}
    txt = lambda s, k: str(g(s, k).get("text") or "").strip()
    hay = norm(module_text)

    for k in LOCKED:  # locked-field integrity: the saved text must equal what the teacher confirmed
        leaf, days = g("intentions", k), conf.get(k + "_days")
        saved = leaf.get("days") if days is not None else txt("intentions", k)
        expected = ["\n".join(d) for d in days] if days is not None else "\n".join(conf[k])
        if saved != expected or leaf.get("source") == "ai-organized":
            flag("fail", f"intentions.{k}", "Nabago ang naka-lock na field. Dapat kapareho ito ng kinumpirma mula sa module.")
        for item in conf[k] if hay else []:
            if norm(item) not in hay: flag("warn", f"intentions.{k}", f"Hindi makita nang eksakto sa module (na-edit ba?): \"{item[:60]}\"")
        if days is not None and k != "standards":
            for i, d in enumerate(days):
                if not d: flag("warn", f"intentions.{k}", f"Walang {k} para sa Day {i + 1}.")
    if not conf["standards"]: flag("warn", "intentions.standards", "Walang Curriculum Standards na nakumpirma.")

    for s, k, label in [("header", "lessonTitle", "Lesson Title"), ("header", "learningArea", "Learning Area/s"), ("header", "teacherName", "Name of Teacher/s"),
                        ("header", "gradeSection", "Grade Level and Section"), ("header", "noOfSessions", "No. of Sessions"),
                        ("experience", "preLesson", "Pre-Lesson"), ("assessment", "formative", "Formative Assessment")]:
        v = txt(s, k)
        if not v: flag("fail", f"{s}.{k}", f"Walang laman: {label}.")
        elif PLACEHOLDER.match(v): flag("fail", f"{s}.{k}", f"Placeholder lang ang laman ng {label}.")

    flow = [str(x.get("text") or "").strip() for x in (draft.get("experience") or {}).get("flow") or []]
    if not any(flow): flag("fail", "experience.flow", "Walang laman: Flow.")
    n = NUM.search(txt("header", "noOfSessions"))
    if n and flow and int(float(n.group().replace(",", "."))) != len(flow): flag("warn", "experience.flow", f"{len(flow)} sesyon ang nasa Flow pero {n.group()} ang nakalagay sa No. of Sessions.")
    for s, k, label in [("header", "references", "References"), ("intentions", "learnerContext", "Learner Context"), ("experience", "learningResources", "Learning Resources"),
                        ("experience", "integration", "Opportunities for integration (isulat ang N/A kung wala)"), ("waysForward", "extendedLearning", "Extended learning opportunities")]:
        if not txt(s, k): flag("warn", f"{s}.{k}", f"Walang laman: {label}.")

    fails, warns = sum(f["level"] == "fail" for f in flags), sum(f["level"] == "warn" for f in flags)
    return {"status": "fail" if fails else ("review" if warns else "pass"), "fail": fails, "warn": warns, "flags": flags, "note": NOTE}


# ---------- optional: advisory AI review (quotes are verified against the draft) ----------
def flat_text(draft: dict) -> str:
    lines = []
    for sec, fields in draft.items():
        if not isinstance(fields, dict): continue
        for k, v in fields.items():
            if isinstance(v, list): lines += [f"{sec}.{k}.{i + 1}: {x.get('text', '')}" for i, x in enumerate(v)]
            elif isinstance(v, dict) and v.get("days") is not None: lines += [f"{sec}.{k}.day{i + 1}: {t}" for i, t in enumerate(v["days"])]
            elif isinstance(v, dict): lines.append(f"{sec}.{k}: {v.get('text', '')}")
    return "\n".join(lines)


def review_draft(draft: dict, call) -> dict:
    flat = flat_text(draft)
    parsed = call("review", REVIEW_ILAW_PROMPT, "DRAFT TO REVIEW:\n\n" + flat)
    hay, flags = norm(flat), []
    for f in (parsed.get("flags") or [])[:10]:
        if not isinstance(f, dict): continue
        quote = str(f.get("quote") or "").strip()[:300]
        verified = (not quote) or norm(quote) in hay
        flags.append({"level": "fail" if f.get("level") == "fail" and verified else "warn", "field": str(f.get("field") or "")[:60], "check": f.get("check"),
                      "quote": quote, "quote_verified": verified, "message": str(f.get("message") or "")[:300]})
    fails = sum(f["level"] == "fail" for f in flags)
    return {"verdict": "problems" if fails else ("review" if flags else "ok"), "fail": fails, "warn": len(flags) - fails, "flags": flags}