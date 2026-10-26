"""A trustworthy dengue assistant.

Rules (enforced in code, not just in the prompt):
  * Answers ONLY from retrieved official guideline passages, with [n] citations. No passages -> say so.
  * Never diagnoses or prescribes. Diagnosis-seeking questions get general information + "see a doctor".
  * Warning signs of severe dengue (from WHO guidance) -> immediate "go to hospital / call 108" message
    and nearby facilities, BEFORE anything else.
  * Answers in the user's language (English, Kannada, Hindi).
  * Post-check: every citation must point to a passage we actually provided; otherwise the answer is
    replaced by a safe fallback.
Retrieval works on English documents, so non-English questions are translated for search first.
"""
from __future__ import annotations

import json
import re

from app import db
from app.services.assistant import llm
from app.services.assistant.retrieval import MIN_COVERAGE, search
from pipeline.config import load_city

LANG_NAMES = {"en": "English", "kn": "Kannada", "hi": "Hindi"}

# WHO warning signs of severe dengue, in the three languages (keyword match is deliberately broad).
WARNING_SIGNS = [
    "severe abdominal pain", "stomach pain", "persistent vomiting", "vomiting blood", "bleeding gums", "nose bleed",
    "nosebleed", "blood in", "black stool", "difficulty breathing", "breathless", "restless", "lethargic", "drowsy",
    "unconscious", "fainted", "cold clammy", "very weak",
    "पेट में तेज दर्द", "लगातार उल्टी", "खून", "मसूड़ों से खून", "सांस लेने में तकलीफ", "बेहोश",
    "ಹೊಟ್ಟೆ ನೋವು", "ವಾಂತಿ", "ರಕ್ತ", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಪ್ರಜ್ಞೆ",
]
DIAGNOSIS = [r"\bdo i have\b", r"\bis it dengue\b", r"\bam i\b.*\b(sick|infected)\b", r"\bwhat (medicine|tablet|dose)\b",
             r"\bhow much (paracetamol|medicine)\b", "क्या मुझे डेंगू", "ನನಗೆ ಡೆಂಗ್ಯೂ"]

URGENT = {
    "en": "These can be warning signs of severe dengue. Please go to the nearest hospital now or call {emergency} (ambulance). Do not wait.",
    "kn": "ಇವು ತೀವ್ರ ಡೆಂಗ್ಯೂವಿನ ಎಚ್ಚರಿಕೆ ಲಕ್ಷಣಗಳಾಗಿರಬಹುದು. ದಯವಿಟ್ಟು ತಕ್ಷಣ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ ಅಥವಾ {emergency} (ಆಂಬ್ಯುಲೆನ್ಸ್) ಗೆ ಕರೆ ಮಾಡಿ. ಕಾಯಬೇಡಿ.",
    "hi": "ये गंभीर डेंगू के चेतावनी संकेत हो सकते हैं। कृपया तुरंत नज़दीकी अस्पताल जाएँ या {emergency} (एम्बुलेंस) पर कॉल करें। इंतज़ार न करें।",
}
NO_DIAGNOSIS = {
    "en": "I can't tell whether you have dengue; only a doctor and a blood test can. Here is what official guidelines say:",
    "kn": "ನಿಮಗೆ ಡೆಂಗ್ಯೂ ಇದೆಯೇ ಎಂದು ನಾನು ಹೇಳಲಾರೆ; ವೈದ್ಯರು ಮತ್ತು ರಕ್ತ ಪರೀಕ್ಷೆ ಮಾತ್ರ ಹೇಳಬಹುದು. ಅಧಿಕೃತ ಮಾರ್ಗಸೂಚಿಗಳು ಹೇಳುವುದು:",
    "hi": "मैं यह नहीं बता सकता कि आपको डेंगू है या नहीं; यह केवल डॉक्टर और खून की जाँच से पता चलता है। आधिकारिक दिशानिर्देश यह कहते हैं:",
}
NOT_FOUND = {
    "en": "I couldn't find this in the official guidelines I use, so I won't guess. Please ask a doctor or call {helpline}.",
    "kn": "ನಾನು ಬಳಸುವ ಅಧಿಕೃತ ಮಾರ್ಗಸೂಚಿಗಳಲ್ಲಿ ಇದು ಸಿಗಲಿಲ್ಲ, ಆದ್ದರಿಂದ ನಾನು ಊಹಿಸುವುದಿಲ್ಲ. ದಯವಿಟ್ಟು ವೈದ್ಯರನ್ನು ಕೇಳಿ ಅಥವಾ {helpline} ಗೆ ಕರೆ ಮಾಡಿ.",
    "hi": "मुझे यह उन आधिकारिक दिशानिर्देशों में नहीं मिला जिनका मैं उपयोग करता हूँ, इसलिए मैं अनुमान नहीं लगाऊँगा। कृपया डॉक्टर से पूछें या {helpline} पर कॉल करें।",
}
MIN_SCORE = 2.0

