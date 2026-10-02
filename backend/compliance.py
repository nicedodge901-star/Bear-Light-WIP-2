"""Structure/compliance flags for a generated DLL.
Checks ONLY what the approved template in prompts.py requires (header, intentions, 9-step flow A-I, HOTS/values, resources).
It cannot verify that content is pedagogically correct or that competency codes are real: it says so in the result."""
import re

PLACEHOLDER = re.compile(r"^\s*(string|tbd|todo|n/?a|lorem ipsum.*|\[.*\]|\.\.\.)\s*$", re.I)
CODE_LIKE = re.compile(r"\b[A-Z]{1,3}\d{0,2}[A-Z]{2,}-[IVX]+[a-z]?(-[a-z])?-\d+\b")  # heuristic: looks like e.g. M1NS-Ia-1 (format NOT verified for MATATAG)
NOTE = "Istruktura lang ang sinusuri (ayon sa template ng app). Hindi nito pinapatunayan ang nilalaman, ang mga competency code, o ang opisyal na pag-apruba ng DepEd."

PROC_LABELS = {"a_review": "A (Balik-aral)", "b_purpose": "B (Layunin)", "c_examples": "C (Halimbawa)", "d_discussion": "D (Talakayan)", "e_mastery": "E (Formative)",
               "f_application": "F (Paglalapat)", "g_generalization": "G (Paglalahat)", "h_evaluation": "H (Pagtataya)", "i_remediation": "I (Remediation)"}


def check_dll(dll: dict) -> dict:
    flags = []

    def flag(level, section, path, msg): flags.append({"level": level, "section": section, "path": path, "message": msg})

    def get(path):
        v = dll
        for k in path.split("."):
            v = v.get(k) if isinstance(v, dict) else None
        return v if isinstance(v, str) else ("" if v is None else str(v))

    def need(path, section, label, level="fail", min_len=1):
        v = get(path).strip()
        if not v: flag(level, section, path, f"Walang laman: {label}.")
        elif PLACEHOLDER.match(v): flag("fail", section, path, f"Placeholder lang ang laman ng {label} (\"{v[:20]}\").")
        elif len(v) < min_len: flag("warn", section, path, f"Masyadong maikli ang {label}.")

    # Header: fields the template lists. Teacher-typed, so the teacher must fill them.
    for p, lbl in [("header.teacherName", "Pangalan ng Guro"), ("header.noOfSessions", "Bilang ng Sesyon"), ("header.references", "References"),
                   ("header.declarationOfAiUse", "Declaration of AI use")]: need(p, "Header", lbl)
    # Intentions
    need("objectives.contentStandard", "Intentions", "Content Standard"); need("objectives.performanceStandard", "Intentions", "Performance Standard")
    comps = (dll.get("objectives") or {}).get("learningCompetencies") or []
    if not comps: flag("fail", "Intentions", "objectives.learningCompetencies", "Walang Learning Competency.")
    elif any(PLACEHOLDER.match(str(c)) for c in comps): flag("fail", "Intentions", "objectives.learningCompetencies", "May placeholder sa Learning Competencies.")
    if any(CODE_LIKE.search(str(c)) for c in comps):
        flag("warn", "Intentions", "objectives.learningCompetencies", "May competency code na mukhang opisyal. Hindi ito mabe-verify ng AI: ikumpara sa opisyal na listahan.")
    # Flow A-I
    for k, lbl in PROC_LABELS.items(): need(f"procedures.{k}", "Learning Experience", f"Hakbang {lbl}", min_len=40)
    # HOTS + values + resources
    need("content.hotsSkills", "Learning Experience", "HOTS", level="warn"); need("content.integrationValues", "Learning Experience", "Values integration", level="warn")
    if not any(get(f"resources.{k}").strip() for k in ("teacherGuidePages", "learnerMaterialPages", "textbookPages", "additionalMaterials")):
        flag("warn", "Learning Resources", "resources.additionalMaterials", "Walang nakalistang Learning Resources.")

    fails, warns = sum(f["level"] == "fail" for f in flags), sum(f["level"] == "warn" for f in flags)
    return {"status": "fail" if fails else ("review" if warns else "pass"), "fail": fails, "warn": warns, "flags": flags, "note": NOTE}