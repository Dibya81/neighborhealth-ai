"""BM25 retrieval over the guideline chunks (Okapi BM25, k1=1.5, b=0.75)."""
from __future__ import annotations

import json
from functools import lru_cache

from app.services.assistant.corpus import guidelines_dir, tokenize


@lru_cache
def _index() -> dict | None:
    p = guidelines_dir() / "index.json"
    return json.loads(p.read_text()) if p.exists() else None


def reload() -> None:
    _index.cache_clear()


# Words that carry no topic ("what should I ...") and must not count when judging relevance.
GENERIC = {"what", "which", "who", "whom", "whose", "when", "where", "why", "how", "does", "did", "do", "can", "could",
           "should", "would", "will", "shall", "may", "might", "must", "have", "has", "had", "get", "getting", "got", "take",
           "taking", "long", "much", "many", "best", "good", "about", "tell", "know", "need", "someone", "person", "people",
           "you", "your", "his", "her", "him", "she", "our", "they", "them", "also", "any", "all", "some", "more", "most",
           "my", "me", "mine", "are", "was", "one", "another", "other", "role", "way", "ways", "very", "just", "than", "like", "being", "been", "does", "doing", "home", "after", "before", "during", "while"}
# Lay wording -> the words the guidelines use. Small, explicit, reviewable.
SYNONYMS = {
    "symptom": ["sign", "feature"], "spread": ["transmission", "transmit", "transmitted"],
    "catch": ["transmission"], "contagious": ["transmission", "person-to-person"], "drink": ["fluid", "oral", "ors"],
    "treatment": ["management", "supportive", "symptomatic"], "treat": ["management", "supportive"],
    "medicine": ["paracetamol", "treatment"], "bite": ["biting", "feeding"], "last": ["duration", "days"],
    "prevent": ["control", "prevention"], "prevention": ["control"], "fly": ["flight"], "breed": ["breeding", "larva"],
    "danger": ["warning", "severe"], "emergency": ["warning", "severe"], "test": ["diagnosis", "diagnostic", "laboratory"],
    "blood": ["laboratory", "diagnosis"], "cause": ["virus", "etiology", "serotype", "infection"], "causes": ["virus", "etiology", "serotype"], "start": ["begin", "onset", "incubation"],
    "confirm": ["diagnosis", "detection", "ns1", "igm", "elisa"], "confirms": ["diagnosis", "detection", "ns1", "igm"], "kill": ["fogging", "insecticide"], "eat": ["fluid", "diet", "nutrition"],
}
MIN_COVERAGE = 0.6


SYNONYM_WEIGHT = 0.4    # what the user actually said counts more than our paraphrases of it


def _query_terms(query: str) -> tuple[list[tuple[str, float]], list[tuple[str, list[str]]]]:
    """(weighted terms used for scoring incl. synonyms, topic terms with their accepted alternatives for the relevance check)."""
    raw = [t for t in tokenize(query) if t not in GENERIC]
    expanded = [(t, 1.0) for t in raw]
    topic = []
    for t in raw:
        alts = [a for syn in SYNONYMS.get(t, []) for a in tokenize(syn)]
        expanded.extend((a, SYNONYM_WEIGHT) for a in alts)
        topic.append((t, alts))
    return expanded, topic


def _coverage(topic: list[tuple[str, list[str]]], tf: dict, idf: dict) -> float:
    """Share of the question's topic terms (weighted by rarity) found in a passage.
    A term the corpus has never seen ('cricket', 'Bengaluru') counts as maximally important and unmatched,
    so questions outside the guidelines are refused instead of answered with a random passage."""
    if not topic:
        return 0.0
    top = max(idf.values()) if idf else 1.0
    total = hit = 0.0
    for t, alts in {t: alts for t, alts in topic}.items():
        w = idf.get(t, top)
        total += w
        hit += w if (t in tf or any(a in tf for a in alts)) else 0.0
    return hit / total if total else 0.0


def search(query: str, k: int = 6, k1: float = 1.5, b: float = 0.75) -> list[dict]:
    idx = _index()
    if not idx or not idx["chunks"]:
        return []
    q, topic = _query_terms(query)
    scores = []
    for i, tf in enumerate(idx["tf"]):
        s = 0.0
        dl = idx["doc_len"][i]
        for t, wt in q:
            f = tf.get(t)
            if f:
                s += wt * idx["idf"].get(t, 0) * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / max(idx["avgdl"], 1)))
        if s > 0:
            scores.append((s, i, _coverage(topic, tf, idx["idf"])))
    scores.sort(reverse=True)
    out, seen = [], set()
    for s, i, cov in scores:
        c = idx["chunks"][i]
        key = (c["source_id"], c["text"][:80])
        if key in seen:
            continue
        seen.add(key)
        out.append({**c, "score": round(s, 3), "coverage": round(cov, 3)})
        if len(out) == k:
            break
    return out