SYSTEM = """You are NeighborHealth's dengue information assistant for residents of {city}.
Answer ONLY using the numbered passages from official guidelines given below. Cite each claim like [1] or [2][3].
If the passages don't answer the question, reply exactly: NOT_IN_SOURCES
Never diagnose, never say the user has or doesn't have dengue, never give medicine doses beyond what a passage states,
and always suggest seeing a doctor for personal symptoms. Keep it short (under 150 words), plain and kind.
Write the answer in {language}."""


def _helplines() -> dict:
    return load_city()["assistant"]["helplines"]


def _translate_for_search(q: str, lang: str) -> str:
    if lang == "en":
        return q
    out = llm.chat("Translate the user's question to English. Output only the translation.", q, max_tokens=120)
    return out or q


def _readable(text: str, limit: int = 400) -> str:
    """Passages are cut on a size boundary, so one can start mid-sentence. Show it from the first full sentence."""
    t = " ".join(text.split())
    if t and t[0].islower() and ". " in t[:200]:
        t = t.split(". ", 1)[1]
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + "…"


def select_passages(question_en: str, k: int = 6) -> list[dict]:
    """Passages relevant enough to answer from. Empty list means: say 'not in the sources'."""
    ranked = search(question_en, k=max(k * 4, 12))   # over-fetch, then keep only passages that cover the question
    return [p for p in ranked if p["score"] >= MIN_SCORE and p["coverage"] >= MIN_COVERAGE][:k]


def answer(question: str, language: str = "en", user_id: str | None = None) -> dict:
    lang = language if language in LANG_NAMES else "en"
    q = question.strip()[:800]
    ql = q.lower()
    hl = _helplines()
    result: dict = {"language": lang, "citations": [], "urgent": False, "refused_diagnosis": False}

    if any(w in ql for w in WARNING_SIGNS):
        result["urgent"] = True
        result["urgent_message"] = URGENT[lang].format(emergency=hl["emergency"])
    if any(re.search(p, ql) for p in DIAGNOSIS):
        result["refused_diagnosis"] = True

    passages = select_passages(_translate_for_search(q, lang), k=6)
    if not passages:
        result["answer"] = NOT_FOUND[lang].format(helpline=hl["health_helpline"])
        result["grounded"] = False
        return _log(result, q, user_id)

    context = "\n\n".join(f"[{i + 1}] ({p['org']}, {p['title']}, p.{p['page']}) {p['text']}" for i, p in enumerate(passages))
    text = llm.chat(SYSTEM.format(city=load_city()["city"]["name"], language=LANG_NAMES[lang]),
                    f"Passages:\n{context}\n\nQuestion: {q}")
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text or "")})
    valid = text and "NOT_IN_SOURCES" not in text and cited and all(1 <= n <= len(passages) for n in cited)
    if not valid:
        if text is None:  # no LLM configured: show the best passages verbatim (still grounded)
            result["answer"] = "\n\n".join(f"{_readable(p['text'])} [{i + 1}]" for i, p in enumerate(passages[:2]))
            cited = [1, 2][: len(passages[:2])]
            result["grounded"] = True
        else:
            result["answer"] = NOT_FOUND[lang].format(helpline=hl["health_helpline"])
            result["grounded"] = False
            return _log(result, q, user_id)
    else:
        result["answer"] = text.strip()
        result["grounded"] = True
    if result["refused_diagnosis"]:
        result["answer"] = NO_DIAGNOSIS[lang] + "\n\n" + result["answer"]
    result["citations"] = [{"n": n, "title": passages[n - 1]["title"], "org": passages[n - 1]["org"],
                            "url": passages[n - 1]["url"], "page": passages[n - 1]["page"],
                            "quote": passages[n - 1]["text"][:280]} for n in cited]
    return _log(result, q, user_id)


def _log(result: dict, q: str, user_id: str | None) -> dict:
    db.insert("chat_logs", {"id": db.new_id(), "user_id": user_id, "kind": "question", "question": q,
                            "answer": result["answer"], "citations": json.dumps(result["citations"]),
                            "language": result["language"], "refused": int(result["refused_diagnosis"]),
                            "grounded": int(bool(result.get("grounded"))), "created_at": db.now()})
    return result
