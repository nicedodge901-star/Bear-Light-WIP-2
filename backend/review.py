"""AI review pass: a second model checks a drafted DLL against the Bear-Light skill rules (the Phase 1 workflow that passed school review).
It is ADVISORY: every flag must quote the DLL text, and quotes that do not exist in the DLL are marked unverified."""
import re

REVIEW_PROMPT = """You are a strict reviewer of a DepEd MATATAG Daily Lesson Log (DLL) that another AI drafted for a Filipino public school teacher.
The teacher is accountable for this official document, so accuracy matters more than politeness. Apply ONLY the rules below. Do not use outside knowledge of DepEd policy, and never claim the DLL is "DepEd compliant".

RULES
1. Competency codes: a formal-looking curriculum code (letters, digits and dashes, for example M1NS-Ia-1) must be marked [VERIFY CODE] or flagged as uncertain. An unflagged code is a problem, because the drafter must never guess codes.
2. Learning objectives must be specific and observable, and must not be the competency restated in other words.
3. The Flow must sequence activities across the sessions. Flag it if it looks like one generic session repeated.
4. Learner context, class size and resources must not be invented. Flag confident claims about the class that no input supports.
5. Opportunities for integration may be N/A. Flag a forced or unrealistic integration.
6. The Flow should connect to prior learning, check understanding, encourage collaboration, and include all learners.
7. Formative assessment must include a concrete task or questions, ways for learners to ask for help, and accommodations.
8. Flag generic filler that could apply to any week, or vague inspirational wording where concrete steps are needed.
9. Anything the drafter was unsure about must be flagged in bold as "Flag: [thing], because [why]". Flag confident wording on uncertain items.
10. No emojis anywhere.
11. Flag placeholder or schema-echo text (for example "string", "TBD", "[insert]") and empty sections.

OUTPUT: return ONLY one JSON object, with no commentary and no code fences:
{"verdict":"ok|review|problems","flags":[{"level":"fail|warn","section":"section name","rule":1,"quote":"text copied EXACTLY from the DLL, or an empty string if something is missing","message":"one short sentence saying what is wrong and why"}]}
- At most 12 flags, most serious first. Use "fail" only for clear rule violations.
- Every flag about existing text MUST quote it exactly. If you cannot quote it, leave quote empty and say what is missing.
- Do not praise. If nothing is wrong, return {"verdict":"ok","flags":[]}.
"""

SKIP = {"leftLogoUrl", "rightLogoUrl", "compliance", "review", "id", "providerUsed", "tierUsed", "fallbackOccurred", "dateCreated", "title"}


def flatten(dll: dict) -> str:
    """The DLL as readable 'section.field: text' lines for the reviewer."""
    lines = []
    for sec, val in dll.items():
        if sec in SKIP: continue
        if isinstance(val, dict):
            for k, v in val.items():
                if k in SKIP: continue
                lines.append(f"{sec}.{k}: " + (" | ".join(map(str, v)) if isinstance(v, list) else str(v or "")))
    return "\n".join(lines)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower().strip("\"'")


def normalize(parsed: dict, dll: dict) -> dict:
    """Clean the model output; verify each quote really appears in the DLL (anti-hallucination)."""
    hay, flags = _norm(flatten(dll)), []
    for f in (parsed.get("flags") or [])[:12]:
        if not isinstance(f, dict): continue
        quote = str(f.get("quote") or "").strip()[:300]
        verified = (not quote) or (_norm(quote) in hay)
        level = "fail" if f.get("level") == "fail" else "warn"
        flags.append({"level": level if verified else "warn",  # an unverifiable quote can never be a hard failure
                      "section": str(f.get("section") or "")[:60], "rule": f.get("rule"), "quote": quote,
                      "quote_verified": verified, "message": str(f.get("message") or "")[:300]})
    fails = sum(f["level"] == "fail" for f in flags)
    verdict = "problems" if fails else ("review" if flags else "ok")
    return {"verdict": verdict, "fail": fails, "warn": len(flags) - fails, "flags": flags}
