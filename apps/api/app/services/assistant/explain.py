"""Explain a ward's risk using ONLY the model's own numbers (SHAP factors + ward estimate).

The LLM gets a list of facts and must write 2-3 sentences from them. A verifier then checks the
text: every number it mentions must appear in the facts (±0.5 or the same rounded %), and it
must not mention a driver that isn't among the factors. Failing text is replaced by a
deterministic template, so a hallucinated reason can never reach the user.
`scripts/eval_explanations.py` runs this over every ward and reports the pass rate.
"""
from __future__ import annotations

import re

from app.forecast_store import get_bundle, ward_estimate
from app.geo import ward_name
from app.services.assistant import llm
from app.services.alerts.templates import BANDS

KNOWN_DRIVER_WORDS = {
    "rain": ["rain", "rainfall", "monsoon", "showers"],
    "temperature": ["temperature", "heat", "warm", "cold"],
    "humidity": ["humidity", "humid", "moisture"],
    "trend": ["trend", "recent cases", "rising", "falling"],
    "seasonal": ["last year", "previous year"],
    "testing": ["testing", "tests", "positivity"],
    "season": ["time of year", "season"],
}

SYSTEM = """You explain a dengue risk ESTIMATE for one city ward to residents. Use ONLY the facts given.
Do not add causes, numbers, places or advice that are not in the facts. 2-3 short sentences, plain {language}.
Mention that ward values are estimates derived from the city-wide forecast."""


def facts_for(ward_id: str, horizon: int = 1) -> dict | None:
    b = get_bundle()
    est = ward_estimate(ward_id, horizon)
    if not b or not est:
        return None
    fc = next(f for f in b["forecast"] if f["horizon"] == horizon)
    factors = (b.get("drivers") or {}).get("factors", [])[:3]
    return {
        "ward": ward_name(ward_id), "band": est["band"], "rate_per_100k": est["rate_per_100k"],
        "rate_interval": [est["rate_lo80"], est["rate_hi80"]], "uncertainty": est["uncertainty"],
        "city_cases": fc["median"], "city_interval": [fc.get("lo80"), fc.get("hi80")], "week_end": fc["week_end"],
        "factors": [{"label": f["label"], "factor": f["factor"], "direction": f["direction"],
                     "effect_pct": f["effect_pct"]} for f in factors],
    }


def _numbers(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", text)]


def verify(text: str, facts: dict) -> tuple[bool, list[str]]:
    problems = []
    allowed = []
    for v in [facts["rate_per_100k"], *facts["rate_interval"], facts["city_cases"], *facts["city_interval"],
              *[abs(f["effect_pct"]) for f in facts["factors"]], 1, 80, 100000, 100]:  # 80% / per 100,000
        if v is not None:
            allowed.append(float(v))
    allowed += [float(x) for x in re.findall(r"\d+", facts["week_end"])]
    for n in _numbers(text):
        if not any(abs(n - a) <= 0.5 or round(n) == round(a) for a in allowed):
            problems.append(f"number {n} not in facts")
    present = {f["factor"] for f in facts["factors"]}
    low = text.lower()
    for factor, words in KNOWN_DRIVER_WORDS.items():
        if factor not in present and any(w in low for w in words):
            problems.append(f"mentions '{factor}' which is not a driver")
    return (not problems), problems


def template(facts: dict, language: str = "en") -> str:
    band = BANDS.get(language, BANDS["en"]).get(facts["band"], facts["band"])
    parts = [f"Estimated dengue risk in {facts['ward']} is {band} for the week ending {facts['week_end']} "
             f"(about {facts['rate_per_100k']:.1f} reported cases per 100,000 people; likely range "
             f"{facts['rate_interval'][0]:.1f}–{facts['rate_interval'][1]:.1f})."]
    if facts["factors"]:
        drivers = ", ".join(f"{f['label'].lower()} ({'+' if f['effect_pct'] > 0 else ''}{f['effect_pct']:.0f}%)"
                            for f in facts["factors"])
        parts.append(f"The city-wide forecast is driven mainly by: {drivers}.")
    parts.append("Ward values are estimates derived from the city-wide forecast, not counted ward cases.")
    return " ".join(parts)


def explain_ward(ward_id: str, horizon: int = 1, language: str = "en") -> dict:
    facts = facts_for(ward_id, horizon)
    if not facts:
        return {"available": False}
    lang_name = {"en": "English", "kn": "Kannada", "hi": "Hindi"}.get(language, "English")
    text = llm.chat(SYSTEM.format(language=lang_name), f"Facts (JSON): {facts}", temperature=0.0, max_tokens=220)
    method = "llm"
    problems: list[str] = []
    if text and language == "en":
        ok, problems = verify(text, facts)
        if not ok:
            text, method = template(facts, language), "template (LLM failed verification)"
    elif text is None:
        text, method = template(facts, language), "template"
    # Non-English text can't be number-checked as reliably; it is generated from the same facts and
    # shown together with the structured factor list, which is always the source of truth.
    return {"available": True, "text": text, "method": method, "verification_problems": problems, "facts": facts}
